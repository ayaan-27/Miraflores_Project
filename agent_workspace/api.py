from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import json
import re

import aiosqlite
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel, Field

from .evidence import CATALOG, MAX_PDF_BYTES, SAMPLES
from .model import configured_model, model_ready, DATA_DIR
from .models import EvidenceResponse, ReviewerDecision
from .service import RunService
from .store import Store, now


class StartRequest(BaseModel):
    case_id: str | None = Field(default=None, max_length=80)
    document_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


def create_app(*, model=None, data_dir: Path | None = None):
    runtime_model = model or configured_model()
    data_dir = data_dir or DATA_DIR

    @asynccontextmanager
    async def lifespan(app):
        data_dir.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(data_dir / "workspace.db") as connection:
            store = Store(connection)
            await store.initialize()
            async with AsyncSqliteSaver.from_conn_string(
                str(data_dir / "checkpoints.db")
            ) as checkpointer:
                service = RunService(runtime_model, store, checkpointer)
                app.state.service, app.state.store = service, store
                yield
                await service.close()

    app = FastAPI(
        title="LedgerLens Invoice Investigator", version="2.0.0", lifespan=lifespan
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://ayaan-27.github.io",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def request_limits(request, call_next):
        if request.url.path == "/api/documents" and request.method == "POST":
            length = request.headers.get("content-length")
            if length is None:
                return JSONResponse(
                    {
                        "detail": "A Content-Length header is required for document uploads."
                    },
                    status_code=411,
                )
            try:
                too_large = int(length) > MAX_PDF_BYTES + 20_000
            except ValueError:
                return JSONResponse(
                    {"detail": "Invalid request size."}, status_code=400
                )
            if too_large:
                return JSONResponse(
                    {"detail": "Document upload exceeds 2 MB."}, status_code=413
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def identifier(value):
        if not re.fullmatch(r"[a-f0-9]{32}", value):
            raise HTTPException(404, "Run or document not found.")
        return value

    @app.get("/api/health")
    async def health():
        ready = await model_ready(runtime_model)
        return {
            "status": "ok",
            "model_ready": ready,
            "model_setup_message": getattr(runtime_model, "readiness_error", "") if not ready else "",
            "mode": runtime_model.mode,
            "model": runtime_model.name,
            "framework": "LangGraph",
            "model_api_key_required": False,
            "notice": "Demonstration workspace. Use synthetic documents only. No payments or messages are sent.",
        }

    @app.get("/api/cases")
    async def cases():
        return {
            "cases": CATALOG["cases"],
            "sources": "Synthetic internal-system fixtures; these are not real accounting integrations.",
        }

    @app.get("/api/sample/{filename}")
    async def sample(filename: str):
        allowed = {case["file"] for case in CATALOG["cases"]} | {
            "remaining-delivery.pdf",
            "instruction-injection.pdf",
        }
        if filename not in allowed:
            raise HTTPException(404, "Sample not found.")
        return FileResponse(
            SAMPLES / filename, media_type="application/pdf", filename=filename
        )

    @app.post("/api/documents", status_code=201)
    async def upload(file: UploadFile = File()):
        data = await file.read(MAX_PDF_BYTES + 1)
        try:
            document = await app.state.store.document(
                data, file.filename or "invoice.pdf"
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return {
            "id": document["id"],
            "filename": document["filename"],
            "pages": len(document["pages"]),
        }

    @app.post("/api/runs", status_code=202)
    async def start(request: StartRequest):
        if bool(request.case_id) == bool(request.document_id):
            raise HTTPException(422, "Choose one sample case or one uploaded document.")
        if request.case_id:
            case = next(
                (case for case in CATALOG["cases"] if case["id"] == request.case_id),
                None,
            )
            if not case:
                raise HTTPException(404, "Sample case not found.")
            document = await app.state.store.document(
                (SAMPLES / case["file"]).read_bytes(), case["file"]
            )
        else:
            document = await app.state.store.get_document(request.document_id)
            if not document:
                raise HTTPException(404, "Document not found.")
        try:
            run_id = await app.state.service.start(
                document, request.case_id, synthetic=bool(request.case_id)
            )
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {"id": run_id}

    @app.get("/api/runs")
    async def runs():
        return {"runs": await app.state.store.runs()}

    @app.get("/api/runs/{run_id}")
    async def view(run_id: str):
        result = await app.state.service.view(identifier(run_id))
        if result is None:
            raise HTTPException(404, "Run not found.")
        return result

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str, after: int = 0):
        identifier(run_id)
        if not await app.state.store.get_run(run_id):
            raise HTTPException(404, "Run not found.")

        async def generate():
            cursor = max(0, after)
            for _ in range(1800):
                records = await app.state.store.events(run_id, cursor)
                for event in records:
                    cursor = event["seq"]
                    yield "id: " + str(cursor) + "\ndata: " + json.dumps(event) + "\n\n"
                status = (await app.state.store.get_run(run_id))["status"]
                if status != "running":
                    yield (
                        "event: state\ndata: " + json.dumps({"status": status}) + "\n\n"
                    )
                    return
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @app.post("/api/runs/{run_id}/review", status_code=202)
    async def review(run_id: str, decision: ReviewerDecision):
        try:
            await app.state.service.review(identifier(run_id), decision)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {"status": "queued"}

    @app.post("/api/runs/{run_id}/evidence", status_code=202)
    async def reply(run_id: str, response: EvidenceResponse):
        document = await app.state.store.get_document(response.document_id)
        if not document:
            raise HTTPException(404, "Document not found.")
        try:
            await app.state.service.reply(identifier(run_id), document)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {"status": "queued"}

    @app.post("/api/runs/{run_id}/retry", status_code=202)
    async def retry(run_id: str):
        try:
            await app.state.service.retry(identifier(run_id))
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {"status": "queued"}

    @app.get("/api/runs/{run_id}/pack")
    async def pack(run_id: str):
        result = await app.state.service.view(identifier(run_id))
        if not result:
            raise HTTPException(404, "Run not found.")
        if not result.get("controls"):
            raise HTTPException(
                409, "The investigation has not produced verified controls yet."
            )
        result["exported_at"] = now()
        result["schema_version"] = 2
        result["notice"] = (
            "Editable review export, not a tamper-evident audit record. No payment or message has been sent."
        )
        return Response(
            json.dumps(result, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="ledgerlens-investigation.json"'
            },
        )

    @app.get("/api/runs/{run_id}/workpaper.pdf")
    async def workpaper(run_id: str):
        result = await app.state.service.view(identifier(run_id))
        if result is None:
            raise HTTPException(404, "Run not found.")
        if not result.get("controls"):
            raise HTTPException(
                409, "Verified controls are required before creating a workpaper."
            )
        from .workpaper import render_workpaper

        return Response(
            render_workpaper(result),
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="ledgerlens-workpaper.pdf"'
            },
        )

    @app.get("/api/documents/{document_id}")
    async def document(document_id: str):
        result = await app.state.store.get_document(
            identifier(document_id), include_data=True
        )
        if result is None:
            raise HTTPException(404, "Document not found.")
        return Response(
            result["data"],
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="source.pdf"'},
        )

    web = Path(__file__).parent / "web"
    if web.exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="workspace")
    return app


app = create_app()
