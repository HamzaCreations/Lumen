import { useEffect, useRef, useState } from 'react'
import {
  ArrowUp, ChevronDown, MessageSquareText, PanelRightClose,
  PanelRightOpen, RotateCcw, SlidersHorizontal, Sparkles,
} from 'lucide-react'
import { Controls } from '../components/Controls'
import { Message } from '../components/Message'
import type { ChatMessage, Connection, Controls as ControlsType, Health } from '../types'

type Props = {
  messages: ChatMessage[]
  streaming: boolean
  inspecting: boolean
  controls: ControlsType
  onControlsChange: (next: ControlsType) => void
  connection: Connection
  health: Health | null
  input: string
  onInputChange: (value: string) => void
  onAsk: (question: string) => void
  onInspect: (question: string) => void
  onStop: () => void
  onClear: () => void
  onOpenSettings: () => void
}

const STARTERS = [
  'What is precision?',
  'What does top-k mean in retrieval?',
  'How do I handle missing values in pandas?',
  'What is LangChain?',
]

export function ChatView({ messages, streaming, inspecting, controls, onControlsChange,
  connection, health, input, onInputChange, onAsk, onInspect, onStop, onClear,
  onOpenSettings }: Props) {
  const [railOpen, setRailOpen] = useState(false)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages])
  useEffect(() => { inputRef.current?.focus() }, [])

  const send = () => {
    const q = input.trim()
    if (!q || streaming) return
    onAsk(q)
  }

  const suggest = (q: string) => {
    onInputChange(q)
    inputRef.current?.focus()
  }

  return (
    <div className="view chat-view">
      <div className="chat-toolbar">
        <div className="chat-toolbar-title">
          <MessageSquareText size={17} />
          <div><strong>Conversation</strong><span>Grounded in your indexed documents</span></div>
        </div>
        <div className="chat-toolbar-actions">
          <button className="btn ghost" onClick={onClear} disabled={!messages.length || streaming}
            title="Clear this conversation">
            <RotateCcw size={15} /> <span>Clear chat</span>
          </button>
          <button className="btn ghost rail-toggle" onClick={() => setRailOpen((v) => !v)}
            title="Retrieval settings">
            <SlidersHorizontal size={16} /> <span>Settings</span>
            {railOpen ? <ChevronDown size={14} /> : <PanelRightOpen size={14} />}
          </button>
        </div>
      </div>

      <div className={`chat-layout ${railOpen ? 'rail-visible' : ''}`}>
        <div className="chat-main">
          <div className="chat-scroll">
            {messages.length === 0 ? (
              <div className="chat-empty">
                <div className="empty-mark"><Sparkles size={26} strokeWidth={1.7} /></div>
                <h2>Ask your documents anything</h2>
                <p>Lumen searches your indexed sources, then writes an answer using only what it finds.
                  Every answer includes the passages it relied on.</p>
                <div className="starter-grid">
                  {STARTERS.map((q) => (
                    <button key={q} className="starter" onClick={() => suggest(q)}>{q}</button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="message-list">
                {messages.map((m) => (
                  <Message key={m.id} message={m}
                    streaming={streaming && m.id === messages[messages.length - 1]?.id} />
                ))}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="composer-wrap">
            {streaming && (
              <div className="thinking-bar"><span className="dots"><i /><i /><i /></span>
                Searching your documents and writing an answer…</div>
            )}
            <div className="composer">
              <textarea ref={inputRef} value={input} rows={2}
                placeholder="Ask a question about your documents…"
                onChange={(e) => onInputChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
                }} />
              {streaming ? (
                <button className="send-btn stop" onClick={onStop} title="Stop generating"
                  aria-label="Stop generating"><span className="stop-square" /></button>
              ) : (
                <button className="send-btn" onClick={send} disabled={!input.trim()}
                  title="Send question" aria-label="Send question"><ArrowUp size={19} /></button>
              )}
            </div>
            <p className="composer-hint">Answers are generated only from your documents · Enter to send · Shift + Enter for a new line</p>
          </div>
        </div>

        <aside className="chat-rail">
          <div className="rail-head">
            <strong>Answer settings</strong>
            <button className="icon-btn" onClick={() => setRailOpen(false)}
              title="Close settings" aria-label="Close settings"><PanelRightClose size={16} /></button>
          </div>
          <Controls value={controls} onChange={onControlsChange} disabled={streaming}
            onInspect={() => onInspect(input.trim())} inspecting={inspecting} onSuggest={suggest} />
          <button className="connection-card" onClick={onOpenSettings}>
            <span className={`status-dot ${health?.llm_ready || connection.apiKey ? 'ok' : 'off'}`} />
            <div>
              <strong>{health?.llm_ready || connection.apiKey ? 'AI answers enabled' : 'API key needed'}</strong>
              <span>{connection.apiModel.trim() || health?.llm_model || 'Configure in Settings'}</span>
            </div>
            <span className="chev">›</span>
          </button>
        </aside>
      </div>
    </div>
  )
}
