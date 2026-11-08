import { ScanSearch } from 'lucide-react'
import type { Controls as ControlsType } from '../types'

type Props = {
  value: ControlsType
  onChange: (next: ControlsType) => void
  disabled: boolean
  onInspect: () => void
  inspecting: boolean
  onSuggest: (question: string) => void
}

const SUGGESTIONS = [
  'What is precision?',
  'What does top-k mean in retrieval?',
  'How do I handle missing values in pandas?',
  'What is the difference between classification and regression?',
  'What is LangChain?',
]

export function Controls({ value, onChange, disabled, onInspect, inspecting, onSuggest }: Props) {
  const set = <K extends keyof ControlsType>(key: K, v: ControlsType[K]) =>
    onChange({ ...value, [key]: v })

  return (
    <div className="controls">
      <div className="control-group">
        <label className="control">
          <span>Passages to use <b>{value.k}</b></span>
          <input type="range" min={1} max={10} step={1} value={value.k}
            disabled={disabled} onChange={(e) => set('k', Number(e.target.value))} />
          <small>How many matching passages are given to the AI.</small>
        </label>

        <label className="control">
          <span>Confidence threshold <b>{value.minScore.toFixed(2)}</b></span>
          <input type="range" min={0} max={0.9} step={0.05} value={value.minScore}
            disabled={disabled} onChange={(e) => set('minScore', Number(e.target.value))} />
          <small>Below this match score the assistant says “I don't know” instead of guessing.</small>
        </label>

        <label className="control">
          <span>Search method</span>
          <select value={value.mode} disabled={disabled}
            onChange={(e) => set('mode', e.target.value as ControlsType['mode'])}>
            <option value="semantic">Meaning-based (recommended)</option>
            <option value="hybrid">Meaning + keywords</option>
          </select>
        </label>

        <label className="check">
          <input type="checkbox" checked={value.includeBaseline} disabled={disabled}
            onChange={(e) => set('includeBaseline', e.target.checked)} />
          <span>Also show an answer <b>without</b> documents, for comparison</span>
        </label>
      </div>

      <button className="btn secondary full" type="button" onClick={onInspect}
        disabled={disabled || inspecting}>
        <ScanSearch size={15} /> {inspecting ? 'Searching…' : 'Preview retrieved passages'}
      </button>
      <p className="control-hint">See what the system found without generating an answer.</p>

      <div className="suggestions">
        <h4>Try asking</h4>
        {SUGGESTIONS.map((q) => (
          <button key={q} type="button" className="suggestion" disabled={disabled}
            onClick={() => onSuggest(q)}>{q}</button>
        ))}
      </div>
    </div>
  )
}
