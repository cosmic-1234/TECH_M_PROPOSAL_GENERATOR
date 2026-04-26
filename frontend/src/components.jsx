import { useState, useCallback } from 'react';
import { Upload, X, FileText } from 'lucide-react';

export function UploadZone({ onFile, accept = '.pdf', label = 'Drop your PDF here', hint = 'PDF up to 50 MB' }) {
  const [drag, setDrag] = useState(false);
  const [file, setFile] = useState(null);

  const handle = useCallback((f) => { setFile(f); onFile(f); }, [onFile]);
  const onDrop = (e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) handle(f); };
  const clear = (e) => { e.stopPropagation(); setFile(null); onFile(null); };

  return (
    <div className={`upload-zone${drag ? ' dragover' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}>
      <input type="file" accept={accept} onChange={(e) => { if (e.target.files[0]) handle(e.target.files[0]); }} />
      {!file ? (
        <>
          <div className="upload-icon"><Upload size={36} /></div>
          <div className="upload-title">{label}</div>
          <div className="upload-sub">{hint}</div>
        </>
      ) : (
        <div className="upload-file">
          <FileText size={18} color="var(--success)" />
          <span className="upload-file-name">{file.name}</span>
          <span className="upload-file-size">{(file.size / 1024).toFixed(0)} KB</span>
          <button onClick={clear} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', marginLeft: 'auto' }}><X size={15} /></button>
        </div>
      )}
    </div>
  );
}

export function Spinner({ size = 18 }) {
  return <div className="spinner" style={{ width: size, height: size }} />;
}

export function Alert({ type = 'info', children }) {
  return <div className={`alert alert-${type}`}>{children}</div>;
}

export function MetricCard({ label, value, sub }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}

export function ProgressBar({ pct }) {
  return (
    <div className="progress-bar-bg">
      <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function MdRenderer({ text }) {
  if (!text) return null;
  const parsed = text
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    .replace(/\n\n/g, '<br/><br/>');
  return <div className="md-output" dangerouslySetInnerHTML={{ __html: parsed }} />;
}
