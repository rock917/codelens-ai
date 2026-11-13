import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../src/theme/ThemeProvider'
import Appearance from '../src/theme/Appearance'
import { DEFAULT_THEME, LAST_THEME_KEY, cacheTheme, initialTheme, readTheme, themeKey } from '../src/theme/preferences'

const mocks = vi.hoisted(() => ({
  auth: { session: null as null | { user: { id: string; user_metadata: Record<string, unknown> } }, loading: false },
  updateUser: vi.fn(), getSession: vi.fn(),
}))
vi.mock('../src/auth/AuthProvider', () => ({ useAuth: () => mocks.auth }))
vi.mock('../src/auth/client', () => ({ supabase: { auth: { updateUser: mocks.updateUser, getSession: mocks.getSession } } }))
beforeEach(() => {
  localStorage.clear()
  mocks.auth.session = null
  mocks.getSession.mockImplementation(async () => ({ data: { session: mocks.auth.session } }))
  mocks.updateUser.mockResolvedValue({ error: null })
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.clearAllMocks() })
const app = () => <MemoryRouter><ThemeProvider><Appearance /></ThemeProvider></MemoryRouter>
const select = (name: string) => fireEvent.click(screen.getByRole('button', { name }))

it('defaults to Midnight Violet and restores a guest choice after a refresh', () => {
  const view = render(app())
  expect(screen.getByRole('button', { name: 'Midnight Violet' }).getAttribute('aria-pressed')).toBe('true')
  select('Arctic Light')
  expect(document.documentElement.dataset.theme).toBe('arctic-light')
  expect(document.documentElement.style.colorScheme).toBe('light')
  expect(mocks.updateUser).not.toHaveBeenCalled()
  view.unmount(); render(app())
  expect(screen.getByRole('button', { name: 'Arctic Light' }).getAttribute('aria-pressed')).toBe('true')
})
it('loads the account preference and switches accounts without leaking the previous choice', async () => {
  mocks.auth.session = { user: { id: 'a', user_metadata: { codelens_theme: 'cyber-cyan', name: 'A' } } }
  const view = render(app())
  expect(document.documentElement.dataset.theme).toBe('cyber-cyan')
  select('Arctic Light')
  await waitFor(() => expect(mocks.updateUser).toHaveBeenCalledWith({ data: { codelens_theme: 'arctic-light' } }))
  await screen.findByText('Saved to your account.')
  mocks.auth.session = { user: { id: 'b', user_metadata: { codelens_theme: 'emerald-matrix' } } }
  view.rerender(app())
  expect(document.documentElement.dataset.theme).toBe('emerald-matrix')
  expect(readTheme('a')?.theme).toBe('arctic-light')
})
it('applies immediately, serializes rapid selections and saves the latest choice last', async () => {
  mocks.auth.session = { user: { id: 'a', user_metadata: {} } }
  let finish!: (value: { error: null }) => void
  mocks.updateUser.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  render(app()); select('Cyber Cyan')
  await waitFor(() => expect(mocks.updateUser).toHaveBeenCalledTimes(1))
  select('Emerald Matrix'); select('Arctic Light')
  expect(document.documentElement.dataset.theme).toBe('arctic-light')
  expect(mocks.updateUser).toHaveBeenCalledTimes(1)
  await act(async () => finish({ error: null }))
  await screen.findByText('Saved to your account.')
  expect(mocks.updateUser).toHaveBeenLastCalledWith({ data: { codelens_theme: 'arctic-light' } })
  expect(readTheme('a')).toEqual({ theme: 'arctic-light', pending: false })
})
it('retains a failed save across refresh and allows retry without claiming account sync', async () => {
  mocks.auth.session = { user: { id: 'a', user_metadata: { codelens_theme: DEFAULT_THEME } } }
  mocks.updateUser.mockResolvedValueOnce({ error: new Error('offline') })
  const view = render(app()); select('Cyber Cyan')
  await screen.findByText(/Account sync failed/)
  expect(readTheme('a')?.pending).toBe(true)
  view.unmount(); render(app())
  expect(document.documentElement.dataset.theme).toBe('cyber-cyan')
  select('Cyber Cyan'); await screen.findByText('Saved to your account.')
  expect(readTheme('a')?.pending).toBe(false)
})
it('rejects invalid cache and metadata values and tolerates blocked storage', () => {
  localStorage.setItem(LAST_THEME_KEY, 'invalid')
  localStorage.setItem(themeKey(), '{broken')
  expect(initialTheme()).toBe(DEFAULT_THEME)
  mocks.auth.session = { user: { id: 'a', user_metadata: { codelens_theme: 'unknown' } } }
  render(app())
  expect(document.documentElement.dataset.theme).toBe(DEFAULT_THEME)
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  expect(cacheTheme('arctic-light')).toBe(false)
})
it('reflects another tab’s change for the same account only', () => {
  render(app())
  cacheTheme('cyber-cyan')
  fireEvent(window, new StorageEvent('storage', { key: themeKey('another-user') }))
  expect(document.documentElement.dataset.theme).toBe(DEFAULT_THEME)
  fireEvent(window, new StorageEvent('storage', { key: themeKey() }))
  expect(document.documentElement.dataset.theme).toBe('cyber-cyan')
})
