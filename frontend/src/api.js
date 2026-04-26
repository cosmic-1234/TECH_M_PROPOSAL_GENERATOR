const BASE = '/api';

export const api = {
  health: () => fetch(`${BASE}/health`).then(r => r.json()),
  kbStatus: () => fetch(`${BASE}/kb/status`).then(r => r.json()),
  kbLoad: () => fetch(`${BASE}/kb/load`, { method: 'POST' }).then(r => r.json()),
  kbUpload: (file) => {
    const fd = new FormData(); fd.append('file', file);
    return fetch(`${BASE}/kb/upload`, { method: 'POST', body: fd }).then(r => { if (!r.ok) return r.json().then(e => Promise.reject(e.detail)); return r.json(); });
  },
  uploadRfp: (file) => {
    const fd = new FormData(); fd.append('file', file);
    return fetch(`${BASE}/upload-rfp`, { method: 'POST', body: fd }).then(r => { if (!r.ok) return r.json().then(e => Promise.reject(e.detail)); return r.json(); });
  },
  generate: (payload) => fetch(`${BASE}/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }).then(r => { if (!r.ok) return r.json().then(e => Promise.reject(e.detail)); return r.json(); }),
  getJob: (id) => fetch(`${BASE}/jobs/${id}`).then(r => r.json()),
  exportWord: (jobId, clientName) => fetch(`${BASE}/export/word`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job_id: jobId, client_name: clientName }) }),
  exportPpt:  (jobId, clientName) => fetch(`${BASE}/export/ppt`,  { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job_id: jobId, client_name: clientName }) }),
};

export async function pollJob(jobId, onUpdate, interval = 4000) {
  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      try {
        const job = await api.getJob(jobId);
        onUpdate(job);
        if (job.status === 'done' || job.status === 'error') {
          clearInterval(timer);
          job.status === 'done' ? resolve(job) : reject(new Error(job.error));
        }
      } catch (e) { clearInterval(timer); reject(e); }
    }, interval);
  });
}

export async function downloadFile(response, filename) {
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
