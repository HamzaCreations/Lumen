import { useEffect, useRef, useState } from 'react'
import { CircleAlert, X } from 'lucide-react'
import { deleteDocument, getDocuments, getHealth, search, streamAsk, uploadDocuments } from './api'
import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { ChatView } from './views/ChatView'
import { DocumentsView } from './views/DocumentsView'
import { HomeView } from './views/HomeView'
import { SettingsView } from './views/SettingsView'
import type {
  ChatMessage, Connection, Controls as ControlsType, DocumentList,
  Health, StreamEvent, UploadItem, View,
} from './types'

const uid = () => Math.random().toString(36).slice(2, 10)
const CONN_KEY = 'rag:connection'

/** Credentials live only for this browser tab. Nothing is persisted to disk. */
function loadConnection(): Connection {
  try {
    const raw = sessionStorage.getItem(CONN_KEY)
    if (raw) {
      const p = JSON.parse(raw)
      return { apiKey: p.apiKey ?? '', apiBase: p.apiBase ?? '', apiModel: p.apiModel ?? '' }
    }
  } catch { /* ignore unavailable storage */ }
  return { apiKey: '', apiBase: '', apiModel: '' }
}

export default function App() {
  const [view, setView] = useState<View>('home')
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [documents, setDocuments] = useState<DocumentList | null>(null)
  const [docError, setDocError] = useState<string | null>(null)
  const [docBusy, setDocBusy] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [uploads, setUploads] = useState<UploadItem[]>([])

  const [connection, setConnection] = useState<Connection>(loadConnection)
  const [controls, setControls] = useState<ControlsType>({
    k: 3, minScore: 0.4, mode: 'semantic', includeBaseline: false,
  })
  const [controlsInitialised, setControlsInitialised] = useState(false)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [inspecting, setInspecting] = useState(false)
  const [questionCount, setQuestionCount] = useState(0)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    getHealth().then((h) => {
      setHealth(h)
      if (!controlsInitialised) {
        setControls((c) => ({ ...c, k: h.default_k, minScore: h.default_min_score }))
        setControlsInitialised(true)
      }
    }).catch((e: Error) => setHealthError(e.message))
    refreshDocuments()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    try { sessionStorage.setItem(CONN_KEY, JSON.stringify(connection)) } catch { /* ignore */ }
  }, [connection])

  const refreshDocuments = () => {
    getDocuments().then(setDocuments).catch((e: Error) => setDocError(e.message))
  }

  const patch = (id: string, fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)))

  const ask = async (question: string) => {
    const q = question.trim()
    if (!q || streaming) return
    setInput('')
    setQuestionCount((n) => n + 1)
    setView('chat')
    const assistantId = uid()
    setMessages((prev) => [
      ...prev,
      { id: uid(), role: 'user', content: q },
      { id: assistantId, role: 'assistant', content: '' },
    ])
    setStreaming(true)
    const ctrl = new AbortController()
    abortRef.current = ctrl

    const onEvent = (ev: StreamEvent) => {
      switch (ev.type) {
        case 'meta':
          patch(assistantId, (m) => ({ ...m, sources: ev.sources, abstained: ev.abstained,
            topScore: ev.top_score, timings: ev.timings }))
          break
        case 'token':
          patch(assistantId, (m) => ({ ...m, content: m.content + ev.text }))
          break
        case 'baseline':
          patch(assistantId, (m) => ({ ...m, baseline: ev.text }))
          break
        case 'done':
          patch(assistantId, (m) => ({ ...m, content: ev.answer || m.content,
            abstained: ev.abstained, timings: ev.timings }))
          break
        case 'error':
          patch(assistantId, (m) => ({ ...m, error: ev.message }))
          break
      }
    }

    try {
      await streamAsk({
        question: q, k: controls.k, min_score: controls.minScore,
        mode: controls.mode, include_baseline: controls.includeBaseline,
      }, connection, onEvent, ctrl.signal)
    } catch (e) {
      const err = e as Error
      if (err.name !== 'AbortError') patch(assistantId, (m) => ({ ...m, error: err.message }))
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }

  const inspect = async (raw: string) => {
    const lastUser = [...messages].reverse().find((m) => m.role === 'user')
    const q = (raw || lastUser?.content || '').trim()
    if (!q || inspecting) return
    setInspecting(true)
    try {
      const res = await search(q, controls.k, controls.mode)
      const top = res.hits.length ? Math.max(...res.hits.map((h) => h.semantic_score)) : 0
      setMessages((prev) => [...prev, {
        id: uid(), role: 'assistant',
        content: `Retrieved passages for “${q}” — no answer was generated.`,
        sources: res.hits, topScore: top,
      }])
    } catch (e) {
      setMessages((prev) => [...prev, { id: uid(), role: 'assistant', content: '',
        error: (e as Error).message }])
    } finally {
      setInspecting(false)
    }
  }

  const upload = async (files: File[]) => {
    if (docBusy || files.length === 0) return
    const valid: { name: string; content: string }[] = []
    const items: UploadItem[] = []

    for (const file of files) {
      const id = uid()
      if (!file.name.toLowerCase().endsWith('.txt')) {
        items.push({ id, name: file.name, progress: 0, status: 'error',
          message: 'Only .txt files are supported.' })
      } else if (file.size > 2_000_000) {
        items.push({ id, name: file.name, progress: 0, status: 'error',
          message: 'File is larger than the 2 MB text limit.' })
      } else {
        const content = await file.text()
        if (!content.trim()) {
          items.push({ id, name: file.name, progress: 0, status: 'error', message: 'File is empty.' })
        } else {
          valid.push({ name: file.name, content })
          items.push({ id, name: file.name, progress: 0, status: 'uploading' })
        }
      }
    }

    setUploads((prev) => [...items, ...prev])
    if (!valid.length) return

    const activeIds = items.filter((i) => i.status === 'uploading').map((i) => i.id)
    const patchUploads = (p: Partial<UploadItem>) =>
      setUploads((prev) => prev.map((i) => (activeIds.includes(i.id) ? { ...i, ...p } : i)))

    setDocBusy(true)
    setDocError(null)
    try {
      const result = await uploadDocuments(valid, (pct) =>
        patchUploads(pct >= 100 ? { status: 'processing', progress: 100 } : { progress: pct }))
      setDocuments(result)
      patchUploads({ status: 'done', progress: 100, message: 'Indexed and ready to search' })
      getHealth().then(setHealth).catch(() => undefined)
    } catch (e) {
      const message = (e as Error).message
      patchUploads({ status: 'error', message })
      setDocError(message)
    } finally {
      setDocBusy(false)
    }
  }

  const removeDoc = async (name: string) => {
    if (docBusy) return
    if (!window.confirm(`Remove “${name}” from the library?\n\nThe search index will be rebuilt (about 20–30 seconds).`)) return
    setDeleting(name)
    setDocBusy(true)
    setDocError(null)
    try {
      const result = await deleteDocument(name)
      setDocuments(result)
      getHealth().then(setHealth).catch(() => undefined)
    } catch (e) {
      setDocError((e as Error).message)
    } finally {
      setDeleting(null)
      setDocBusy(false)
    }
  }

  const navigate = (next: View) => { setView(next); setMobileNavOpen(false) }

  const configured = Boolean(connection.apiKey.trim() || health?.api_key_configured)
  const model = connection.apiModel.trim() || health?.llm_model || ''

  return (
    <div className="app-shell">
      <Sidebar view={view} onNavigate={navigate} collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((v) => !v)} mobileOpen={mobileNavOpen}
        onCloseMobile={() => setMobileNavOpen(false)} online={Boolean(health) && !healthError}
        documentCount={documents?.total_documents ?? 0} />

      <div className="main-column">
        <TopBar view={view} onOpenMobileNav={() => setMobileNavOpen(true)}
          online={Boolean(health) && !healthError} configured={configured} model={model} />

        <main className="content">
          {healthError && (
            <div className="global-banner">
              <CircleAlert size={16} />
              <span><strong>Backend unavailable.</strong> {healthError} — start the API server on port 8000.</span>
              <button className="icon-btn" onClick={() => setHealthError(null)} aria-label="Dismiss"><X size={15} /></button>
            </div>
          )}

          {view === 'home' && (
            <HomeView health={health} documents={documents} configured={configured}
              questionCount={questionCount} onNavigate={navigate}
              onSuggest={(q) => { setInput(q); navigate('chat') }} />
          )}
          {view === 'chat' && (
            <ChatView messages={messages} streaming={streaming} inspecting={inspecting}
              controls={controls} onControlsChange={setControls} connection={connection}
              health={health} input={input} onInputChange={setInput}
              onAsk={ask} onInspect={inspect} onStop={() => abortRef.current?.abort()}
              onClear={() => setMessages([])} onOpenSettings={() => navigate('settings')} />
          )}
          {(view === 'upload' || view === 'library') && (
            <DocumentsView focus={view === 'upload' ? 'upload' : 'library'}
              documents={documents} uploads={uploads} busy={docBusy} deleting={deleting}
              error={docError} onUpload={upload} onDelete={removeDoc}
              onRefresh={refreshDocuments} onNavigate={navigate} />
          )}
          {view === 'settings' && (
            <SettingsView connection={connection} onConnectionChange={setConnection}
              health={health} documents={documents} controls={controls}
              onControlsChange={setControls} />
          )}
        </main>
      </div>
    </div>
  )
}
