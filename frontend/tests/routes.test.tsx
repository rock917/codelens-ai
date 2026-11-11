import React, { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import App from '../src/App'
const mock = vi.hoisted(() => ({ session: null as any }))
vi.mock('../src/auth/AuthProvider', () => ({
  AuthProvider: ({ children }: any) => children,
  useAuth: () => ({ session: mock.session, loading: false }),
}))
vi.mock('../src/auth/client', () => ({ supabase: null }))
vi.mock('../src/components/layout/Sidebar', () => ({ default: () => <p>Private navigation</p> }))
vi.mock('../src/pages/Dashboard', () => ({ default: () => <p>Private dashboard</p> }))
vi.mock('../src/pages/Repositories', () => ({ default: () => {
  const [selected, setSelected] = useState(false)
  return <button onClick={() => setSelected(true)}>{selected ? 'Selected private repository' : 'Choose repository'}</button>
} }))
afterEach(() => { cleanup(); mock.session = null; window.history.replaceState({}, '', '/') })
it('redirects a direct dashboard URL to login before rendering private content', () => {
  window.history.replaceState({}, '', '/repositories')
  render(<App />)
  expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeTruthy()
  expect(screen.queryByText('Private navigation')).toBeNull()
  expect(window.location.pathname).toBe('/login')
})
it('remounts private content on account change and removes it on logout', () => {
  window.history.replaceState({}, '', '/repositories')
  mock.session = { user: { id: 'a' } }
  const view = render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Choose repository' }))
  expect(screen.getByText('Selected private repository')).toBeTruthy()
  mock.session = { user: { id: 'b' } }; view.rerender(<App />)
  expect(screen.getByText('Choose repository')).toBeTruthy()
  expect(screen.queryByText('Selected private repository')).toBeNull()
  mock.session = null; view.rerender(<App />)
  expect(screen.queryByText('Private navigation')).toBeNull()
  expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeTruthy()
})
