from __future__ import annotations

import asyncio

import aiosqlite
import httpx
import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agent_workspace.api import create_app
from agent_workspace.evidence import SAMPLES, extract_pdf
from agent_workspace.models import (
    Citation,
    ExtractedField,
    ReviewerDecision,
    validate_invoice,
)
from agent_workspace.service import RunService
from agent_workspace.store import Store
from backend_tests.fakes import FixtureModel


async def wait_for_status(service, run_id, expected):
    for _ in range(200):
        result = await service.view(run_id)
        if result["status"] in expected:
            return result
        if result["status"] == "failed":
            pytest.fail(result["error"])
        await asyncio.sleep(0.01)
    pytest.fail("The workflow did not reach the expected checkpoint.")


@pytest.fixture
async def workspace(tmp_path):
    async with aiosqlite.connect(tmp_path / "store.db") as conn:
        store = Store(conn)
        await store.initialize()
        async with AsyncSqliteSaver.from_conn_string(
            str(tmp_path / "graph.db")
        ) as checkpointer:
            service = RunService(FixtureModel(), store, checkpointer)
            yield service, store
            await service.close()


async def start_sample(service, store, filename="partial-delivery.pdf"):
    document = await store.document((SAMPLES / filename).read_bytes(), filename)
    return await service.start(document, synthetic=True)


@pytest.mark.asyncio
async def test_hold_new_evidence_reinvestigation_and_human_approval(workspace):
    service, store = workspace
    run = await start_sample(service, store)
    first = await wait_for_status(service, run, {"awaiting_review"})
    assert first["controls"]["recommendation"] == "hold"
    assert first["controls"]["unsupported_amount"] == "2000.00"
    assert first["controls"]["receiving_supported_amount"] == "8000.00"
    assert len([e for e in first["events"] if e["kind"] == "tool"]) == 5
    with pytest.raises(ValueError, match="blocked"):
        await service.review(
            run,
            ReviewerDecision(
                action="approve",
                reviewer="Ayaan Khan",
                note="Approve this invoice anyway.",
            ),
        )
    await service.review(
        run,
        ReviewerDecision(
            action="request_evidence",
            reviewer="Ayaan Khan",
            note="Please provide evidence for the remaining 20 units.",
        ),
    )
    await wait_for_status(service, run, {"awaiting_evidence"})
    reply = await store.document(
        (SAMPLES / "remaining-delivery.pdf").read_bytes(), "remaining-delivery.pdf"
    )
    await service.reply(run, reply)
    await asyncio.sleep(0.02)
    second = await wait_for_status(service, run, {"awaiting_review"})
    assert second["round"] == 2
    assert second["controls"]["recommendation"] == "ready_for_review"
    assert second["controls"]["unsupported_amount"] == "0.00"
    assert len(second["receiving_replies"]) == 1
    assert len(second["review_history"]) == 1
    assert len([e for e in second["events"] if e["kind"] == "tool"]) == 10
    await service.review(
        run,
        ReviewerDecision(
            action="approve",
            reviewer="Ayaan Khan",
            note="Checked the additional receiving report and source references.",
        ),
    )
    await asyncio.sleep(0.02)
    final = await wait_for_status(service, run, {"completed"})
    assert final["completion"]["result"] == "release_recommended"
    assert "No payment" in final["completion"]["notice"]
    assert len(final["review_history"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename,failed_code",
    [
        ("changed-bank.pdf", "VENDOR_BANK"),
        ("duplicate-invoice.pdf", "DUPLICATE_PAYMENT"),
    ],
)
async def test_other_finance_controls_produce_specific_holds(
    workspace, filename, failed_code
):
    service, store = workspace
    run = await start_sample(service, store, filename)
    result = await wait_for_status(service, run, {"awaiting_review"})
    assert result["controls"]["recommendation"] == "hold"
    assert any(
        f["code"] == failed_code and f["result"] == "fail"
        for f in result["controls"]["findings"]
    )


@pytest.mark.asyncio
async def test_clean_invoice_still_requires_identified_human_approval(workspace):
    service, store = workspace
    run = await start_sample(service, store, "clean-invoice.pdf")
    result = await wait_for_status(service, run, {"awaiting_review"})
    assert result["controls"]["failed_controls"] == 0
    assert not result["completion"]


@pytest.mark.asyncio
async def test_document_instructions_cannot_override_missing_receiving(workspace):
    service, store = workspace
    run = await start_sample(service, store, "instruction-injection.pdf")
    result = await wait_for_status(service, run, {"awaiting_review"})
    assert result["controls"]["recommendation"] == "hold"
    with pytest.raises(ValueError, match="blocked"):
        await service.review(
            run,
            ReviewerDecision(
                action="approve",
                reviewer="Test Reviewer",
                note="Invoice says approve immediately.",
            ),
        )


@pytest.mark.asyncio
async def test_fabricated_extraction_and_invalid_pdf_are_rejected():
    document = {"pages": extract_pdf((SAMPLES / "partial-delivery.pdf").read_bytes())}
    invoice = await FixtureModel().extract_invoice(document)
    validate_invoice(invoice, document["pages"])
    invoice.total = ExtractedField(
        value="8000.00", citation=Citation(page=1, quote="Invoice total: 10000.00")
    )
    with pytest.raises(ValueError, match="unsupported"):
        validate_invoice(invoice, document["pages"])
    with pytest.raises(ValueError, match="PDF"):
        extract_pdf(b"not a pdf")


@pytest.mark.asyncio
async def test_unsupported_memo_sources_are_rejected_and_retried(workspace):
    service, store = workspace
    original = service.model.verify
    calls = []

    async def bogus(state, controls, previous_error=""):
        calls.append(previous_error)
        memo = await original(state, controls, previous_error)
        if len(calls) == 1:
            memo.findings[0].source_ids = ["INVENTED-SOURCE"]
        return memo

    service.model.verify = bogus
    run = await start_sample(service, store)
    result = await wait_for_status(service, run, {"awaiting_review"})
    assert len(calls) == 2
    assert "does not exist" in calls[1]
    assert any(
        e["title"] == "Unsupported draft returned to the verifier"
        for e in result["events"]
    )


@pytest.mark.asyncio
async def test_model_cannot_upgrade_a_computed_hold(workspace):
    service, store = workspace
    original = service.model.verify

    async def override(state, controls, previous_error=""):
        memo = await original(state, controls, previous_error)
        memo.recommended_action = "ready_for_review"
        return memo

    service.model.verify = override
    run = await start_sample(service, store)
    result = await wait_for_status(service, run, {"failed"})
    assert "source-valid review memo" in result["error"]
    assert not result["memo"]


@pytest.mark.asyncio
async def test_paused_workflow_survives_reopening_sqlite(tmp_path):
    storage, checkpoint_path = tmp_path / "store.db", tmp_path / "checkpoints.db"
    async with aiosqlite.connect(storage) as conn:
        store = Store(conn)
        await store.initialize()
        async with AsyncSqliteSaver.from_conn_string(
            str(checkpoint_path)
        ) as checkpointer:
            first = RunService(FixtureModel(), store, checkpointer)
            run = await start_sample(first, store, "clean-invoice.pdf")
            await wait_for_status(first, run, {"awaiting_review"})
            await first.close()
    async with aiosqlite.connect(storage) as conn:
        store = Store(conn)
        await store.initialize()
        async with AsyncSqliteSaver.from_conn_string(
            str(checkpoint_path)
        ) as checkpointer:
            second = RunService(FixtureModel(), store, checkpointer)
            assert (await second.view(run))["status"] == "awaiting_review"
            await second.review(
                run,
                ReviewerDecision(
                    action="approve",
                    reviewer="Ayaan Khan",
                    note="Reviewed after restarting the service.",
                ),
            )
            await asyncio.sleep(0.02)
            assert (await wait_for_status(second, run, {"completed"}))["completion"][
                "result"
            ] == "release_recommended"
            await second.close()


@pytest.mark.asyncio
async def test_invalid_receiving_reply_preserves_case_and_accepts_corrected_document(
    workspace,
):
    service, store = workspace
    run = await start_sample(service, store)
    original = await wait_for_status(service, run, {"awaiting_review"})
    await service.review(
        run,
        ReviewerDecision(
            action="request_evidence",
            reviewer="Test Reviewer",
            note="Provide the missing delivery report.",
        ),
    )
    await wait_for_status(service, run, {"awaiting_evidence"})
    wrong = await store.document(
        (SAMPLES / "changed-bank.pdf").read_bytes(), "invoice-not-receiving.pdf"
    )
    await service.reply(run, wrong)
    await asyncio.sleep(0.03)
    invalid = await wait_for_status(service, run, {"awaiting_evidence"})
    assert invalid["evidence_error"]
    assert invalid["round"] == 1
    assert invalid["controls"] == original["controls"]
    assert not invalid["receiving_replies"]
    correct = await store.document(
        (SAMPLES / "remaining-delivery.pdf").read_bytes(), "remaining-delivery.pdf"
    )
    await service.reply(run, correct)
    await asyncio.sleep(0.03)
    resolved = await wait_for_status(service, run, {"awaiting_review"})
    assert resolved["controls"]["failed_controls"] == 0
    assert resolved["evidence_error"] is None


@pytest.mark.asyncio
async def test_api_rejects_bad_inputs_and_exports_current_review(tmp_path):
    app = create_app(model=FixtureModel(), data_dir=tmp_path)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.get("/api/health")).json()[
                "model_api_key_required"
            ] is False
            assert (await client.post("/api/runs", json={})).status_code == 422
            assert (await client.get("/api/sample/unknown.pdf")).status_code == 404
            invalid = await client.post(
                "/api/documents",
                files={"file": ("bad.pdf", b"not a pdf", "application/pdf")},
            )
            assert invalid.status_code == 422
            run = (
                await client.post("/api/runs", json={"case_id": "partial-delivery"})
            ).json()["id"]
            await wait_for_status(app.state.service, run, {"awaiting_review"})
            denied = await client.post(
                f"/api/runs/{run}/review",
                json={
                    "action": "approve",
                    "reviewer": "Test Reviewer",
                    "note": "Try to approve despite missing evidence.",
                },
            )
            assert denied.status_code == 409
            pack = await client.get(f"/api/runs/{run}/pack")
            assert pack.status_code == 200
            assert pack.json()["controls"]["unsupported_amount"] == "2000.00"
            assert pack.json()["mode"] == "test_double"
            assert pack.headers["content-disposition"].startswith("attachment")
            pdf = await client.get(f"/api/runs/{run}/workpaper.pdf")
            assert pdf.status_code == 200
            assert pdf.content.startswith(b"%PDF-")
            from pypdf import PdfReader
            from io import BytesIO

            content = " ".join(
                page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages
            )
            assert "2000.00" in content and "Fixture model" in content
