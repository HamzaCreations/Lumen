import {
  ArrowRight, BookOpen, CheckCircle2, Clock3, Cpu, FileText,
  Layers3, MessageSquareText, Sparkles, UploadCloud,
} from 'lucide-react'
import type { DocumentList, Health, View } from '../types'

type Props = {
  health: Health | null
  documents: DocumentList | null
  configured: boolean
  questionCount: number
  onNavigate: (view: View) => void
  onSuggest: (question: string) => void
}

function formatDate(iso: string): string {
  if (!iso) return 'Not available'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export function HomeView({ health, documents, configured, questionCount, onNavigate, onSuggest }: Props) {
  const stats = [
    { label: 'Documents', value: documents?.total_documents ?? '—', icon: FileText },
    { label: 'Searchable passages', value: health?.chunks?.toLocaleString() ?? '—', icon: Layers3 },
    { label: 'Vector dimensions', value: health?.dim ?? '—', icon: Cpu },
    { label: 'Answer model', value: health?.llm_model || 'Not set', icon: Sparkles, wide: true },
  ]

  return (
    <div className="view home-view">
      <section className="hero">
        <div className="hero-eyebrow"><Sparkles size={13} /> Document intelligence</div>
        <h2>Answers you can trace<br />back to the source.</h2>
        <p className="hero-copy">
          Lumen reads your course documents, finds the passages that matter, and writes an answer
          grounded in them — with every source shown alongside it.
        </p>
        <div className="hero-actions">
          <button className="btn primary" onClick={() => onNavigate('chat')}>
            <MessageSquareText size={16} /> Start a conversation <ArrowRight size={15} />
          </button>
          <button className="btn secondary" onClick={() => onNavigate('upload')}>
            <UploadCloud size={16} /> Add documents
          </button>
        </div>
        {!configured && (
          <div className="hero-note">
            <CheckCircle2 size={15} />
            <span>Retrieval is working. Add an API key in <button className="link-btn"
              onClick={() => onNavigate('settings')}>Settings</button> to enable AI answers.</span>
          </div>
        )}
      </section>

      <section className="section">
        <div className="section-head"><h3>At a glance</h3><span>Live from your index</span></div>
        <div className="stat-grid">
          {stats.map(({ label, value, icon: Icon, wide }) => (
            <div className={`stat-card ${wide ? 'wide' : ''}`} key={label}>
              <span className="stat-icon"><Icon size={17} strokeWidth={1.9} /></span>
              <span className="stat-value" title={String(value)}>{value}</span>
              <span className="stat-label">{label}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-head"><h3>How it works</h3><span>Three simple steps</span></div>
        <div className="steps">
          <div className="step-card">
            <span className="step-num">1</span>
            <UploadCloud size={20} />
            <h4>Add your files</h4>
            <p>Drop in plain-text documents. They are saved to the corpus on this machine.</p>
          </div>
          <div className="step-card">
            <span className="step-num">2</span>
            <Layers3 size={20} />
            <h4>We index them</h4>
            <p>Text is split into passages, embedded, and added to the search index automatically.</p>
          </div>
          <div className="step-card">
            <span className="step-num">3</span>
            <MessageSquareText size={20} />
            <h4>Ask a question</h4>
            <p>The best passages are retrieved and used to write a grounded, cited answer.</p>
          </div>
        </div>
      </section>

      <section className="section home-bottom">
        <div className="panel">
          <div className="section-head"><h3>Recent activity</h3><Clock3 size={16} className="muted-icon" /></div>
          <ul className="activity-list">
            <li>
              <span className="activity-dot ok" />
              <div><strong>Index {documents?.corpus_ok ? 'up to date' : 'needs rebuilding'}</strong>
                <span>Last built {formatDate(documents?.built_at || '')}</span></div>
            </li>
            <li>
              <span className="activity-dot" />
              <div><strong>{questionCount} question{questionCount === 1 ? '' : 's'} asked this session</strong>
                <span>Conversations stay on this device</span></div>
            </li>
            <li>
              <span className="activity-dot" />
              <div><strong>{documents?.total_documents ?? 0} documents indexed</strong>
                <span>{documents?.total_chunks?.toLocaleString() ?? 0} searchable passages</span></div>
            </li>
          </ul>
        </div>
        <div className="panel quick-ask">
          <div className="section-head"><h3>Try a question</h3><BookOpen size={16} className="muted-icon" /></div>
          <p>Not sure where to start? These are drawn from the indexed course material.</p>
          {['What is precision?', 'What does top-k mean in retrieval?', 'How do I handle missing values in pandas?'].map((q) => (
            <button key={q} className="quick-question" onClick={() => { onSuggest(q); onNavigate('chat') }}>
              {q} <ArrowRight size={14} />
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}
