import { Cpu, Database, Info, KeyRound, SlidersHorizontal, Sparkles } from 'lucide-react'
import { ConnectionPanel } from '../components/ConnectionPanel'
import type { Connection, Controls as ControlsType, DocumentList, Health } from '../types'

type Props = {
  connection: Connection
  onConnectionChange: (next: Connection) => void
  health: Health | null
  documents: DocumentList | null
  controls: ControlsType
  onControlsChange: (next: ControlsType) => void
}

export function SettingsView({ connection, onConnectionChange, health, documents,
  controls, onControlsChange }: Props) {
  const set = <K extends keyof ControlsType>(key: K, v: ControlsType[K]) =>
    onControlsChange({ ...controls, [key]: v })

  return (
    <div className="view settings-view">
      <div className="settings-grid">
        <section className="panel">
          <div className="section-head"><h3><KeyRound size={16} /> AI connection</h3>
            <span>Real generation</span></div>
          <p className="panel-intro">Choose the model that writes answers. Retrieval always runs locally
            against your own documents.</p>
          <ConnectionPanel value={connection} onChange={onConnectionChange} health={health} disabled={false} />
        </section>

        <section className="panel">
          <div className="section-head"><h3><SlidersHorizontal size={16} /> Answer preferences</h3>
            <span>Default behaviour</span></div>
          <p className="panel-intro">These apply to every new question you ask.</p>

          <label className="setting-row">
            <div><strong>Passages per question</strong><span>How much context the AI receives</span></div>
            <div className="setting-control">
              <input type="range" min={1} max={10} value={controls.k}
                onChange={(e) => set('k', Number(e.target.value))} />
              <b>{controls.k}</b>
            </div>
          </label>

          <label className="setting-row">
            <div><strong>Confidence threshold</strong><span>Lower values allow weaker matches</span></div>
            <div className="setting-control">
              <input type="range" min={0} max={0.9} step={0.05} value={controls.minScore}
                onChange={(e) => set('minScore', Number(e.target.value))} />
              <b>{controls.minScore.toFixed(2)}</b>
            </div>
          </label>

          <label className="setting-row">
            <div><strong>Search method</strong><span>How passages are ranked</span></div>
            <select value={controls.mode} onChange={(e) => set('mode', e.target.value as ControlsType['mode'])}>
              <option value="semantic">Meaning-based</option>
              <option value="hybrid">Meaning + keywords</option>
            </select>
          </label>

          <label className="setting-row">
            <div><strong>Show comparison</strong><span>Also answer without using documents</span></div>
            <input className="switch" type="checkbox" checked={controls.includeBaseline}
              onChange={(e) => set('includeBaseline', e.target.checked)} />
          </label>
        </section>

        <section className="panel">
          <div className="section-head"><h3><Database size={16} /> System information</h3>
            <span>Live values</span></div>
          <dl className="kv-list">
            <div><dt>Index status</dt><dd>{health?.index_ready ? 'Ready' : 'Not ready'}</dd></div>
            <div><dt>Corpus in sync</dt><dd>{health?.corpus_ok ? 'Yes' : 'No'}</dd></div>
            <div><dt>Documents</dt><dd>{documents?.total_documents ?? '—'}</dd></div>
            <div><dt>Searchable passages</dt><dd>{health?.chunks?.toLocaleString() ?? '—'}</dd></div>
            <div><dt>Embedding model</dt><dd>{health?.embedding_model || '—'}</dd></div>
            <div><dt>Vector dimensions</dt><dd>{health?.dim ?? '—'}</dd></div>
            <div><dt>Answer model</dt><dd>{health?.llm_model || '—'}</dd></div>
            <div><dt>Generation backend</dt><dd>{health?.llm_backend || '—'}</dd></div>
          </dl>
        </section>

        <section className="panel about-panel">
          <div className="section-head"><h3><Info size={16} /> About</h3></div>
          <div className="about-mark"><Sparkles size={22} /></div>
          <h4>Lumen · Document Intelligence</h4>
          <p>A Retrieval-Augmented Generation system built with React, FastAPI, FAISS and
            MiniLM embeddings. Questions are answered only from indexed documents; sources are
            shown with every answer.</p>
          <div className="about-chips">
            <span><Cpu size={13} /> 384-dimensional vectors</span>
            <span><Database size={13} /> Local FAISS index</span>
          </div>
        </section>
      </div>
    </div>
  )
}
