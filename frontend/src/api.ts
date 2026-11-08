import type {
  AskRequest,
  Connection,
  ConnectionTestResult,
  DocumentList,
  Health,
  Source,
  StreamEvent,
} from './types'

const BASE = '/api'

/** Only non-empty runtime credentials are sent; otherwise the server uses .env. */
function credentials(c: Connection): Partial<AskRequest> {
  return {
    ...(c.apiKey.trim() ? { api_key: c.apiKey.trim() } : {}),
    ...(c.apiBase.trim() ? { api_base: c.apiBase.trim() } : {}),
    ...(c.apiModel.trim() ? { api_model: c.apiModel.trim() } : {}),
  }
}

async function detail(res: Response): Promise<string> {
  let message = `${res.status} ${res.statusText}`
  try {
    const body = await res.json()
    if (body.detail) message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  } catch {
    /* keep the status line */
  }
  return message
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init)
  if (!res.ok) throw new Error(await detail(res))
  return res.json() as Promise<T>
}

export function getHealth(): Promise<Health> {
  return json<Health>('/health')
}

export function getDocuments(): Promise<DocumentList> {
  return json<DocumentList>('/documents')
}

export function deleteDocument(name: string): Promise<DocumentList> {
  return json<DocumentList>(`/documents/${encodeURIComponent(name)}`, { method: 'DELETE' })
}

/** Real upload with byte-level progress. The server rebuilds the FAISS index. */
export function uploadDocuments(
  files: { name: string; content: string }[],
  onProgress: (percent: number) => void,
): Promise<DocumentList> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', BASE + '/documents')
    xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100))
    }
    xhr.onload = () => {
      let body: DocumentList | { detail?: string } | null = null
      try { body = JSON.parse(xhr.responseText) } catch { /* non-JSON error page */ }
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(100)
        resolve(body as DocumentList)
      } else {
        const message = (body as { detail?: string } | null)?.detail || `${xhr.status} ${xhr.statusText}`
        reject(new Error(message))
      }
    }
    xhr.onerror = () => reject(new Error('Network error while uploading. Check that the backend is running.'))
    xhr.send(JSON.stringify({ files }))
  })
}

export function search(question: string, k: number, mode: 'semantic' | 'hybrid'): Promise<{ hits: Source[] }> {
  return json<{ hits: Source[] }>('/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, k, mode }),
  })
}

/** Verify a real API key with one tiny chat-completion call. */
export function testConnection(connection: Connection): Promise<ConnectionTestResult> {
  return json<ConnectionTestResult>('/test-connection', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials(connection)),
  })
}

/** POST /ask and parse the SSE frames. Returns when the stream ends. */
export async function streamAsk(
  req: AskRequest,
  connection: Connection,
  onEvent: (event: StreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(BASE + '/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...req, ...credentials(connection) }),
    signal,
  })
  if (!res.ok) throw new Error(await detail(res))
  if (!res.body) throw new Error('Response body is empty (streaming unsupported).')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let split = buffer.indexOf('\n\n')
    while (split !== -1) {
      const frame = buffer.slice(0, split)
      buffer = buffer.slice(split + 2)
      let name = 'message'
      let data = ''
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) name = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (data) {
        try {
          onEvent({ type: name, ...JSON.parse(data) } as StreamEvent)
        } catch {
          /* ignore malformed frame */
        }
      }
      split = buffer.indexOf('\n\n')
    }
  }
}
