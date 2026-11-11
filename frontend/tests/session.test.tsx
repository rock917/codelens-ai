import React from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import { AuthProvider, useAuth } from '../src/auth/AuthProvider'
const mock = vi.hoisted(() => ({ listener: null as any, unsubscribe: vi.fn() }))
vi.mock('../src/auth/client', () => ({ supabase: { auth: {
  getSession: async () => ({ data: { session: { user: { id: 'user-a' } } }, error: null }),
  onAuthStateChange: (listener: any) => { mock.listener = listener; return { data: { subscription: { unsubscribe: mock.unsubscribe } } } },
} } }))
afterEach(cleanup)
function Account() { const { session, loading } = useAuth(); return <p>{loading ? 'Loading' : session?.user.id || 'Signed out'}</p> }
it('clears identity on logout and switches accounts without retaining the prior user', async () => {
  const view = render(<AuthProvider><Account /></AuthProvider>)
  await screen.findByText('user-a')
  act(() => mock.listener('SIGNED_OUT', null))
  expect(screen.getByText('Signed out')).toBeTruthy()
  act(() => mock.listener('SIGNED_IN', { user: { id: 'user-b' } }))
  expect(screen.getByText('user-b')).toBeTruthy()
  expect(screen.queryByText('user-a')).toBeNull()
  view.unmount(); expect(mock.unsubscribe).toHaveBeenCalledOnce()
})
