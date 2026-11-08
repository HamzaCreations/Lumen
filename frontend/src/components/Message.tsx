import { useState } from 'react'
import { Check, Copy, Info, Sparkles } from 'lucide-react'
import { AnswerText } from './AnswerText'
import { SourceCard } from './SourceCard'
import type { ChatMessage } from '../types'

type Props = { message: ChatMessage; streaming: boolean }

/** SSE timings arrive in stages, so every field may be temporarily absent. */
const num = (value: number | undefined, digits = 2): string =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—'

const timing = (label: string, value: number | undefined): string =>
  typeof value === 'number' && Number.isFinite(value)
    ? `${label} ${value.toFixed(2)}s`
    : `${label} …`

export function Message({ message, streaming }: Props) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    if (!message.content) return
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  return (
    <article className={`message ${isUser ? 'user' : 'assistant'}`}>
      <div className="avatar" aria-hidden="true">
        {isUser ? 'You' : <Sparkles size={16} strokeWidth={1.9} />}
      </div>
      <div className="message-body">
        <div className="message-meta">
          <strong>{isUser ? 'You' : 'Lumen'}</strong>
          {!isUser && message.topScore !== undefined && (
            <span className="match-pill">best match {num(message.topScore, 3)}</span>
          )}
        </div>

        <div className={`bubble ${message.abstained ? 'abstained' : ''} ${message.error ? 'errored' : ''}`}>
          {message.content ? (
            isUser ? message.content : (
              <AnswerText text={message.content} rich={!streaming} sources={message.sources} />
            )
          ) : (streaming && !isUser ? <span className="typing">Thinking…</span> : '')}
          {streaming && !isUser && message.content && <span className="caret" />}
        </div>

        {message.error && (
          <div className="error-text"><Info size={14} /> {message.error}</div>
        )}

        {!isUser && message.content && !streaming && !message.error && (
          <div className="message-actions">
            <button className="mini-btn" onClick={() => void copy()} title="Copy answer">
              {copied ? <Check size={13} /> : <Copy size={13} />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            {message.timings && (
              <span className="timings">
                {timing('retrieval', message.timings.retrieval_s)} · {timing('generation', message.timings.generation_s)}
              </span>
            )}
          </div>
        )}

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="sources">
            <div className="sources-title">
              <span>Sources</span>
              <span className="sources-count">{message.sources.length} passages used</span>
            </div>
            {message.sources.map((s, i) => <SourceCard key={`${s.id}-${i}`} source={s} rank={i + 1} />)}
          </div>
        )}

        {!isUser && message.abstained && (
          <p className="abstain-note"><Info size={13} /> No answer was generated — the retrieved passages did not match well enough.</p>
        )}

        {!isUser && message.baseline && (
          <div className="baseline">
            <div className="sources-title">Without documents (for comparison)</div>
            <div className="bubble baseline-bubble"><AnswerText text={message.baseline} rich /></div>
          </div>
        )}
      </div>
    </article>
  )
}
