"""
agents.py — RFP Proposal Generator (Direct API approach)

Uses langchain_groq directly instead of CrewAI orchestration.
CrewAI makes 5-10+ internal API calls per agent task, which blows through
Groq free-tier TPM limits (12k-20k/min). This implementation makes exactly
4 sequential calls with enforced delays to stay within limits.
"""

import os
import sys
import time
import random

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

# ── Groq model IDs (current as of April 2025) ────────────────────────────────
# Free-tier TPM limits:
#   llama-3.1-8b-instant    : ~20,000 TPM  <-- recommended for free tier
#   llama-3.3-70b-versatile : ~12,000 TPM  <-- higher quality, needs paid tier
#   gemma2-9b-it            : ~15,000 TPM
GROQ_MODEL_IDS = {
    "llama-3.1-8b-instant":    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile": "llama-3.3-70b-versatile",
    "gemma2-9b-it":            "gemma2-9b-it",
    # Legacy aliases
    "llama3-70b-8192":    "llama-3.3-70b-versatile",
    "llama3-8b-8192":     "llama-3.1-8b-instant",
    "mixtral-8x7b-32768": "gemma2-9b-it",
}

DEFAULT_MODEL = "llama-3.1-8b-instant"

# ── Delay between agent calls (seconds) ──────────────────────────────────────
# 20s gap ensures we stay well within free-tier TPM windows.
# Each call uses ~2000-2500 tokens. 3 calls in 60s = ~7500 tokens < 20k limit.
INTER_AGENT_DELAY = 20


# ── Agent System Prompts ──────────────────────────────────────────────────────

ANALYST_SYSTEM = """You are a Senior RFP Requirements Analyst at Tech Mahindra with 15 years
of experience analysing 500+ RFPs across Banking, Healthcare, Retail, and Manufacturing.

Your job: read the provided RFP text and produce a structured analysis in Markdown.

Output exactly these sections (use ## headers):
## 1. Client Background
## 2. Key Requirements (functional & non-functional)
## 3. Scope of Work
## 4. Evaluation Criteria
## 5. Deadlines & Milestones
## 6. Risks & Constraints
## 7. Business Pain Points
## 8. Compliance & Governance

Be specific and extract real details from the RFP. Use bullet points."""


ARCHITECT_SYSTEM = """You are the Principal Solution Architect at Tech Mahindra with 20 years
designing enterprise transformation programmes. Expert in cloud (AWS/Azure/GCP), AI/ML,
SAP, microservices, and digital engineering.

Your job: design the complete technical solution and produce a structured response in Markdown.

Output exactly these sections (use ## headers):
## 1. Solution Overview
## 2. Technology Stack
## 3. System Architecture
   MANDATORY: Include one Mermaid.js flowchart in a ```mermaid code block.
   Example format:
   ```mermaid
   flowchart TD
       A[Client Systems] --> B[Integration Layer]
       B --> C[Core Platform]
       C --> D[Analytics & AI]
       D --> E[Reporting & Dashboards]
   ```
## 4. Team Structure (table: Role | Count | Location)
## 5. Operating Model (onshore/offshore/nearshore % split)
## 6. Delivery Roadmap (Phase 1/2/3 with durations and key milestones)"""


PRICING_SYSTEM = """You are the Pricing & Commercials Specialist at Tech Mahindra.
You know market rates: offshore $25-35/hr, nearshore $45-65/hr, onshore $80-120/hr.

Your job: create the full commercial model in Markdown.

Output exactly these sections (use ## headers and Markdown tables):
## 1. Rate Card
| Role | Count | Location | Hrs/Month | Rate/hr | Monthly Cost |
|------|-------|----------|-----------|---------|--------------|

## 2. Phase Cost Breakdown
| Phase | Duration | Team Size | Total Cost |
|-------|----------|-----------|------------|

## 3. Total Engagement Cost
(provide a min-max range)

## 4. Payment Milestones
| Milestone | % | Trigger |
|-----------|---|---------|

## 5. ROI Justification
(3-4 bullet points on tangible value delivered)

## 6. Optional Add-ons
(2-3 premium services with pricing)

All numbers must be realistic and internally consistent."""


WRITER_SYSTEM = """You are the Principal Proposal Writer at Tech Mahindra, responsible for
winning $2B+ in contracts. You craft compelling, client-centric proposals that convert.

Your job: write the complete, polished proposal in Markdown.

Use this EXACT structure:
# Tech Mahindra – Solution Proposal for [CLIENT NAME]

## 1. Executive Summary
(2-3 paragraphs: why TechM, what we propose, key benefits)

## 2. Understanding Your Challenge
(reframe the client's pain points as a narrative)

## 3. Our Proposed Solution
(describe the solution in business terms)

## 4. Solution Architecture
(PASTE THE MERMAID DIAGRAM from the architect here, inside a ```mermaid block)

## 5. Team Structure & Operating Model
(summarise team and onshore/offshore model)

## 6. Delivery Roadmap
(phase-by-phase plan with milestones)

## 7. Commercial Summary
(summarise pricing — include the rate table and total cost range)

## 8. Why Tech Mahindra?
(3 specific, evidence-backed differentiators)

## 9. Next Steps
(3-4 concrete actions to advance the engagement)

Tone: Professional, confident, forward-looking. Minimum 1500 words. No filler sentences."""


# ── Core LLM caller with retry / backoff ─────────────────────────────────────

def _is_rate_limit(exc: Exception) -> bool:
    s = str(exc).lower()
    return any(x in s for x in [
        "rate_limit", "ratelimit", "rate limit",
        "429", "tpm", "tokens per minute", "quota"
    ])


def _call_with_retry(llm: ChatGroq, messages: list,
                     label: str = "Agent", max_retries: int = 6) -> str:
    """Call the LLM with exponential backoff on rate-limit errors."""
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[{label}] Calling Groq API (attempt {attempt})...")
            response = llm.invoke(messages)
            content = response.content
            print(f"[{label}] Done. {len(content)} chars returned.")
            return content
        except Exception as e:
            if _is_rate_limit(e) and attempt < max_retries:
                wait = 30 * (2 ** (attempt - 1)) + random.uniform(3, 10)
                print(
                    f"[{label}] Rate limit hit (attempt {attempt}/{max_retries}). "
                    f"Waiting {wait:.0f}s..."
                )
                time.sleep(wait)
            else:
                raise


def _make_llm(model: str, groq_api_key: str) -> ChatGroq:
    """Build a ChatGroq instance from the model name."""
    api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to your .env file or the sidebar."
        )
    groq_id = GROQ_MODEL_IDS.get(model, model)
    return ChatGroq(
        model=groq_id,
        groq_api_key=api_key,
        temperature=0.2,
        max_tokens=1800,    # controlled output size to respect TPM limits
    )


# ── Main Run Function ─────────────────────────────────────────────────────────

def run_crew(rfp_content: str, kb_context: str = "",
             model: str = DEFAULT_MODEL, groq_api_key: str = "") -> dict:
    """
    Run the 4-agent pipeline using direct Groq API calls.
    Each call is separated by INTER_AGENT_DELAY seconds to respect
    Groq free-tier TPM (tokens per minute) limits.

    Returns dict: {analysis, architecture, pricing, proposal}
    """
    llm = _make_llm(model, groq_api_key)

    # Truncate RFP to a safe size (~600 tokens input for analyst)
    rfp_preview = rfp_content[:2500]

    # ── Step 1: Requirements Analyst ─────────────────────────────────────────
    print("[Pipeline] Step 1/4 — Requirements Analyst")
    analysis = _call_with_retry(
        llm,
        [
            SystemMessage(content=ANALYST_SYSTEM),
            HumanMessage(content=f"Please analyse this RFP document:\n\n{rfp_preview}"),
        ],
        label="Analyst",
    )

    # Pause to avoid TPM overflow
    print(f"[Pipeline] Waiting {INTER_AGENT_DELAY}s before next agent...")
    time.sleep(INTER_AGENT_DELAY)

    # ── Step 2: Solution Architect ────────────────────────────────────────────
    print("[Pipeline] Step 2/4 — Solution Architect")
    kb_section = ""
    if kb_context and "No relevant" not in kb_context:
        kb_section = f"\n\nRelevant past proposals from knowledge base:\n{kb_context[:600]}"

    architecture = _call_with_retry(
        llm,
        [
            SystemMessage(content=ARCHITECT_SYSTEM),
            HumanMessage(
                content=(
                    f"Based on this requirements analysis:\n\n{analysis[:1400]}"
                    f"{kb_section}"
                    f"\n\nDesign the complete solution architecture."
                )
            ),
        ],
        label="Architect",
    )

    print(f"[Pipeline] Waiting {INTER_AGENT_DELAY}s before next agent...")
    time.sleep(INTER_AGENT_DELAY)

    # ── Step 3: Pricing Specialist ────────────────────────────────────────────
    print("[Pipeline] Step 3/4 — Pricing Specialist")
    pricing = _call_with_retry(
        llm,
        [
            SystemMessage(content=PRICING_SYSTEM),
            HumanMessage(
                content=(
                    f"Based on this solution design:\n\n{architecture[:1400]}"
                    f"\n\nCreate the full commercial model."
                )
            ),
        ],
        label="Pricing",
    )

    print(f"[Pipeline] Waiting {INTER_AGENT_DELAY}s before next agent...")
    time.sleep(INTER_AGENT_DELAY)

    # ── Step 4: Proposal Writer ───────────────────────────────────────────────
    print("[Pipeline] Step 4/4 — Proposal Writer")
    proposal = _call_with_retry(
        llm,
        [
            SystemMessage(content=WRITER_SYSTEM),
            HumanMessage(
                content=(
                    "Write the complete polished proposal using these inputs:\n\n"
                    f"--- REQUIREMENTS ANALYSIS ---\n{analysis[:700]}\n\n"
                    f"--- SOLUTION ARCHITECTURE ---\n{architecture[:700]}\n\n"
                    f"--- COMMERCIAL MODEL ---\n{pricing[:700]}\n\n"
                    "Now write the full, detailed proposal. "
                    "Embed the Mermaid diagram from the architecture section. "
                    "Minimum 1500 words."
                )
            ),
        ],
        label="Writer",
    )

    print("[Pipeline] All 4 agents complete.")
    return {
        "analysis":     analysis,
        "architecture": architecture,
        "pricing":      pricing,
        "proposal":     proposal,
    }


# ── Compatibility shims (kept for any direct imports) ─────────────────────────

def get_llm(model: str = DEFAULT_MODEL, groq_api_key: str = "") -> ChatGroq:
    return _make_llm(model, groq_api_key)


def build_analyst(llm):    return None   # not used in direct-call mode
def build_architect(llm, kb_context=""): return None
def build_pricing_agent(llm): return None
def build_writer(llm):     return None