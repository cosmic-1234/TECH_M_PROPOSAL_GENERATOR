"""
server.py - FastAPI backend for TechM RFP Automation System
Run: python server.py
"""
import os, sys, json, asyncio, tempfile, threading
from pathlib import Path
from datetime import datetime
from typing import Optional

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Force UTF-8 in all spawned threads/subprocesses
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="TechM RFP Automation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store ───────────────────────────────────────────────────────
jobs: dict[str, dict] = {}

# ── Models ────────────────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    rfp_text: str
    client_name: str = "Client"
    model: str = "llama3-70b-8192"
    groq_api_key: Optional[str] = None

class ExportRequest(BaseModel):
    job_id: str
    client_name: str = "Client"
    format: str = "word"  # "word" or "ppt"


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ── KB Endpoints ──────────────────────────────────────────────────────────────
@app.get("/api/kb/status")
def kb_status():
    try:
        from brain import RFPKnowledgeBase
        kb = RFPKnowledgeBase()
        sources = kb.list_sources()
        return {"count": kb.count(), "sources": sources}
    except Exception as e:
        return {"count": 0, "sources": [], "error": str(e)}


@app.post("/api/kb/load")
def kb_load():
    try:
        from brain import load_knowledge_base
        kb = load_knowledge_base()
        return {"count": kb.count(), "sources": kb.list_sources(), "message": "Knowledge base loaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kb/upload")
async def kb_upload(file: UploadFile = File(...)):
    try:
        from ingestor import process_to_markdown
        from brain import RFPKnowledgeBase

        suffix = Path(file.filename).suffix.lower()
        if suffix not in [".pdf", ".txt", ".md"]:
            raise HTTPException(status_code=400, detail="Only PDF, TXT, and MD files supported")

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        os.makedirs("data/markdown", exist_ok=True)
        if suffix == ".pdf":
            md_path = process_to_markdown(tmp_path, "data/markdown")
        else:
            md_path = os.path.join("data/markdown", Path(file.filename).stem + ".md")
            with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            with open(md_path, "w", encoding="utf-8") as out:
                out.write(content)

        kb = RFPKnowledgeBase()
        kb.add_document(md_path)
        os.unlink(tmp_path)

        return {"message": f"'{file.filename}' added successfully", "chunks": kb.count(), "sources": kb.list_sources()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Generate Endpoint ─────────────────────────────────────────────────────────
def _run_crew_thread(job_id: str, rfp_text: str, kb_context: str, model: str, groq_key: str):
    """Run the 4-agent pipeline in a background thread and update job status in real-time."""
    import time, random

    def set_stage(stage: str):
        jobs[job_id]["stage"] = stage
        print(f"[Job {job_id}] Stage: {stage}")

    def is_rate_limit(e: Exception) -> bool:
        s = str(e).lower()
        return any(x in s for x in ["rate_limit", "ratelimit", "rate limit", "429", "tpm", "tokens per minute"])

    def call_with_backoff(fn, label, max_retries=6):
        for attempt in range(1, max_retries + 1):
            try:
                return fn()
            except Exception as e:
                if is_rate_limit(e) and attempt < max_retries:
                    wait = 30 * (2 ** (attempt - 1)) + random.uniform(3, 10)
                    print(f"[{label}] Rate limit (attempt {attempt}). Waiting {wait:.0f}s...")
                    jobs[job_id]["stage"] = f"{label.lower()}_retry_{attempt}"
                    time.sleep(wait)
                else:
                    raise

    try:
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key

        from agents import _make_llm, _call_with_retry, INTER_AGENT_DELAY
        from agents import ANALYST_SYSTEM, ARCHITECT_SYSTEM, PRICING_SYSTEM, WRITER_SYSTEM
        from langchain_core.messages import SystemMessage, HumanMessage

        jobs[job_id]["status"] = "running"
        llm = _make_llm(model, groq_key)
        rfp_preview = rfp_text[:2500]

        # ── Agent 1: Analyst ──────────────────────────────────────────────────
        set_stage("analyst")
        analysis = call_with_backoff(
            lambda: _call_with_retry(llm, [
                SystemMessage(content=ANALYST_SYSTEM),
                HumanMessage(content=f"Please analyse this RFP document:\n\n{rfp_preview}"),
            ], label="Analyst"),
            label="Analyst",
        )
        time.sleep(INTER_AGENT_DELAY)

        # ── Agent 2: Architect ────────────────────────────────────────────────
        set_stage("architect")
        kb_section = ""
        if kb_context and "No relevant" not in kb_context:
            kb_section = f"\n\nRelevant past proposals:\n{kb_context[:600]}"

        architecture = call_with_backoff(
            lambda: _call_with_retry(llm, [
                SystemMessage(content=ARCHITECT_SYSTEM),
                HumanMessage(content=(
                    f"Based on this requirements analysis:\n\n{analysis[:1400]}"
                    f"{kb_section}"
                    f"\n\nDesign the complete solution architecture."
                )),
            ], label="Architect"),
            label="Architect",
        )
        time.sleep(INTER_AGENT_DELAY)

        # ── Agent 3: Pricing ──────────────────────────────────────────────────
        set_stage("pricing")
        pricing = call_with_backoff(
            lambda: _call_with_retry(llm, [
                SystemMessage(content=PRICING_SYSTEM),
                HumanMessage(content=(
                    f"Based on this solution design:\n\n{architecture[:1400]}"
                    f"\n\nCreate the full commercial model."
                )),
            ], label="Pricing"),
            label="Pricing",
        )
        time.sleep(INTER_AGENT_DELAY)

        # ── Agent 4: Writer ───────────────────────────────────────────────────
        set_stage("writer")
        proposal = call_with_backoff(
            lambda: _call_with_retry(llm, [
                SystemMessage(content=WRITER_SYSTEM),
                HumanMessage(content=(
                    "Write the complete polished proposal using these inputs:\n\n"
                    f"--- REQUIREMENTS ANALYSIS ---\n{analysis[:700]}\n\n"
                    f"--- SOLUTION ARCHITECTURE ---\n{architecture[:700]}\n\n"
                    f"--- COMMERCIAL MODEL ---\n{pricing[:700]}\n\n"
                    "Embed the Mermaid diagram. Minimum 1500 words."
                )),
            ], label="Writer"),
            label="Writer",
        )

        jobs[job_id]["status"] = "done"
        jobs[job_id]["stage"] = "complete"
        jobs[job_id]["outputs"] = {
            "analysis":     analysis,
            "architecture": architecture,
            "pricing":      pricing,
            "proposal":     proposal,
        }
        jobs[job_id]["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        err_str = str(e)
        if is_rate_limit(e):
            jobs[job_id]["error"] = (
                "Groq free-tier rate limit reached. The system will retry automatically "
                "on next run. Please wait 60 seconds then click Generate again, "
                "or select 'Llama 3.1 8B Instant' in the sidebar (higher rate limits)."
            )
        else:
            jobs[job_id]["error"] = err_str
        jobs[job_id]["status"] = "error"




@app.post("/api/generate")
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    if not req.rfp_text.strip():
        raise HTTPException(status_code=400, detail="RFP text cannot be empty")

    groq_key = req.groq_api_key or os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        raise HTTPException(status_code=400, detail="GROQ_API_KEY not configured")

    # Query KB
    kb_context = ""
    try:
        from brain import RFPKnowledgeBase
        kb = RFPKnowledgeBase()
        if kb.count() > 0:
            kb_context = kb.query(req.rfp_text[:600])
    except Exception:
        pass

    # Create job
    job_id = f"job_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    jobs[job_id] = {
        "id": job_id,
        "job_id": job_id,     # also expose as job_id for frontend restore
        "status": "queued",
        "stage": "queued",
        "client_name": req.client_name,
        "outputs": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
    }

    t = threading.Thread(
        target=_run_crew_thread,
        args=(job_id, req.rfp_text, kb_context, req.model, groq_key),
        daemon=True,
    )
    t.start()

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs")
def list_jobs():
    return list(jobs.values())


@app.get("/api/jobs/latest")
def get_latest_job():
    """Return the most recently completed job — used for page-refresh recovery."""
    done_jobs = [j for j in jobs.values() if j.get("status") == "done"]
    if not done_jobs:
        raise HTTPException(status_code=404, detail="No completed jobs found")
    latest = max(done_jobs, key=lambda j: j.get("completed_at", ""))
    return latest


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


# ── Upload RFP PDF ─────────────────────────────────────────────────────────────
@app.post("/api/upload-rfp")
async def upload_rfp(file: UploadFile = File(...)):
    try:
        from ingestor import extract_text_only
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
        text = extract_text_only(tmp_path)
        os.unlink(tmp_path)
        return {"text": text, "length": len(text), "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Export Endpoints ──────────────────────────────────────────────────────────
@app.post("/api/export/word")
def export_word(req: ExportRequest):
    job = jobs.get(req.job_id)
    if not job or job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job not complete or not found")
    try:
        from exporter import export_to_word
        path = export_to_word(job["outputs"], client_name=req.client_name)
        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=os.path.basename(path),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export/ppt")
def export_ppt(req: ExportRequest):
    job = jobs.get(req.job_id)
    if not job or job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job not complete or not found")
    try:
        from exporter import export_to_ppt
        path = export_to_ppt(job["outputs"], client_name=req.client_name)
        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=os.path.basename(path),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Serve built React app ─────────────────────────────────────────────────────
dist_path = Path("frontend/dist")
if dist_path.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_path / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        index = dist_path / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse({"status": "API only mode"})


if __name__ == "__main__":
    os.makedirs("data/markdown", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    print("TechM RFP Automation Server starting on http://localhost:8000")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
