"""
app.py — Streamlit UI for the TechM RFP Automation System
Run: streamlit run app.py
"""

import os, re, time, tempfile
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="TechM RFP Automation",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: linear-gradient(135deg, #080c18 0%, #0b1630 55%, #150820 100%); color: #e2e8f0; }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b1630 0%, #150820 100%);
    border-right: 1px solid rgba(200,0,43,0.25);
}

.hero-title {
    font-size: 2.6rem; font-weight: 700; text-align: center;
    background: linear-gradient(90deg, #ff4d6d, #c8002b, #4361ee);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero-sub { text-align: center; color: #7890b0; font-size: 1rem; margin-top: 2px; }

.card {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(200,0,43,0.2);
    border-radius: 12px; padding: 18px; margin: 8px 0; backdrop-filter: blur(8px);
}
.card-blue { border-color: rgba(96,180,255,0.25) !important; }

.agent-card { border-radius: 10px; padding: 12px 16px; margin: 5px 0;
    border-left: 4px solid; background: rgba(255,255,255,0.04); }
.agent-analyst   { border-color: #60b4ff; }
.agent-architect { border-color: #c8002b; }
.agent-pricing   { border-color: #ffd700; }
.agent-writer    { border-color: #4caf86; }

.stButton > button {
    background: linear-gradient(135deg, #c8002b, #8b0020);
    color: white; border: none; border-radius: 8px;
    padding: 12px 28px; font-weight: 600; font-size: 1rem;
    transition: all 0.3s ease; width: 100%;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #ff1a45, #c8002b);
    transform: translateY(-2px); box-shadow: 0 8px 25px rgba(200,0,43,0.4);
}
.stDownloadButton > button {
    background: linear-gradient(135deg, #003578, #001f4d);
    color: white; border: 1px solid rgba(96,180,255,0.3);
    border-radius: 8px; font-weight: 600; width: 100%;
}
[data-testid="stFileUploader"] {
    border: 2px dashed rgba(200,0,43,0.35); border-radius: 12px;
    background: rgba(255,255,255,0.02); padding: 8px;
}
.stTabs [data-baseweb="tab-list"] { background: rgba(255,255,255,0.05); border-radius: 10px; padding: 4px; }
.stTabs [data-baseweb="tab"] { color: #7890b0; font-weight: 500; }
.stTabs [aria-selected="true"] { background: rgba(200,0,43,0.22) !important; color: #ff6b8a !important; }
.stTextArea textarea { background: rgba(255,255,255,0.06) !important; color: #e2e8f0 !important;
    border: 1px solid rgba(200,0,43,0.3) !important; border-radius: 8px !important; }
[data-testid="metric-container"] { background: rgba(255,255,255,0.05);
    border: 1px solid rgba(200,0,43,0.2); border-radius: 10px; padding: 10px; }
hr { border-color: rgba(200,0,43,0.18) !important; }
</style>
""", unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────────────────────
for k, v in {
    "outputs": None, "rfp_text": "", "client_name": "",
    "running": False, "edited_proposal": "", "kb_loaded": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")

    groq_key = st.text_input(
        "Groq API Key",
        value=os.getenv("GROQ_API_KEY", ""),
        type="password",
        help="Free key at console.groq.com",
    )
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key

    model_choice = st.selectbox(
        "LLM Model",
        ["llama3-70b-8192", "llama3-8b-8192", "mixtral-8x7b-32768"],
        index=0,
        help="llama3-70b gives best quality; llama3-8b is faster",
    )

    st.markdown("---")
    st.markdown("### 🧠 Knowledge Base")
    kb_status = st.empty()

    if st.button("📂 Load Past Proposals", key="load_kb"):
        with st.spinner("Indexing…"):
            try:
                from brain import load_knowledge_base
                kb = load_knowledge_base()
                n = kb.count()
                st.session_state.kb_loaded = True
                kb_status.success(f"✅ {n} chunks indexed")
            except Exception as e:
                kb_status.error(f"❌ {e}")
    else:
        if st.session_state.kb_loaded:
            kb_status.success("KB Ready")
        else:
            kb_status.info("Not loaded yet — click to index")

    st.markdown("### 📁 Add Past Proposal to KB")
    past_pdf = st.file_uploader("Upload past proposal PDF", type=["pdf"], key="past_pdf")
    if past_pdf and st.button("➕ Add to KB", key="add_kb"):
        with st.spinner("Processing…"):
            try:
                from ingestor import process_to_markdown
                from brain import RFPKnowledgeBase
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(past_pdf.read()); tmp_path = tmp.name
                md_path = process_to_markdown(tmp_path, "data/markdown")
                kb = RFPKnowledgeBase()
                kb.add_document(md_path)
                os.unlink(tmp_path)
                st.success(f"✅ Added '{past_pdf.name}'")
            except Exception as e:
                st.error(f"❌ {e}")

    st.markdown("---")
    st.markdown("""
    <div style='color:#556677;font-size:0.75rem;text-align:center;'>
    🤖 <b>Groq + CrewAI</b> · Llama 3<br>
    🗄️ <b>ChromaDB</b> · pdfplumber<br>
    Built for Tech Mahindra
    </div>""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<h1 class="hero-title">⚡ RFP Automation System</h1>', unsafe_allow_html=True)
st.markdown('<p class="hero-sub">AI-powered proposal generation · Tech Mahindra · Zero-Budget OSS Stack</p>', unsafe_allow_html=True)
st.markdown("---")

# ── Agent Status Strip ─────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
for col, name, css, desc in [
    (c1, "🔍 Analyst",    "agent-analyst",   "Extracts all requirements & risks"),
    (c2, "🏗️ Architect",  "agent-architect", "Designs solution + Mermaid diagram"),
    (c3, "💰 Pricing",    "agent-pricing",   "Rate card & commercial summary"),
    (c4, "✍️ Writer",     "agent-writer",    "Polished client-ready narrative"),
]:
    with col:
        st.markdown(f"""
        <div class="agent-card {css}">
            <b>{name}</b><br>
            <span style='font-size:0.78rem;color:#7890b0'>{desc}</span>
        </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── Main Tabs ──────────────────────────────────────────────────────────────────
tab_upload, tab_results, tab_export = st.tabs(["📤 Upload & Generate", "📋 Review & Edit", "📥 Export"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Upload & Generate
# ═══════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.markdown("### Step 1 — Upload RFP Document")
    left, right = st.columns([1.2, 1])

    with left:
        client_name = st.text_input(
            "Client / Company Name",
            value=st.session_state.client_name or "",
            placeholder="e.g. HDFC Bank, Infosys, Reliance…",
        )
        uploaded_file = st.file_uploader(
            "Drop your RFP PDF here",
            type=["pdf"],
            key="rfp_upload",
            help="Any PDF — text, tables, and structure are extracted automatically",
        )
        with st.expander("✏️ Or paste RFP text directly"):
            manual_text = st.text_area(
                "Paste RFP content",
                height=200,
                placeholder="Paste full RFP text if you don't have a PDF…",
                key="manual_rfp",
            )

    with right:
        st.markdown("""
        <div class="card">
        <b>🚀 What happens when you click Generate?</b><br><br>
        <ol style='color:#9aaabb;font-size:0.88rem;line-height:2.1'>
        <li>PDF is parsed to structured Markdown</li>
        <li>Knowledge Base is queried for past proposals</li>
        <li>4 AI agents run in sequence (≈ 2–4 min)</li>
        <li>You review & edit the draft</li>
        <li>Export to Word + PowerPoint in one click</li>
        </ol>
        </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class="card card-blue">
        <b>💡 Tips for best results</b><br><br>
        <ul style='color:#9aaabb;font-size:0.83rem;line-height:1.9'>
        <li>Upload past TechM proposals to the KB first</li>
        <li>Use the client's actual company name</li>
        <li>Larger, detailed RFPs produce richer proposals</li>
        <li>You can edit every section before exporting</li>
        </ul>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    gen_col, _ = st.columns([1, 2])
    with gen_col:
        generate_btn = st.button("🤖 Generate Proposal", key="generate", disabled=st.session_state.running)

    if generate_btn:
        if not os.environ.get("GROQ_API_KEY"):
            st.error("❌ Please enter your Groq API Key in the sidebar first.")
        elif not uploaded_file and not manual_text.strip():
            st.error("❌ Please upload a PDF or paste the RFP text.")
        else:
            st.session_state.client_name = client_name or "Client"
            st.session_state.running = True
            progress = st.progress(0, text="📄 Extracting RFP content…")
            status   = st.empty()

            try:
                # Step 1: Extract text
                if uploaded_file:
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp.write(uploaded_file.read()); tmp_path = tmp.name
                    from ingestor import extract_text_only
                    rfp_text = extract_text_only(tmp_path)
                    os.unlink(tmp_path)
                else:
                    rfp_text = manual_text.strip()

                st.session_state.rfp_text = rfp_text
                progress.progress(20, text="✅ RFP parsed — querying knowledge base…")

                # Step 2: KB Query
                kb_context = ""
                try:
                    from brain import RFPKnowledgeBase
                    kb = RFPKnowledgeBase()
                    if kb.count() > 0:
                        kb_context = kb.query(rfp_text[:600])
                        status.info(f"📚 KB has {kb.count()} chunks — context injected into Architect agent")
                    else:
                        status.warning("ℹ️ KB is empty. Upload past proposals via the sidebar for richer results.")
                except Exception as e:
                    status.warning(f"⚠️ KB query failed (continuing without it): {e}")

                progress.progress(35, text="🤖 Running 4-agent AI crew… (2–4 min)")

                # Step 3: Run Crew
                with st.spinner("🧠 AI Agents are working… Analyst → Architect → Pricing → Writer"):
                    from agents import run_crew
                    outputs = run_crew(rfp_text, kb_context, model=model_choice)

                progress.progress(95, text="💾 Saving results…")
                st.session_state.outputs = outputs
                st.session_state.edited_proposal = outputs.get("proposal", "")
                progress.progress(100, text="✅ Complete!")
                st.session_state.running = False
                st.success("🎉 Proposal generated! Switch to the **Review & Edit** tab.")
                st.balloons()

            except Exception as e:
                st.session_state.running = False
                progress.empty()
                st.error(f"❌ Generation failed: {e}")
                with st.expander("Show error details"):
                    st.code(str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Review & Edit (Human-in-the-Loop)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_results:
    if not st.session_state.outputs:
        st.info("💡 Generate a proposal first using the **Upload & Generate** tab.")
    else:
        outputs = st.session_state.outputs
        st.markdown(f"### 📋 Proposal for **{st.session_state.client_name}**")

        # Metrics
        proposal_text = outputs.get("proposal", "")
        word_count  = len(proposal_text.split())
        has_mermaid = bool(re.search(r"```mermaid", proposal_text, re.IGNORECASE))
        has_table   = "|" in proposal_text

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📝 Word Count",   f"{word_count:,}")
        m2.metric("📊 Has Diagram",  "Yes ✅" if has_mermaid else "No ❌")
        m3.metric("📈 Has Tables",   "Yes ✅" if has_table else "No ❌")
        m4.metric("🤖 Agents Run",   "4 / 4")

        st.markdown("---")

        r1, r2, r3, r4 = st.tabs(["🔍 Analysis", "🏗️ Architecture", "💰 Pricing", "✍️ Full Proposal"])

        with r1:
            st.markdown(outputs.get("analysis", "_No output_"))

        with r2:
            arch = outputs.get("architecture", "_No output_")
            st.markdown(arch)
            mermaid_match = re.search(r"```mermaid\s*([\s\S]+?)```", arch, re.IGNORECASE)
            if mermaid_match:
                import base64, zlib
                code = mermaid_match.group(1).strip()
                enc  = base64.urlsafe_b64encode(zlib.compress(code.encode(), 9)).decode()
                url  = f"https://kroki.io/mermaid/png/{enc}"
                st.markdown("---")
                st.markdown("**🖼️ Architecture Diagram (live render via Kroki.io)**")
                st.image(url, caption="Solution Architecture", use_container_width=True)

        with r3:
            st.markdown(outputs.get("pricing", "_No output_"))

        with r4:
            st.markdown("#### ✏️ Human-in-the-Loop — Edit before exporting")
            st.caption("Freely edit the proposal below. Your edits are used when you export.")
            edited = st.text_area(
                "Edit Proposal",
                value=st.session_state.edited_proposal,
                height=620,
                key="proposal_editor",
                label_visibility="collapsed",
            )
            col_save, col_preview = st.columns([1, 3])
            with col_save:
                if st.button("💾 Save Edits", key="save_edits"):
                    st.session_state.edited_proposal = edited
                    st.session_state.outputs["proposal"] = edited
                    st.success("✅ Saved — export from the Export tab.")
            with col_preview:
                if st.button("👁️ Preview as Markdown", key="preview_md"):
                    st.markdown("---")
                    st.markdown(edited)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Export
# ═══════════════════════════════════════════════════════════════════════════════
with tab_export:
    if not st.session_state.outputs:
        st.info("💡 Generate and review a proposal first.")
    else:
        st.markdown("### 📥 Export Your Proposal")
        st.markdown(f"Exporting proposal for **{st.session_state.client_name}**")
        st.markdown("---")

        col_w, col_p = st.columns(2)

        with col_w:
            st.markdown("""
            <div class="card">
            <h4>📄 Word Document (.docx)</h4>
            <p style='color:#7890b0;font-size:0.88rem'>
            Structured doc with TechM branding, all sections, tables,
            and the architecture diagram embedded automatically.</p>
            </div>""", unsafe_allow_html=True)

            if st.button("📄 Generate Word Document", key="gen_word"):
                with st.spinner("Creating Word document…"):
                    try:
                        from exporter import export_to_word
                        path = export_to_word(st.session_state.outputs, st.session_state.client_name)
                        with open(path, "rb") as f:
                            st.download_button(
                                "⬇️ Download .docx", data=f.read(),
                                file_name=os.path.basename(path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key="dl_word",
                            )
                        st.success(f"✅ Ready: {os.path.basename(path)}")
                    except Exception as e:
                        st.error(f"❌ {e}")
                        with st.expander("Error details"):
                            st.code(str(e))

        with col_p:
            st.markdown("""
            <div class="card">
            <h4>📊 PowerPoint Deck (.pptx)</h4>
            <p style='color:#7890b0;font-size:0.88rem'>
            Multi-slide deck: cover, agenda, content slides,
            architecture diagram, rate card table, and thank-you slide.</p>
            </div>""", unsafe_allow_html=True)

            if st.button("📊 Generate PowerPoint", key="gen_ppt"):
                with st.spinner("Creating PowerPoint deck…"):
                    try:
                        from exporter import export_to_ppt
                        path = export_to_ppt(st.session_state.outputs, st.session_state.client_name)
                        with open(path, "rb") as f:
                            st.download_button(
                                "⬇️ Download .pptx", data=f.read(),
                                file_name=os.path.basename(path),
                                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                key="dl_ppt",
                            )
                        st.success(f"✅ Ready: {os.path.basename(path)}")
                    except Exception as e:
                        st.error(f"❌ {e}")
                        with st.expander("Error details"):
                            st.code(str(e))

        st.markdown("---")
        st.markdown("### 📋 Raw Markdown (copy anywhere)")
        st.caption("Paste into Notion, Confluence, email, or any editor.")
        st.code(st.session_state.outputs.get("proposal", ""), language="markdown")
