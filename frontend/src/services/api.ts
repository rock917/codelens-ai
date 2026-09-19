import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 60000,
})

// ── Repository ──────────────────────────────────────────────
export const uploadRepository = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/repositories/upload', form)
}

export const ingestGithub = (url: string, name?: string) =>
  api.post('/repositories/github', { url, name })

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

export const sendMessageStream = (
  repositoryId: string,
  question: string,
  conversationId?: string,
  onToken: (token: string) => void = () => {},
  onSources: (sources: any[]) => void = () => {},
  onMeta: (meta: any) => void = () => {},
  onDone: () => void = () => {},
  onError: (err: string) => void = () => {}
) => {
  return fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      repository_id: repositoryId,
      question,
      conversation_id: conversationId,
      stream: true
    })
  }).then(async res => {
    if (!res.ok) throw new Error('Stream request failed')
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (!data) continue

        try {
          const parsed = JSON.parse(data)
          if (parsed.type === 'token') onToken(parsed.content)
          else if (parsed.type === 'sources') onSources(parsed.sources)
          else if (parsed.type === 'meta') onMeta(parsed)
          else if (parsed.type === 'done') onDone()
        } catch { }
      }
    }
  }).catch(err => onError(err.message))
}
export const getConversations = (repoId: string) =>
  api.get(`/chat/conversations/${repoId}`)

export const getChatHistory = (conversationId: string) =>
  api.get(`/chat/history/${conversationId}`)

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