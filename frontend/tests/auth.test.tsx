import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Login, AuthCallback, ResetPassword } from '../src/auth/AuthPages'

const mocks = vi.hoisted(() => ({
  state: { session: null as unknown, loading: false },
  auth: {
    signInWithPassword: vi.fn(), signUp: vi.fn(), signInWithOAuth: vi.fn(),
    resetPasswordForEmail: vi.fn(), updateUser: vi.fn(), getSession: vi.fn(),
  },
}))
vi.mock('../src/auth/client', () => ({ supabase: { auth: mocks.auth } }))
vi.mock('../src/auth/AuthProvider', () => ({ useAuth: () => mocks.state }))

afterEach(cleanup)
beforeEach(() => {
  mocks.state.session = null; mocks.state.loading = false
  for (const fn of Object.values(mocks.auth)) fn.mockReset().mockResolvedValue({ error: null })
  window.history.replaceState({}, '', '/')
})
function show(element = <Login />) {
  return render(<MemoryRouter><Routes><Route path="/" element={element} /></Routes></MemoryRouter>)
}

describe('account forms', () => {
  it('submits email and password to Auth', async () => {
    show(); const user = userEvent.setup()
    await user.type(screen.getByLabelText('Email address'), 'friend@example.com')
    await user.type(screen.getByLabelText('Password'), 'a-long-password')
    await user.click(screen.getByRole('button', { name: 'Sign in', exact: true }))
    expect(mocks.auth.signInWithPassword).toHaveBeenCalledWith({ email: 'friend@example.com', password: 'a-long-password' })
  })
  it('creates an account with the confirmation callback', async () => {
    show(); const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'New here? Create an account' }))
    await user.type(screen.getByLabelText('Email address'), 'friend@example.com')
    await user.type(screen.getByLabelText('Password'), 'a-long-password')
    await user.click(screen.getByRole('button', { name: 'Create account', exact: true }))
    expect(mocks.auth.signUp).toHaveBeenCalledWith(expect.objectContaining({
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    }))
    expect(screen.getByRole('status').textContent).toContain('Check your email')
  })
  it.each(['Google', 'GitHub'])('starts %s OAuth with the fixed callback', async provider => {
    show(); await userEvent.click(screen.getByRole('button', { name: `Continue with ${provider}` }))
    expect(mocks.auth.signInWithOAuth).toHaveBeenCalledWith({
      provider: provider.toLowerCase(), options: { redirectTo: `${window.location.origin}/auth/callback` },
    })
  })
  it('shows login errors and permits retry', async () => {
    mocks.auth.signInWithPassword.mockResolvedValue({ error: new Error('Invalid login credentials') })
    show(); const user = userEvent.setup()
    await user.type(screen.getByLabelText('Email address'), 'friend@example.com')
    await user.type(screen.getByLabelText('Password'), 'bad-password')
    await user.click(screen.getByRole('button', { name: 'Sign in', exact: true }))
    expect(screen.getByRole('alert').textContent).toContain('Invalid login credentials')
    expect((screen.getByRole('button', { name: 'Sign in', exact: true }) as HTMLButtonElement).disabled).toBe(false)
  })
  it('sends a reset link without disclosing account existence', async () => {
    show(); const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Forgot password?' }))
    await user.type(screen.getByLabelText('Email address'), 'friend@example.com')
    await user.click(screen.getByRole('button', { name: 'Send reset link' }))
    expect(mocks.auth.resetPasswordForEmail).toHaveBeenCalledWith('friend@example.com', { redirectTo: `${window.location.origin}/auth/callback?next=reset` })
    expect(screen.getByRole('status').textContent).toContain('If an account exists')
  })
  it('rejects an expired callback', async () => {
    mocks.auth.getSession.mockResolvedValue({ data: { session: null }, error: null })
    show(<AuthCallback />)
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('invalid or expired'))
  })
  it('sends recovery callbacks to the password form', async () => {
    window.history.replaceState({}, '', '/auth/callback?next=reset')
    mocks.auth.getSession.mockResolvedValue({ data: { session: { user: { id: 'user-a' } } }, error: null })
    render(<MemoryRouter><Routes><Route path="/" element={<AuthCallback />} /><Route path="/reset-password" element={<p>Recovery destination</p>} /></Routes></MemoryRouter>)
    await screen.findByText('Recovery destination')
  })
  it('updates the password of the authenticated account', async () => {
    mocks.state.session = { user: { id: 'user-a' } }
    show(<ResetPassword />); const user = userEvent.setup()
    await user.type(screen.getByLabelText('New password'), 'another-long-password')
    await user.click(screen.getByRole('button', { name: 'Save password' }))
    expect(mocks.auth.updateUser).toHaveBeenCalledWith({ password: 'another-long-password' })
  })
})
