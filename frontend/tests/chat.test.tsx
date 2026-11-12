import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import Chat from '../src/pages/Chat'
const api = vi.hoisted(() => ({ getRepositories: vi.fn(), getConversations: vi.fn(), getChatHistory: vi.fn(), sendMessageStream: vi.fn(), renameConversation: vi.fn(), deleteConversation: vi.fn() }))
vi.mock('../src/services/api', () => api)
vi.mock('../src/components/layout/TopBar', () => ({ default: () => <header>Chat</header> }))
const conversation = { id: 'c1', repository_id: 'r1', title: 'Architecture', created_at: '2026-11-12T01:00:00Z', updated_at: '2026-11-12T02:00:00Z', is_generating: false }
const history = [{ id: 'm1', role: 'user', content: 'Explain the entry point', created_at: '2026-11-12T01:00:00Z' }, { id: 'm2', role: 'assistant', content: 'The entry point is app.py.', sources: [], created_at: '2026-11-12T01:00:01Z' }]
beforeEach(() => {
  api.getRepositories.mockResolvedValue({ data: [{ id: 'r1', name: 'Repo one', status: 'READY' }, { id: 'r2', name: 'Repo two', status: 'READY' }] })
  api.getConversations.mockImplementation((id: string) => Promise.resolve({ data: id === 'r1' ? [conversation] : [] }))
  api.getChatHistory.mockResolvedValue({ data: history })
  api.renameConversation.mockResolvedValue({ data: {} })
  api.deleteConversation.mockResolvedValue({ status: 204 })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })
it('reopens saved messages on remount and renames a conversation', async () => {
  const view = render(<Chat />)
  await screen.findByText('The entry point is app.py.')
  view.unmount()
  render(<Chat />)
  await screen.findByText('The entry point is app.py.')
  fireEvent.click(screen.getByRole('button', { name: 'Rename Architecture' }))
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'My architecture notes' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save title' }))
  await waitFor(() => expect(api.renameConversation).toHaveBeenCalledWith('c1', 'My architecture notes'))
})
it('requires a confirmation before deleting saved messages', async () => {
  render(<Chat />)
  await screen.findByText('The entry point is app.py.')
  fireEvent.click(screen.getByRole('button', { name: 'Delete Architecture' }))
  expect(api.deleteConversation).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Keep conversation' }))
  expect(api.deleteConversation).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Delete Architecture' }))
  api.getConversations.mockResolvedValue({ data: [] })
  fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }))
  await waitFor(() => expect(api.deleteConversation).toHaveBeenCalledWith('c1'))
  await waitFor(() => expect(screen.queryByText('The entry point is app.py.')).toBeNull())
})
it('ignores delayed history after changing repositories', async () => {
  let finish: (value: unknown) => void = () => {}
  api.getChatHistory.mockReturnValue(new Promise(resolve => { finish = resolve }))
  render(<Chat />)
  await waitFor(() => expect(api.getChatHistory).toHaveBeenCalled())
  fireEvent.change(screen.getByLabelText('Repository'), { target: { value: 'r2' } })
  await screen.findByText('Ask about Repo two')
  await act(async () => { finish({ data: history }) })
  expect(screen.queryByText('The entry point is app.py.')).toBeNull()
  expect(screen.queryByRole('button', { name: 'Rename Architecture' })).toBeNull()
})
it('cancels a stream on navigation and ignores its late callbacks', async () => {
  let args: any[] = [], finish = () => {}
  api.sendMessageStream.mockImplementation((...values: any[]) => { args = values; return new Promise<void>(resolve => { finish = resolve }) })
  render(<Chat />)
  await screen.findByText('The entry point is app.py.')
  fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'Follow up' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
  await waitFor(() => expect(args.length).toBe(9))
  fireEvent.change(screen.getByLabelText('Repository'), { target: { value: 'r2' } })
  await screen.findByText('Ask about Repo two')
  expect(args[8].aborted).toBe(true)
  await act(async () => { args[3]('Late answer'); args[5]({ conversation_id: 'c1' }); args[6](); finish() })
  expect(screen.queryByText('Late answer')).toBeNull()
  expect(screen.queryByRole('button', { name: 'Rename Architecture' })).toBeNull()
})
it('displays saved history after the server confirms completion', async () => {
  api.sendMessageStream.mockImplementation(async (_r, _q, _c, token, _sources, meta, done) => {
    meta({ conversation_id: 'c1' }); token('New reply');
    api.getChatHistory.mockResolvedValue({ data: [...history, { id: 'm3', role: 'user', content: 'Follow up' }, { id: 'm4', role: 'assistant', content: 'New reply', sources: [] }] });
    done()
  })
  render(<Chat />)
  await screen.findByText('The entry point is app.py.')
  fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'Follow up' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
  await screen.findByText('New reply')
  await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Saved'))
  expect(api.sendMessageStream.mock.calls[0].slice(0, 3)).toEqual(['r1', 'Follow up', 'c1'])
})
