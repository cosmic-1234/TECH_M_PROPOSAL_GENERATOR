import { useState, useEffect } from 'react';
import {
  FileSearch, Layers, DollarSign, PenTool,
  Database, Upload, BarChart3, Download,
  CheckCircle, AlertCircle, Clock, Loader,
  ChevronRight, BookOpen, Cpu, Globe
} from 'lucide-react';
import { api, pollJob, downloadFile } from './api.js';
import { UploadZone, Spinner, Alert, MetricCard, ProgressBar, MdRenderer } from './components.jsx';

const MODELS = [
  { value: 'llama-3.3-70b-versatile', label: 'Llama 3.3 — 70B Versatile (Best Quality)' },
  { value: 'llama-3.1-8b-instant',    label: 'Llama 3.1 — 8B Instant (Fastest)' },
  { value: 'gemma2-9b-it',            label: 'Gemma 2 — 9B IT' },
];

const AGENTS = [
  { key: 'analyst',   label: 'Requirements Analyst', role: 'Extracts all requirements & constraints', icon: FileSearch, color: 'blue' },
  { key: 'architect', label: 'Solution Architect',    role: 'Designs architecture & Mermaid diagram', icon: Layers,     color: 'red' },
  { key: 'pricing',   label: 'Commercials Specialist',role: 'Rate card & engagement cost model',     icon: DollarSign, color: 'gold' },
  { key: 'writer',    label: 'Proposal Writer',       role: 'Compiles client-ready narrative',       icon: PenTool,    color: 'green' },
];

export default function App() {
  // Read initial page from URL path (supports /review, /export, /kb, /generate)
  const VALID_PAGES = ['generate', 'review', 'export', 'kb'];
  const getPageFromUrl = () => {
    const p = window.location.pathname.replace(/^\//,'').split('/')[0];
    return VALID_PAGES.includes(p) ? p : 'generate';
  };

  const [page, setPageState]      = useState(getPageFromUrl);
  // ── Navigate: update React state + browser URL ──────────────────────────
  const setPage = (p) => {
    setPageState(p);
    const url = p === 'generate' ? '/' : `/${p}`;
    window.history.pushState({ page: p }, '', url);
  };

  // Handle browser back/forward buttons
  useEffect(() => {
    const handler = (e) => {
      const p = e.state?.page || getPageFromUrl();
      setPageState(p);
    };
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, []);

  const [groqKey, setGroqKey]     = useState(() => localStorage.getItem('groq_key') || '');
  const [model, setModel]         = useState('llama-3.1-8b-instant');
  const [kbInfo, setKbInfo]       = useState({ count: 0, sources: [] });
  const [kbLoading, setKbLoading] = useState(false);
  const [job, setJob]             = useState(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError]         = useState('');
  // ── Persist groq key ───────────────────────────────────────────────────────
  useEffect(() => { if (groqKey) localStorage.setItem('groq_key', groqKey); }, [groqKey]);
  useEffect(() => { api.kbStatus().then(setKbInfo).catch(() => {}); }, []);

  // ── Restore latest job on page load ───────────────────────────────────────
  useEffect(() => {
    const savedJobId = localStorage.getItem('latest_job_id');
    if (savedJobId) {
      // Try saved job first
      api.getJob(savedJobId)
        .then(j => { if (j && j.status === 'done') setJob(j); })
        .catch(() => {
          // Fallback: fetch whatever the server has as latest
          fetch('/api/jobs/latest').then(r => r.ok ? r.json() : null)
            .then(j => { if (j && j.status === 'done') setJob(j); })
            .catch(() => {});
        });
    } else {
      // No saved id — try server latest anyway
      fetch('/api/jobs/latest').then(r => r.ok ? r.json() : null)
        .then(j => { if (j && j.status === 'done') setJob(j); })
        .catch(() => {});
    }
  }, []);

  // ── Save job id when a proposal completes ─────────────────────────────────
  const handleJobDone = (j) => {
    setJob(j);
    if (j?.job_id || j?.id) {
      localStorage.setItem('latest_job_id', j.job_id || j.id);
    }
    setPage('review');
  };


  const loadKb = async () => {
    setKbLoading(true);
    try { const r = await api.kbLoad(); setKbInfo(r); } catch (e) { setError(String(e)); }
    setKbLoading(false);
  };

  return (
    <div className="layout">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-line">
            <img src="/techm_icon.png" alt="Tech Mahindra" style={{ height: '36px', borderRadius: '4px', marginRight: '10px' }} />
            <span className="logo-divider" />
            <span className="logo-name">RFP Intelligence</span>
          </div>
          <div className="logo-subtitle">AI Proposal Automation Platform</div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-label">Workspace</div>
          <ul className="sidebar-nav">
            {[
              { id: 'generate', label: 'Generate Proposal', icon: Cpu },
              { id: 'review',   label: 'Review & Refine',   icon: BookOpen, badge: job?.status === 'done' ? 'Ready' : null },
              { id: 'export',   label: 'Export Documents',  icon: Download },
              { id: 'kb',       label: 'Knowledge Base',    icon: Database, badge: kbInfo.count > 0 ? kbInfo.count : null },
            ].map(({ id, label, icon: Icon, badge }) => (
              <li key={id}><button className={page === id ? 'active' : ''} onClick={() => setPage(id)}>
                <Icon size={15} />{label}
                {badge && <span className="nav-badge">{badge}</span>}
              </button></li>
            ))}
          </ul>
        </div>

        <div className="sidebar-divider" />

        <div className="sidebar-section">
          <div className="sidebar-section-label">Configuration</div>
          <div className="form-group">
            <label className="form-label">Groq API Key</label>
            <input className="form-input" type="password" placeholder="gsk_..." value={groqKey} onChange={e => setGroqKey(e.target.value)} />
            <div className="form-hint">Free at console.groq.com</div>
          </div>
          <div className="form-group">
            <label className="form-label">Language Model</label>
            <select className="form-select" value={model} onChange={e => setModel(e.target.value)}>
              {MODELS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
        </div>

        <div className="sidebar-divider" />

        <div className="sidebar-status">
          <div className="sidebar-section-label" style={{ padding: '0 4px' }}>System Status</div>
          {[
            { label: 'API Server', dot: 'green pulse', val: 'Online' },
            { label: 'Knowledge Base', dot: kbInfo.count > 0 ? 'green' : 'grey', val: `${kbInfo.count} chunks` },
            { label: 'Model', dot: groqKey ? 'green' : 'grey', val: groqKey ? 'Ready' : 'No Key' },
          ].map(({ label, dot, val }) => (
            <div key={label} className="status-item">
              <div className={`status-dot ${dot}`} />
              <span className="status-label">{label}</span>
              <span className="status-value">{val}</span>
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          Powered by Groq · CrewAI · ChromaDB<br />
          Built for Tech Mahindra Pre-Sales
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="main">
        <header className="topbar">
          <div>
            <div className="topbar-title">
              {{ generate: 'Proposal Generator', review: 'Review & Refine', export: 'Export Documents', kb: 'Knowledge Base' }[page]}
            </div>
            <div className="topbar-subtitle">Tech Mahindra RFP Intelligence Platform</div>
          </div>
          <div className="topbar-right">
            {job?.status === 'done' && <div className="chip success"><CheckCircle size={12} /> Proposal Ready</div>}
            {job?.status === 'error' && <div className="chip error"><AlertCircle size={12} /> Generation Failed</div>}
            {generating && <div className="chip"><Loader size={12} /> Processing</div>}
            <div className="chip"><Globe size={12} /> v1.0</div>
          </div>
        </header>

        <div className="content">
          {error && <Alert type="error"><AlertCircle size={14} /><span>{error}</span></Alert>}
          {page === 'generate' && <GeneratePage groqKey={groqKey} model={model} onJobDone={handleJobDone} onError={setError} generating={generating} setGenerating={setGenerating} onNavigate={setPage} job={job} />}
          {page === 'review'   && <ReviewPage job={job} />}
          {page === 'export'   && <ExportPage job={job} />}
          {page === 'kb'       && <KbPage kbInfo={kbInfo} onUpdate={setKbInfo} loading={kbLoading} onLoad={loadKb} />}
        </div>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   GENERATE PAGE
════════════════════════════════════════════════════════════════ */
function GeneratePage({ groqKey, model, onJobDone, onError, generating, setGenerating, onNavigate, job }) {
  const [clientName, setClientName] = useState('');
  const [rfpFile, setRfpFile]       = useState(null);
  const [rfpText, setRfpText]       = useState('');
  const [progress, setProgress]     = useState(0);
  const [stage, setStage]           = useState('');
  const [showPaste, setShowPaste]   = useState(false);
  const [done, setDone]             = useState(false);

  const STAGES = { queued: 5, running: 40, analyst: 30, architect: 55, pricing: 75, writer: 90, complete: 100 };
  const STAGE_LABELS = {
    queued: 'Initialising agents…',
    running: 'Agents are processing your RFP…',
    analyst: 'Step 1 / 4 — Requirements Analyst is reading the RFP…',
    architect: 'Step 2 / 4 — Solution Architect is designing the solution…',
    pricing: 'Step 3 / 4 — Pricing Specialist is building the commercial model…',
    writer: 'Step 4 / 4 — Proposal Writer is compiling the final document…',
    complete: 'Finalising proposal…',
  };

  const handleGenerate = async () => {
    if (!groqKey) { onError('Please enter your Groq API Key in the sidebar.'); return; }
    if (!rfpFile && !rfpText.trim()) { onError('Please upload an RFP PDF or paste the RFP text.'); return; }
    onError(''); setGenerating(true); setProgress(5); setStage('Extracting RFP content…');

    try {
      let text = rfpText;
      if (rfpFile) {
        setStage('Parsing PDF document…'); setProgress(15);
        const r = await api.uploadRfp(rfpFile);
        text = r.text;
      }
      setStage('Dispatching to AI agents…'); setProgress(25);
      const { job_id } = await api.generate({ rfp_text: text, client_name: clientName || 'Client', model, groq_api_key: groqKey });

      const job = await pollJob(job_id, (j) => {
        const pct = STAGES[j.stage] || STAGES[j.status] || 40;
        setProgress(pct);
        setStage(STAGE_LABELS[j.stage] || STAGE_LABELS[j.status] || 'Agents working…');
      });
      setProgress(100); setStage('All 4 agents complete!');
      setDone(true);
      onJobDone(job);
    } catch (e) { onError(String(e)); setGenerating(false); return; }
    setGenerating(false);
  };

  return (
    <div>
      {/* Agent Pipeline */}
      <div className="pipeline">
        {AGENTS.map((a, i) => {
          const Icon = a.icon;
          const stepPct = [30, 55, 75, 90][i];
          const isDone   = progress >= (stepPct + 10);
          const isActive = progress >= stepPct && !isDone;
          return (
            <div key={a.key} className={`pipeline-step${isActive ? ' active' : isDone ? ' done' : ''}`}>
              <div className="pipeline-step-num">Step {i + 1}</div>
              <div className="pipeline-step-name"><Icon size={13} style={{ display: 'inline', marginRight: 5 }} />{a.label}</div>
              <div className="pipeline-step-role">{a.role}</div>
            </div>
          );
        })}
      </div>

      <div className="grid-2" style={{ gap: 24 }}>
        {/* Left: Inputs */}
        <div>
          <div className="card">
            <div className="card-header">
              <div className="card-icon red"><FileSearch size={16} /></div>
              <div><h3>RFP Document</h3><p>Upload the client's RFP for analysis</p></div>
            </div>
            <div className="card-body">
              <div className="form-group">
                <label className="form-label">Client / Organisation Name</label>
                <input className="form-input" placeholder="e.g. HDFC Bank, Reliance Industries…" value={clientName} onChange={e => setClientName(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">RFP Document (PDF)</label>
                <UploadZone onFile={setRfpFile} label="Drop RFP PDF here or click to browse" hint="Supports multi-page PDFs with tables and structured content" />
              </div>
              <button className="btn btn-secondary btn-sm" style={{ marginBottom: 12 }} onClick={() => setShowPaste(p => !p)}>
                {showPaste ? 'Hide' : 'Paste RFP text instead'}
              </button>
              {showPaste && (
                <div className="form-group">
                  <label className="form-label">RFP Text Content</label>
                  <textarea className="form-textarea" rows={8} placeholder="Paste full RFP text here…" value={rfpText} onChange={e => setRfpText(e.target.value)} />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: Generate + status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="card-header">
              <div className="card-icon blue"><Cpu size={16} /></div>
              <div><h3>Generation Controls</h3><p>Initiate the AI proposal pipeline</p></div>
            </div>
            <div className="card-body">
              {generating ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                    <Spinner /><span style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.5 }}>{stage}</span>
                  </div>
                  <ProgressBar pct={progress} />
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 8 }}>{progress}% complete — approx. 2–3 minutes total</div>
                </>
              ) : done && job?.status === 'done' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px', background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 10 }}>
                    <CheckCircle size={20} style={{ color: 'var(--success)', flexShrink: 0 }} />
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--success)' }}>Proposal Generated Successfully</div>
                      <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>All 4 agents completed — your proposal is ready</div>
                    </div>
                  </div>
                  <button className="btn btn-primary btn-full btn-lg" onClick={() => onNavigate('review')}>
                    <BookOpen size={16} /> View Your Proposal →
                  </button>
                  <button className="btn btn-secondary btn-full" onClick={() => onNavigate('export')}>
                    <Download size={14} /> Download Word / PowerPoint
                  </button>
                  <button className="btn btn-secondary btn-sm btn-full" style={{ opacity: 0.7 }} onClick={() => { setDone(false); setProgress(0); setStage(''); }}>
                    Generate Another Proposal
                  </button>
                </div>
              ) : (
                <button className="btn btn-primary btn-full btn-lg" onClick={handleGenerate}>
                  <Cpu size={16} /> Generate Proposal
                </button>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-icon blue"><BarChart3 size={16} /></div>
              <div><h3>What This Does</h3></div>
            </div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                'PDF is parsed to structured Markdown preserving tables',
                'Knowledge Base is queried for relevant past proposals',
                'Four specialised AI agents run sequentially',
                'Proposal is compiled with architecture diagrams',
                'Export to branded Word and PowerPoint in one click',
              ].map((s, i) => (
                <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <div style={{ width: 20, height: 20, borderRadius: '50%', background: 'rgba(200,0,43,0.15)', color: 'var(--red-light)', fontSize: 11, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{i + 1}</div>
                  <span style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.5 }}>{s}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   REVIEW PAGE
════════════════════════════════════════════════════════════════ */
function ReviewPage({ job }) {
  const [tab, setTab]       = useState('proposal');
  const [edited, setEdited] = useState('');

  useEffect(() => { if (job?.outputs?.proposal) setEdited(job.outputs.proposal); }, [job]);

  if (!job || job.status !== 'done') {
    return (
      <div className="empty-state">
        <Clock size={44} />
        <h4>No Proposal Generated Yet</h4>
        <p>Generate a proposal from the Generate page. Once complete, all agent outputs will appear here for review and editing.</p>
      </div>
    );
  }

  const { outputs } = job;
  const proposal = edited || outputs.proposal || '';
  const wordCount = proposal.split(/\s+/).filter(Boolean).length;
  const hasMermaid = /```mermaid/i.test(outputs.architecture || '');
  const hasTable   = (outputs.pricing || '').includes('|');

  const mermaidMatch = (outputs.architecture || '').match(/```mermaid\s*([\s\S]+?)```/i);
  let diagramUrl = null;
  if (mermaidMatch) {
    try {
      const code = mermaidMatch[1].trim();
      const compressed = btoa(String.fromCharCode(...new Uint8Array(
        Array.from(code).map(c => c.charCodeAt(0))
      )));
      diagramUrl = `https://kroki.io/mermaid/png/${btoa(unescape(encodeURIComponent(code))).replace(/\+/g,'-').replace(/\//g,'_')}`;
    } catch { diagramUrl = null; }
  }

  return (
    <div>
      <div className="metrics">
        <MetricCard label="Word Count"      value={wordCount.toLocaleString()} sub="In final proposal" />
        <MetricCard label="Architecture"    value={hasMermaid ? 'Included' : 'Not Found'} sub="Mermaid diagram" />
        <MetricCard label="Rate Tables"     value={hasTable ? 'Included' : 'Not Found'} sub="Pricing tables" />
        <MetricCard label="Agents Complete" value="4 / 4" sub="All agents ran" />
      </div>

      <div className="card">
        <div className="tabs">
          {[
            { id: 'proposal',     label: 'Full Proposal' },
            { id: 'analysis',     label: 'Requirements Analysis' },
            { id: 'architecture', label: 'Solution Architecture' },
            { id: 'pricing',      label: 'Commercial Model' },
          ].map(t => <button key={t.id} className={`tab-btn${tab === t.id ? ' active' : ''}`} onClick={() => setTab(t.id)}>{t.label}</button>)}
        </div>

        <div style={{ padding: 22 }}>
          {tab === 'proposal' && (
            <>
              <p style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 12 }}>Edit the proposal below before exporting. Changes are preserved when you switch to the Export tab.</p>
              <div className="editor-wrap">
                <textarea style={{ width: '100%', minHeight: 520, background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text-2)', fontFamily: "'DM Sans', sans-serif", fontSize: 13.5, lineHeight: 1.75, padding: 18, resize: 'vertical', outline: 'none' }}
                  value={edited} onChange={e => { setEdited(e.target.value); if (job.outputs) job.outputs.proposal = e.target.value; }} />
              </div>
            </>
          )}
          {tab === 'analysis'     && <MdRenderer text={outputs.analysis} />}
          {tab === 'architecture' && (
            <>
              <MdRenderer text={outputs.architecture} />
              {diagramUrl && (
                <div className="diagram-wrap" style={{ marginTop: 20 }}>
                  <div className="diagram-header">Solution Architecture Diagram</div>
                  <img src={diagramUrl} alt="Architecture Diagram" onError={e => { e.target.style.display = 'none'; }} />
                </div>
              )}
            </>
          )}
          {tab === 'pricing' && <MdRenderer text={outputs.pricing} />}
        </div>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   EXPORT PAGE
════════════════════════════════════════════════════════════════ */
function ExportPage({ job }) {
  const [loading, setLoading] = useState({ word: false, ppt: false });
  const [done,    setDone]    = useState({ word: false, ppt: false });
  const [err,     setErr]     = useState('');

  if (!job || job.status !== 'done') {
    return (
      <div className="empty-state">
        <Download size={44} />
        <h4>No Proposal Ready for Export</h4>
        <p>Complete proposal generation and review before exporting to Word or PowerPoint.</p>
      </div>
    );
  }

  const exportDoc = async (type) => {
    setLoading(l => ({ ...l, [type]: true })); setErr('');
    try {
      const fn = type === 'word' ? api.exportWord : api.exportPpt;
      const ext = type === 'word' ? 'docx' : 'pptx';
      const resp = await fn(job.id, job.client_name || 'Client');
      if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
      await downloadFile(resp, `TechM_Proposal_${job.client_name || 'Client'}.${ext}`);
      setDone(d => ({ ...d, [type]: true }));
    } catch (e) { setErr(String(e)); }
    setLoading(l => ({ ...l, [type]: false }));
  };

  return (
    <div>
      {err && <Alert type="error"><AlertCircle size={14} /><span>{err}</span></Alert>}

      <div className="grid-2">
        {[
          { type: 'word', label: 'Word Document', ext: '.docx', icon: FileSearch,
            desc: 'Structured document with TechM branding, all proposal sections, embedded architecture diagram, and formatted pricing tables.' },
          { type: 'ppt', label: 'PowerPoint Deck', ext: '.pptx', icon: BarChart3,
            desc: 'Multi-slide presentation: cover slide, agenda, solution architecture, team structure, rate card, and closing slide.' },
        ].map(({ type, label, ext, icon: Icon, desc }) => (
          <div className="export-card" key={type}>
            <div className="export-card-header">
              <div className="export-card-title">{label} <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>{ext}</span></div>
              <div className="export-card-desc">{desc}</div>
            </div>
            <div className="export-card-body">
              <button className={`btn btn-full ${type === 'word' ? 'btn-navy' : 'btn-primary'}`}
                disabled={loading[type]} onClick={() => exportDoc(type)}>
                {loading[type] ? <><Spinner size={14} /> Generating…</> : <><Download size={14} /> {done[type] ? 'Download Again' : `Download ${label}`}</>}
              </button>
              {done[type] && <div style={{ fontSize: 12, color: 'var(--success)', marginTop: 8, display: 'flex', gap: 6 }}><CheckCircle size={13} /> File downloaded successfully</div>}
            </div>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 24 }}>
        <div className="card-header">
          <div className="card-icon blue"><BookOpen size={16} /></div>
          <div><h3>Raw Markdown</h3><p>Copy to Notion, Confluence, or any editor</p></div>
        </div>
        <div className="card-body">
          <textarea readOnly style={{ width: '100%', minHeight: 300, background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text-3)', fontFamily: 'monospace', fontSize: 12.5, padding: 16, resize: 'vertical', outline: 'none' }}
            value={job.outputs?.proposal || ''} />
        </div>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════
   KB PAGE
════════════════════════════════════════════════════════════════ */
function KbPage({ kbInfo, onUpdate, loading, onLoad }) {
  const [file,    setFile]    = useState(null);
  const [uploading, setUploading] = useState(false);
  const [msg,     setMsg]     = useState('');
  const [err,     setErr]     = useState('');

  const upload = async () => {
    if (!file) return;
    setUploading(true); setMsg(''); setErr('');
    try {
      const r = await api.kbUpload(file);
      onUpdate({ count: r.chunks, sources: r.sources });
      setMsg(`"${file.name}" indexed successfully. KB now has ${r.chunks} chunks.`);
      setFile(null);
    } catch (e) { setErr(String(e)); }
    setUploading(false);
  };

  return (
    <div>
      <div className="metrics">
        <MetricCard label="Total Chunks" value={kbInfo.count.toLocaleString()} sub="Indexed passages" />
        <MetricCard label="Source Documents" value={kbInfo.sources.length} sub="Unique files" />
        <MetricCard label="Embedding Model" value="MiniLM" sub="all-MiniLM-L6-v2" />
        <MetricCard label="Vector Store" value="ChromaDB" sub="Local persistent" />
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div className="card-icon blue"><Upload size={16} /></div>
            <div><h3>Add Past Proposal</h3><p>Upload a past TechM proposal PDF to enrich the knowledge base</p></div>
          </div>
          <div className="card-body">
            {msg && <Alert type="success"><CheckCircle size={14} /><span>{msg}</span></Alert>}
            {err && <Alert type="error"><AlertCircle size={14} /><span>{err}</span></Alert>}
            <UploadZone onFile={setFile} label="Drop past proposal PDF here" hint="TechM proposals, SOWs, case studies — any PDF" />
            <div style={{ marginTop: 14, display: 'flex', gap: 10 }}>
              <button className="btn btn-primary" disabled={!file || uploading} onClick={upload}>
                {uploading ? <><Spinner size={14} /> Indexing…</> : <><Database size={14} /> Add to Knowledge Base</>}
              </button>
              <button className="btn btn-secondary" disabled={loading} onClick={onLoad}>
                {loading ? <><Spinner size={14} /> Loading…</> : 'Reload from Disk'}
              </button>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-icon green"><Database size={16} /></div>
            <div><h3>Indexed Sources</h3><p>{kbInfo.count} chunks across {kbInfo.sources.length} documents</p></div>
          </div>
          <div className="card-body">
            {kbInfo.sources.length === 0 ? (
              <div style={{ color: 'var(--text-3)', fontSize: 13 }}>No documents indexed yet. Upload past proposals to enhance AI output quality.</div>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                {kbInfo.sources.map(s => <span key={s} className="source-tag"><Database size={11} />{s}</span>)}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
