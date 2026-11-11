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
