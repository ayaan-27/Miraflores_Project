import csv
from io import StringIO
import json
from pathlib import Path

import pytest

from variance_workspace.controls import schedule
from variance_workspace.data import Workspace, SAMPLES, parse_ledger, dollars
from variance_workspace.workflow import Service
from variance_tests.fakes import Planner


@pytest.fixture
def service(tmp_path):
    return Service(Workspace(tmp_path), Planner())


def decision(action):
    return {"action": action, "reviewer": "Demo reviewer", "note": "Reviewed the supporting source and close policy."}


def test_materiality_and_amounts_come_from_ledger(service):
    accounts = {a["code"]: a for a in service.workspace.accounts()}
    assert accounts["6100"]["previous_cents"] == 200000
    assert accounts["6100"]["current_cents"] == 2600000
    assert accounts["6100"]["change_cents"] == 2400000
    assert sum(a["material"] for a in accounts.values()) == 3


def test_full_evidence_loop_keeps_history_and_proposes_balanced_entry(service):
    run = service.start("6100")
    first = service.view(run)
    assert first["analysis"]["outcome"] == "evidence_needed"
    assert first["analysis"]["adjustment_cents"] == 0
    assert first["analysis"]["missing_document_id"] == "AGR-SW-2026"
    with pytest.raises(ValueError, match="blocked"):
        service.review(run, decision("approve"))
    service.review(run, decision("request_evidence"))
    assert service.view(run)["next_nodes"] == ["evidence"]
    with pytest.raises(ValueError):
        service.reply(run, (SAMPLES / "wrong-contract.pdf").read_bytes(), "wrong.pdf")
    assert service.view(run)["round"] == 1
    assert service.workspace.document("AGR-SW-WRONG") is None
    second = service.reply(run, (SAMPLES / "software-contract.pdf").read_bytes(), "contract.pdf")
    assert second["round"] == 2
    assert second["analysis"]["adjustment_cents"] == 2200000
    assert second["analysis"]["adjusted_cents"] == 400000
    assert sum(r["expense_cents"] for r in second["analysis"]["allocation"]) == 2400000
    assert len(second["history"]) == 1
    assert sum(r["debit_cents"] for r in second["analysis"]["journal"]) == sum(r["credit_cents"] for r in second["analysis"]["journal"]) == 2200000
    final = service.review(run, decision("approve"))
    assert final["completion"]["outcome"] == "workpaper_approved"
    assert final["completion"]["journal_posted"] is False
    assert len(final["history"]) == 2


def test_pause_survives_reopening_sqlite(service):
    run = service.start("6100")
    service.review(run, decision("request_evidence"))
    reopened = Service(Workspace(service.workspace.directory), Planner())
    assert reopened.view(run)["next_nodes"] == ["evidence"]
    assert len(reopened.view(run)["history"]) == 1
    resumed = reopened.reply(run, (SAMPLES / "software-contract.pdf").read_bytes(), "contract.pdf")
    assert resumed["analysis"]["adjustment_cents"] == 2200000


def test_approved_bonus_explains_change_without_adjustment(service):
    run = service.start("6200")
    state = service.view(run)
    assert state["analysis"]["outcome"] == "explained"
    assert state["analysis"]["adjustment_cents"] == 0
    assert state["analysis"]["approval_allowed"] is True
    assert state["analysis"]["journal"] == []


def test_current_period_consulting_service_needs_no_deferral(service):
    run = service.start("6300")
    service.review(run, decision("request_evidence"))
    state = service.reply(run, (SAMPLES / "consulting-agreement.pdf").read_bytes(), "agreement.pdf")
    assert state["analysis"]["outcome"] == "explained"
    assert state["analysis"]["adjustment_cents"] == 0
    assert state["analysis"]["adjusted_cents"] == 1400000


def test_duplicate_posting_is_held_even_with_a_reviewer_note(tmp_path):
    rows = list(csv.DictReader(StringIO((SAMPLES / "ledger.csv").read_text())))
    duplicate = dict(next(r for r in rows if r["id"] == "SW-O3"), id="SW-O4")
    out = StringIO(); writer = csv.DictWriter(out, fieldnames=rows[0]); writer.writeheader(); writer.writerows([*rows, duplicate])
    service = Service(Workspace(tmp_path, out.getvalue().encode()), Planner())
    run = service.start("6100")
    assert service.view(run)["analysis"]["outcome"] == "hold"
    with pytest.raises(ValueError, match="blocked"):
        service.review(run, decision("approve"))


def test_invalid_ledger_and_pdf_preserve_waiting_case(service):
    run = service.start("6100"); service.review(run, decision("request_evidence"))
    with pytest.raises(ValueError, match="duplicate"):
        parse_ledger((SAMPLES / "invalid-ledger.csv").read_bytes())
    with pytest.raises(ValueError, match="PDF"):
        service.reply(run, b"not a pdf", "invalid.pdf")
    assert service.view(run)["status"] == "awaiting_evidence"
    assert service.view(run)["round"] == 1


def test_cent_rounding_conserves_contract_total_and_rejects_partial_months():
    result = schedule(10001, "2026-10-01", "2027-09-30", "2026-10")
    assert result["current_expense_cents"] == 834
    assert sum(r["expense_cents"] for r in result["rows"]) == 10001
    with pytest.raises(ValueError, match="Partial-month"):
        schedule(2400000, "2026-10-15", "2027-09-30", "2026-10")


def test_invalid_model_action_stops_with_checkpoint_and_retry(service):
    original = service.model.choose
    service.model.choose = lambda state, available: __import__('variance_workspace.model', fromlist=['Choice']).Choice(action="finish", purpose="Finish without evidence.")
    with pytest.raises(ValueError, match="unavailable"):
        service.start("6100")
    run = service.latest("6100")
    assert service.view(run)["error"]
    service.model.choose = original
    result = service.retry(run)
    assert result["status"] == "awaiting_review"
    assert result["error"] is None


def test_no_writes_or_unmaterial_investigation(service):
    with pytest.raises(ValueError, match="read queries"):
        service.workspace.query("DELETE FROM transactions")
    with pytest.raises(ValueError, match="threshold"):
        service.start("6400")
