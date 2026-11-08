import { useRef, useState } from 'react'
import {
  ArrowRight, CheckCircle2, CircleAlert, Clock3, FileText, FolderOpen,
  HardDrive, Layers3, LoaderCircle, RefreshCw, Trash2, UploadCloud,
} from 'lucide-react'
import type { DocumentList, UploadItem, View } from '../types'

type Props = {
  focus: 'upload' | 'library'
  documents: DocumentList | null
  uploads: UploadItem[]
  busy: boolean
  deleting: string | null
  error: string | null
  onUpload: (files: File[]) => void
  onDelete: (name: string) => void
  onRefresh: () => void
  onNavigate: (view: View) => void
}

function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function dateLabel(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

function fileIcon(type: string) {
  // Only plain text is accepted by the current pipeline; keep a generic
  // document glyph so the table stays consistent if other types are added.
  return type === 'TXT' ? <FileText size={17} /> : <FolderOpen size={17} />
}

export function DocumentsView({ focus, documents, uploads, busy, deleting, error,
  onUpload, onDelete, onRefresh, onNavigate }: Props) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const pick = (list: FileList | null) => {
    if (!list?.length) return
    onUpload(Array.from(list))
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="view documents-view">
      <div className="segmented" role="tablist">
        <button role="tab" aria-selected={focus === 'upload'}
          className={focus === 'upload' ? 'active' : ''} onClick={() => onNavigate('upload')}>
          <UploadCloud size={15} /> Upload
        </button>
        <button role="tab" aria-selected={focus === 'library'}
          className={focus === 'library' ? 'active' : ''} onClick={() => onNavigate('library')}>
          <FolderOpen size={15} /> Library
        </button>
      </div>

      <div className="doc-stats">
        <div className="doc-stat"><Layers3 size={17} /><div><strong>{documents?.total_documents ?? '—'}</strong><span>Documents</span></div></div>
        <div className="doc-stat"><HardDrive size={17} /><div><strong>{documents?.total_chunks?.toLocaleString() ?? '—'}</strong><span>Searchable passages</span></div></div>
        <div className="doc-stat"><CheckCircle2 size={17} /><div>
          <strong className={documents?.corpus_ok ? 'good' : 'warn-text'}>{documents?.corpus_ok ? 'Up to date' : 'Needs indexing'}</strong>
          <span>Index status</span></div></div>
      </div>

      {error && <div className="inline-error"><CircleAlert size={15} /> {error}</div>}

      {focus === 'upload' ? (
        <>
          <section className="panel upload-panel">
            <div className="section-head"><h3>Add documents</h3><span>Plain text (.txt)</span></div>
            <div className={`dropzone ${dragging ? 'dragging' : ''} ${busy ? 'busy' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files) }}>
              <div className="dropzone-icon"><UploadCloud size={26} strokeWidth={1.6} /></div>
              <h4>Drag and drop your files here</h4>
              <p>or choose files from your computer</p>
              <button className="btn primary" type="button" disabled={busy}
                onClick={() => inputRef.current?.click()}>Browse files</button>
              <input ref={inputRef} type="file" accept=".txt,text/plain" multiple hidden
                onChange={(e) => pick(e.target.files)} />
              <p className="dropzone-hint">Supported: UTF-8 <b>.txt</b> · up to 2 MB of text per file · multiple files allowed</p>
            </div>
            <p className="format-note">
              <CircleAlert size={14} /> This system indexes plain text. PDF and Word files need to be
              exported to .txt first — other formats are intentionally not offered.
            </p>
          </section>

          <section className="panel">
            <div className="section-head"><h3>Upload progress</h3>
              {busy && <span className="processing"><LoaderCircle size={14} className="spin" /> Indexing…</span>}
            </div>
            {uploads.length === 0 ? (
              <div className="mini-empty"><Clock3 size={18} /><span>No uploads yet. Files you add will appear here.</span></div>
            ) : (
              <ul className="upload-list">
                {uploads.map((u) => (
                  <li key={u.id} className={`upload-item ${u.status}`}>
                    <span className="upload-file-icon"><FileText size={16} /></span>
                    <div className="upload-info">
                      <div className="upload-row"><strong>{u.name}</strong>
                        <span className="upload-status">
                          {u.status === 'uploading' && `Uploading ${u.progress}%`}
                          {u.status === 'processing' && 'Processing & indexing…'}
                          {u.status === 'done' && <><CheckCircle2 size={13} /> Indexed</>}
                          {u.status === 'error' && <><CircleAlert size={13} /> Failed</>}
                        </span>
                      </div>
                      <div className="progress-track"><div className="progress-fill"
                        style={{ width: `${u.status === 'done' ? 100 : u.progress}%` }} /></div>
                      {u.message && <span className="upload-message">{u.message}</span>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="panel next-panel">
            <div><strong>Want to see what's indexed?</strong>
              <span>All documents, their passage counts and processing status.</span></div>
            <button className="btn secondary" onClick={() => onNavigate('library')}>
              Open library <ArrowRight size={15} /></button>
          </div>
        </>
      ) : (
        <>
          <section className="panel">
            <div className="section-head">
              <h3>Indexed documents</h3>
              <div className="head-actions">
                <button className="btn ghost" onClick={onRefresh} disabled={busy} title="Refresh list">
                  <RefreshCw size={15} /> Refresh
                </button>
                <button className="btn secondary" onClick={() => onNavigate('upload')}>
                  <UploadCloud size={15} /> Add files
                </button>
              </div>
            </div>

            {!documents || documents.total_documents === 0 ? (
              <div className="mini-empty"><FolderOpen size={20} />
                <span>No documents yet. Add a .txt file to get started.</span></div>
            ) : (
              <div className="table-wrap">
                <table className="doc-table">
                  <thead><tr>
                    <th>Document</th><th>Type</th><th>Size</th><th>Passages</th>
                    <th>Added</th><th>Status</th><th aria-label="Actions" />
                  </tr></thead>
                  <tbody>
                    {documents.documents.map((d) => (
                      <tr key={d.name}>
                        <td><div className="doc-name">{fileIcon(d.type)}<span title={d.name}>{d.name}</span></div></td>
                        <td><span className="type-pill">{d.type}</span></td>
                        <td>{sizeLabel(d.size_bytes)}</td>
                        <td>{d.chunks.toLocaleString()}</td>
                        <td>{dateLabel(d.modified)}</td>
                        <td><span className={`status-badge ${d.status === 'Indexed' ? 'ok' : 'warn'}`}>
                          {d.status === 'Indexed' ? <CheckCircle2 size={12} /> : <CircleAlert size={12} />}
                          {d.status}</span></td>
                        <td>
                          <button className="icon-btn danger" title={`Remove ${d.name}`}
                            aria-label={`Remove ${d.name}`} disabled={busy}
                            onClick={() => onDelete(d.name)}>
                            {deleting === d.name ? <LoaderCircle size={15} className="spin" /> : <Trash2 size={15} />}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="panel info-panel">
            <div className="section-head"><h3>Processing status</h3>
              <span className={`status-badge ${documents?.corpus_ok ? 'ok' : 'warn'}`}>
                {documents?.corpus_ok ? <CheckCircle2 size={12} /> : <CircleAlert size={12} />}
                {documents?.corpus_ok ? 'Ready' : 'Needs indexing'}
              </span>
            </div>
            <div className="info-grid">
              <div><span>Last indexed</span><strong>{documents?.built_at ? new Date(documents.built_at).toLocaleString() : '—'}</strong></div>
              <div><span>Embedding model</span><strong>{documents?.embedding_model || '—'}</strong></div>
              <div><span>Vector size</span><strong>{documents?.dim || '—'} dimensions</strong></div>
              <div><span>Search method</span><strong>Cosine similarity (FAISS)</strong></div>
            </div>
            <p className="info-note"><Clock3 size={14} /> Adding or removing a file rebuilds the whole
              index. On this machine that takes about 20–30 seconds — the list updates when it's done.</p>
          </section>
        </>
      )}
    </div>
  )
}
