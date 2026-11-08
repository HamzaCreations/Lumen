import { useState } from 'react'
import { testConnection } from '../api'
import type { Connection, Health, ProviderPreset } from '../types'

type Props = {
  value: Connection
  onChange: (next: Connection) => void
  health: Health | null
  disabled: boolean
}

const PRESETS: ProviderPreset[] = [
  { label: 'OpenAI', base: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  { label: 'OpenRouter', base: 'https://openrouter.ai/api/v1', model: 'openai/gpt-4o-mini' },
  { label: 'Groq · gpt-oss-120b (best)', base: 'https://api.groq.com/openai/v1', model: 'openai/gpt-oss-120b' },
  { label: 'Groq · gpt-oss-20b (fast)', base: 'https://api.groq.com/openai/v1', model: 'openai/gpt-oss-20b' },
  { label: 'Groq · qwen3.8-27b (fastest)', base: 'https://api.groq.com/openai/v1', model: 'qwen/qwen3.8-27b' },
  { label: 'DeepSeek', base: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { label: 'Gemini (OpenAI compat)', base: 'https://generativelanguage.googleapis.com/v1beta/openai', model: 'gemini-2.0-flash' },
  { label: 'HF Router', base: 'https://router.huggingface.co/v1', model: 'Qwen/Qwen2.5-1.5B-Instruct' },
  { label: 'Local (LM Studio / vLLM)', base: 'http://localhost:1234/v1', model: 'local-model' },
]

type TestState =
  | { kind: 'idle' }
  | { kind: 'testing' }
  | { kind: 'ok'; model: string; preview: string; latency: number }
  | { kind: 'error'; message: string }

export function ConnectionPanel({ value, onChange, health, disabled }: Props) {
  const [preset, setPreset] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [state, setState] = useState<TestState>({ kind: 'idle' })

  const set = (patch: Partial<Connection>) => onChange({ ...value, ...patch })

  const applyPreset = (label: string) => {
    setPreset(label)
    const p = PRESETS.find((x) => x.label === label)
    if (p) onChange({ ...value, apiBase: p.base, apiModel: p.model })
    setState({ kind: 'idle' })
  }

  const runTest = async () => {
    setState({ kind: 'testing' })
    try {
      const r = await testConnection(value)
      setState({ kind: 'ok', model: r.model, preview: r.preview, latency: r.latency_s })
    } catch (e) {
      setState({ kind: 'error', message: (e as Error).message })
    }
  }

  const serverConfigured = Boolean(health?.api_key_configured && health?.llm_ready)
  const usingOverride = Boolean(value.apiKey.trim())

  return (
    <section className="conn">
      <h3>API connection <span className="conn-tag">real LLM</span></h3>

      {serverConfigured && !usingOverride && (
        <p className="conn-status ok">Server key configured for <b>{health?.llm_model}</b>. You can override it below.</p>
      )}

      <label className="conn-row">
        <span>Provider preset</span>
        <select value={preset} disabled={disabled} onChange={(e) => applyPreset(e.target.value)}>
          <option value="">Custom / keep server settings</option>
          {PRESETS.map((p) => <option key={p.label} value={p.label}>{p.label}</option>)}
        </select>
      </label>

      <label className="conn-row">
        <span>Base URL</span>
        <input type="text" spellCheck={false} placeholder={health?.api_base || 'https://api.openai.com/v1'}
          value={value.apiBase} disabled={disabled}
          onChange={(e) => { set({ apiBase: e.target.value }); setState({ kind: 'idle' }) }} />
      </label>

      <label className="conn-row">
        <span>Model</span>
        <input type="text" spellCheck={false} placeholder={health?.llm_model || 'gpt-4o-mini'}
          value={value.apiModel} disabled={disabled}
          onChange={(e) => { set({ apiModel: e.target.value }); setState({ kind: 'idle' }) }} />
      </label>

      <label className="conn-row">
        <span>API key</span>
        <div className="conn-key">
          <input type={showKey ? 'text' : 'password'} autoComplete="off" spellCheck={false}
            placeholder="sk-…" value={value.apiKey} disabled={disabled}
            onChange={(e) => { set({ apiKey: e.target.value }); setState({ kind: 'idle' }) }} />
          <button type="button" className="conn-eye" onClick={() => setShowKey((s) => !s)}>
            {showKey ? 'Hide' : 'Show'}
          </button>
        </div>
      </label>

      <button className="btn secondary full conn-test" type="button" disabled={disabled || state.kind === 'testing'}
        onClick={() => void runTest()}>
        {state.kind === 'testing' ? 'Testing…' : 'Test connection'}
      </button>

      {state.kind === 'ok' && (
        <p className="conn-status ok">Connected · {state.model} · {state.latency}s · reply: “{state.preview}”</p>
      )}
      {state.kind === 'error' && <p className="conn-status err">{state.message}</p>}

      <p className="conn-note">
        The key is kept in this browser tab only (sessionStorage) and is sent to the local
        backend with each request. It is never written to disk, logged or returned.
        Alternatively set <code>RAG_API_KEY</code> in <code>backend/.env</code>.
      </p>
    </section>
  )
}
