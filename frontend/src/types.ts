export type View = 'home' | 'chat' | 'upload' | 'library' | 'settings'

export type Theme = 'light' | 'dark'

export type Source = {
  id: number
  source: string
  score: number
  semantic_score: number
  text: string
  snippet: string
}

/** Runtime credentials. Kept in sessionStorage only - never persisted to disk. */
export type Connection = {
  apiKey: string
  apiBase: string
  apiModel: string
}

export type ProviderPreset = {
  label: string
  base: string
  model: string
}

export type ConnectionTestResult = {
  ok: boolean
  model: string
  api_base: string
  preview: string
  latency_s: number
}

export type Controls = {
  k: number
  minScore: number
  mode: 'semantic' | 'hybrid'
  includeBaseline: boolean
}

export type AskRequest = {
  question: string
  k: number
  min_score: number
  mode: 'semantic' | 'hybrid'
  include_baseline: boolean
  api_key?: string
  api_base?: string
  api_model?: string
}

export type Health = {
  status: string
  index_ready: boolean
  corpus_ok: boolean
  chunks: number
  dim: number
  embedding_model: string
  corpus_sha256: string
  llm_backend: string
  llm_model: string
  llm_loaded: boolean
  llm_ready: boolean
  api_base: string
  api_key_configured: boolean
  default_k: number
  default_min_score: number
}

export type DocumentInfo = {
  name: string
  type: string
  size_bytes: number
  characters: number
  chunks: number
  modified: string
  status: string
}

export type DocumentList = {
  documents: DocumentInfo[]
  total_documents: number
  total_chunks: number
  corpus_ok: boolean
  embedding_model: string
  dim: number
  built_at: string
  message: string
}

export type UploadStatus = 'uploading' | 'processing' | 'done' | 'error'

export type UploadItem = {
  id: string
  name: string
  progress: number
  status: UploadStatus
  message?: string
}

/** The `meta` SSE event only has retrieval_s; generation_s arrives with `done`. */
export type Timings = { retrieval_s?: number; generation_s?: number }

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  abstained?: boolean
  baseline?: string
  timings?: Timings
  topScore?: number
  error?: string
}

export type StreamEvent =
  | { type: 'meta'; sources: Source[]; abstained: boolean; top_score: number; timings: Timings }
  | { type: 'token'; text: string }
  | { type: 'baseline'; text: string }
  | { type: 'done'; answer: string; abstained: boolean; timings: Timings }
  | { type: 'error'; message: string }
