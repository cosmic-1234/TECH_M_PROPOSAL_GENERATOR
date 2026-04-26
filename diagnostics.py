"""
diagnostics.py — Full system health check for TechM RFP Automation
Run: python diagnostics.py
"""
import os, sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

results = []

def check(name, fn):
    try:
        msg = fn()
        results.append((PASS, name, msg))
        print(f"{PASS} {name}: {msg}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"{FAIL} {name}: {e}")

# ── 1. Groq API Key ──────────────────────────────────────────────────────────
def test_groq_key():
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise ValueError("GROQ_API_KEY not set in .env")
    if not key.startswith("gsk_"):
        raise ValueError(f"Key looks invalid (should start with gsk_): {key[:12]}...")
    return f"Key loaded: {key[:12]}...{key[-4:]}"

check("Groq API Key", test_groq_key)

# ── 2. Package imports ───────────────────────────────────────────────────────
def test_imports():
    import crewai, chromadb, pdfplumber, fitz, streamlit, fastapi
    return f"crewai={crewai.__version__}, chromadb={chromadb.__version__}"

check("Package Imports", test_imports)

# ── 3. Groq LLM connection ───────────────────────────────────────────────────
def test_groq_llm():
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama3-8b-8192", groq_api_key=os.getenv("GROQ_API_KEY"), temperature=0, max_tokens=64)
    resp = llm.invoke("Say PONG in one word only.")
    content = resp.content if hasattr(resp, 'content') else str(resp)
    if not content.strip():
        raise ValueError("Empty response from Groq")
    return f"Response: '{content.strip()[:40]}'"

check("Groq LLM Connection", test_groq_llm)

# ── 4. ChromaDB ──────────────────────────────────────────────────────────────
def test_chromadb():
    from brain import RFPKnowledgeBase
    kb = RFPKnowledgeBase()
    count = kb.count()
    sources = kb.list_sources()
    return f"{count} chunks, {len(sources)} sources: {sources[:3]}"

check("ChromaDB Knowledge Base", test_chromadb)

# ── 5. ChromaDB write/read ───────────────────────────────────────────────────
def test_chromadb_rw():
    from brain import RFPKnowledgeBase
    kb = RFPKnowledgeBase()
    kb.add_raw_text("Tech Mahindra is a leading IT services company specialising in cloud, AI, and digital transformation.", "diag_test")
    result = kb.query("IT services company", n_results=1)
    if not result or "No relevant" in result:
        raise ValueError("Query returned no results after write")
    return f"Write+Query OK: '{result[:60]}...'"

check("ChromaDB Read/Write", test_chromadb_rw)

# ── 6. PDF parser ────────────────────────────────────────────────────────────
def test_pdf():
    from ingestor import extract_text_only
    import tempfile, fitz
    # Create a tiny PDF in memory
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "TechM RFP Test Document\nRequirements: Cloud Migration\nBudget: $500,000")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        doc.save(tmp.name); tmp_path = tmp.name
    text = extract_text_only(tmp_path)
    os.unlink(tmp_path)
    if len(text) < 10:
        raise ValueError("Extracted text is too short")
    return f"Extracted {len(text)} chars OK"

check("PDF Parser", test_pdf)

# ── 7. Exporter ──────────────────────────────────────────────────────────────
def test_exporter():
    from exporter import export_to_word, export_to_ppt
    sample = {
        "proposal": "# Tech Mahindra – Solution Proposal\n\n## Executive Summary\nThis is a test proposal.\n\n## Architecture\n\n```mermaid\nflowchart TD\n    A[Client] --> B[TechM Platform]\n    B --> C[AI Engine]\n```\n\n## Commercials\n| Role | Rate |\n|------|------|\n| Architect | $120/hr |\n",
        "analysis": "## Requirements\n- Cloud migration\n- 6-month delivery",
        "architecture": "## Architecture\nCloud-native solution.",
        "pricing": "## Rate Card\n| Role | Rate |\n|------|------|\n| Architect | $120/hr |",
    }
    w = export_to_word(sample, "DiagTest")
    p = export_to_ppt(sample, "DiagTest")
    if not os.path.exists(w) or not os.path.exists(p):
        raise ValueError("Output files not created")
    return f"Word: {os.path.basename(w)}, PPT: {os.path.basename(p)}"

check("Word/PPT Exporter", test_exporter)

# ── 8. FastAPI server ────────────────────────────────────────────────────────
def test_fastapi():
    import requests as req
    try:
        r = req.get("http://localhost:8000/api/health", timeout=3)
        if r.status_code == 200:
            return f"Server online: {r.json()}"
        raise ValueError(f"Status {r.status_code}")
    except req.exceptions.ConnectionError:
        raise ValueError("Server not running — start with: python server.py")

check("FastAPI Server", test_fastapi)

# ── 9. Agent build (no LLM call) ────────────────────────────────────────────
def test_agents_build():
    from agents import get_llm, build_analyst, build_architect, build_pricing_agent, build_writer, build_tasks
    llm = get_llm()
    a = build_analyst(llm)
    b = build_architect(llm)
    c = build_pricing_agent(llm)
    d = build_writer(llm)
    tasks = build_tasks("Sample RFP text for testing", a, b, c, d)
    return f"4 agents built, {len(tasks)} tasks defined"

check("Agent Construction", test_agents_build)

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "="*60)
passed = [r for r in results if r[0] == PASS]
failed = [r for r in results if r[0] == FAIL]
print(f"RESULTS: {len(passed)}/{len(results)} checks passed")
print("="*60)
if failed:
    print("\nFAILED CHECKS:")
    for _, name, msg in failed:
        print(f"  - {name}: {msg}")
    print("\nACTION REQUIRED: Fix the above before running the full system.")
else:
    print("\nAll systems operational. Ready to generate proposals.")
