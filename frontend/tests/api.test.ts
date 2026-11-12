import { afterEach, expect, it, vi } from 'vitest'
const auth = vi.hoisted(() => ({ getAccessToken: vi.fn() }))
vi.mock('../src/auth/client', () => auth)
import api, { sendMessageStream } from '../src/services/api'
afterEach(() => vi.unstubAllGlobals())
it('obtains a current token for every API request and account switch', async () => {
  auth.getAccessToken.mockResolvedValueOnce('account-a').mockResolvedValueOnce('account-b')
  const headers: unknown[] = []
  const adapter = async (config: any) => {
    headers.push(config.headers.Authorization)
    return { data: [], status: 200, statusText: 'OK', headers: {}, config }
  }
  await api.get('/repositories', { adapter }); await api.get('/repositories', { adapter })
  expect(headers).toEqual(['Bearer account-a', 'Bearer account-b'])
})
it('does not send an API request without a session', async () => {
  auth.getAccessToken.mockRejectedValueOnce(new Error('Please sign in'))
  const adapter = vi.fn()
  await expect(api.get('/repositories', { adapter })).rejects.toThrow('Please sign in')
  expect(adapter).not.toHaveBeenCalled()
})
it('authenticates streaming chat requests too', async () => {
  auth.getAccessToken.mockResolvedValueOnce('chat-token')
  const fetchMock = vi.fn().mockResolvedValue(new Response('data: {"type":"done"}\n\n'))
  vi.stubGlobal('fetch', fetchMock)
  const done = vi.fn()
  await sendMessageStream('repo-a', 'Explain', undefined, undefined, undefined, undefined, done)
  expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer chat-token')
  expect(done).toHaveBeenCalledOnce()
})

it('reports a truncated reply instead of claiming it was saved', async () => {
  auth.getAccessToken.mockResolvedValueOnce('chat-token')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('data: {"type":"token","content":"partial"}\n\n')))
  const done = vi.fn(), error = vi.fn(), token = vi.fn()
  await sendMessageStream('repo-a', 'Explain', undefined, token, undefined, undefined, done, error)
  expect(token).toHaveBeenCalledWith('partial')
  expect(done).not.toHaveBeenCalled()
  expect(error.mock.calls[0][0]).toContain('interrupted')
})
it('handles split UTF-8 events and only confirms a server-completed reply', async () => {
  auth.getAccessToken.mockResolvedValueOnce('chat-token')
  const bytes = new TextEncoder().encode('data: {"type":"meta","conversation_id":"c"}\n\ndata: {"type":"token","content":"café"}\n\ndata: {"type":"done"}\n\n')
  const body = new ReadableStream({ start(controller) {
    for (const byte of bytes) controller.enqueue(new Uint8Array([byte]))
    controller.close()
  } })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body)))
  const done = vi.fn(), error = vi.fn(), token = vi.fn(), meta = vi.fn()
  await sendMessageStream('repo-a', 'Explain', undefined, token, undefined, meta, done, error)
  expect(token).toHaveBeenCalledWith('café')
  expect(meta).toHaveBeenCalledWith({ type: 'meta', conversation_id: 'c' })
  expect(done).toHaveBeenCalledOnce()
  expect(error).not.toHaveBeenCalled()
})
it('surfaces provider errors and does not mark failed replies as completed', async () => {
  auth.getAccessToken.mockResolvedValueOnce('chat-token')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('data: {"type":"error","message":"Your question was saved, but the reply failed."}\n\n')))
  const done = vi.fn(), error = vi.fn()
  await sendMessageStream('repo-a', 'Explain', undefined, undefined, undefined, undefined, done, error)
  expect(done).not.toHaveBeenCalled()
  expect(error.mock.calls[0][0]).toContain('question was saved')
})
