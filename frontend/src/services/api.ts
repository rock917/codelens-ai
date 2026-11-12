import { getAccessToken } from '../auth/client'
import axios from 'axios'

export const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
})
api.interceptors.request.use(async config => {
  config.headers.Authorization = `Bearer ${await getAccessToken()}`
  return config
})

// ── Repository ──────────────────────────────────────────────
export const getDeletionStatus = () => api.get('/account/deletion')
export const deleteAccount = (email: string, confirmation: string) =>
  api.delete('/account/deletion', { data: { email, confirmation } })

export const uploadRepository = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/repositories/upload', form)
}

export const ingestGithub = (url: string, name?: string, confirmedRevision?: string) =>
  api.post('/repositories/github', { url, name, confirmed_revision: confirmedRevision })

export const getAnalysisUsage = () => api.get('/repositories/usage')

export const getRepositories = () =>
  api.get('/repositories')

export const getRepository = (id: string) =>
  api.get(`/repositories/${id}`)

export const getRepositoryStatus = (id: string) =>
  api.get(`/repositories/${id}/status`)

export const getRepositoryFiles = (id: string) =>
  api.get(`/repositories/${id}/files`)

export const getRepositoryStats = (id: string) =>
  api.get(`/repositories/${id}/stats`)

export const deleteRepository = (id: string) =>
  api.delete(`/repositories/${id}`)

// ── Symbols ─────────────────────────────────────────────────
export const getSymbols = (repoId: string, type?: string) =>
  api.get(`/symbols/${repoId}`, { params: { symbol_type: type } })

export const getFileSymbols = (fileId: string) =>
  api.get(`/symbols/file/${fileId}`)

// ── Search ──────────────────────────────────────────────────
export const searchCode = (
  repositoryId: string,
  query: string,
  nResults = 10
) => api.post('/search', { repository_id: repositoryId, query, n_results: nResults })

// ── Chat ────────────────────────────────────────────────────
export const sendMessage = (
  repositoryId: string,
  question: string,
  conversationId?: string
) => api.post('/chat', {
  repository_id: repositoryId,
  question,
  conversation_id: conversationId,
})

export const sendMessageStream = async (
  repositoryId: string,
  question: string,
  conversationId?: string,
  onToken: (token: string) => void = () => {},
  onSources: (sources: any[]) => void = () => {},
  onMeta: (meta: any) => void = () => {},
  onDone: () => void = () => {},
  onError: (err: string) => void = () => {},
  signal?: AbortSignal,
) => {
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
  try {
    const token = await getAccessToken()
    const res = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST', signal,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ repository_id: repositoryId, question, conversation_id: conversationId, stream: true }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(typeof body.detail === 'string' ? body.detail : 'Unable to send your question. Please try again.')
    }
    if (!res.body) throw new Error('The reply stream is unavailable.')
    reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let completed = false
    function consume(line: string) {
      if (!line.startsWith('data:')) return
      const raw = line.slice(5).trim()
      if (!raw) return
      const data = JSON.parse(raw)
      if (data.type === 'error') throw new Error(data.message || 'The reply failed.')
      if (data.type === 'token') onToken(data.content)
      else if (data.type === 'sources') onSources(data.sources)
      else if (data.type === 'meta') onMeta(data)
      else if (data.type === 'done') completed = true
    }
    while (!completed) {
      const { done, value } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) consume(line)
      if (done) {
        if (buffer.trim()) consume(buffer)
        break
      }
    }
    if (!completed) throw new Error('Connection interrupted before the reply was saved. Reopen the conversation to check its history.')
    onDone()
  } catch (err) {
    if (!signal?.aborted) onError(err instanceof Error ? err.message : 'Unable to load the reply.')
  } finally {
    await reader?.cancel().catch(() => {})
  }
}
export const getConversations = (repoId: string) =>
  api.get(`/chat/conversations/${repoId}`)

export const getChatHistory = (conversationId: string) =>
  api.get(`/chat/history/${conversationId}`)

export const renameConversation = (conversationId: string, title: string) =>
  api.patch(`/chat/conversations/${conversationId}`, { title })

export const deleteConversation = (conversationId: string) =>
  api.delete(`/chat/conversations/${conversationId}`)

// ── Analysis ─────────────────────────────────────────────────
export const triggerAnalysis = (repoId: string) =>
  api.post(`/analysis/${repoId}`)

export const getIssues = (repoId: string, severity?: string) =>
  api.get(`/analysis/${repoId}/issues`, { params: { severity } })

export const getAnalysisSummary = (repoId: string) =>
  api.get(`/analysis/${repoId}/summary`)

// ── Summary ──────────────────────────────────────────────────
export const getFileSummary = (fileId: string) =>
  api.get(`/summary/file/${fileId}`)

export const getRepositorySummary = (repoId: string) =>
  api.get(`/summary/repository/${repoId}`)

export const getAllFileSummaries = (repoId: string) =>
  api.get(`/summary/files/${repoId}`)

// ── Generation ───────────────────────────────────────────────
export const generateTests = (
  repositoryId: string,
  fileId: string,
  symbolName?: string
) => api.post('/generate/tests', {
  repository_id: repositoryId,
  file_id: fileId,
  symbol_name: symbolName,
})

export const generateDocs = (
  repositoryId: string,
  docType: 'readme' | 'architecture' | 'api'
) => api.post('/generate/docs', {
  repository_id: repositoryId,
  doc_type: docType,
})

export const getTestableSymbols = (repoId: string, fileId: string) =>
  api.get(`/generate/symbols/${repoId}/${fileId}`)
export const getFileContent = (repoId: string, fileId: string) =>
  api.get(`/repositories/${repoId}/files/${fileId}/content`)

export default api
