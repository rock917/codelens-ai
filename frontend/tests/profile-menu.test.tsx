import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ProfileMenu from '../src/components/layout/ProfileMenu'
import { ToastProvider } from '../src/components/ui/AccountFeedback'
const mocks = vi.hoisted(() => ({ signOut: vi.fn() }))
vi.mock('../src/auth/client', () => ({ supabase: { auth: mocks } }))
vi.mock('../src/auth/AuthProvider', () => ({ useAuth: () => ({ session: { user: { email: 'friend@example.com' } } }) }))
beforeEach(() => mocks.signOut.mockResolvedValue({ error: null }))
afterEach(() => { cleanup(); vi.resetAllMocks() })
function show() {
  return render(<MemoryRouter><ToastProvider><Routes><Route path="/" element={<ProfileMenu />} /><Route path="/login" element={<p>Public login</p>} /></Routes></ToastProvider></MemoryRouter>)
}
async function openDialog() {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Open profile menu' }))
  await user.click(screen.getByRole('button', { name: 'Sign Out' }))
  return user
}
it('opens a confirmation, focuses Cancel and restores focus on Escape', async () => {
  show(); const user = await openDialog()
  expect(screen.getByRole('dialog', { name: 'Sign out of CodeLens_AI?' })).toBeTruthy()
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cancel' }))
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(mocks.signOut).not.toHaveBeenCalled()
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Open profile menu' }))
})
it('waits for sign-out, blocks duplicate clicks and unsafe dismissal, then redirects', async () => {
  let finish!: (result: { error: null }) => void
  mocks.signOut.mockImplementation(() => new Promise(resolve => { finish = resolve }))
  show(); const user = await openDialog()
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Sign Out' }))
  const busy = screen.getByRole('button', { name: 'Signing out...' }) as HTMLButtonElement
  expect(busy.disabled).toBe(true)
  await user.click(busy); await user.keyboard('{Escape}')
  expect(screen.getByRole('dialog')).toBeTruthy()
  expect(mocks.signOut).toHaveBeenCalledTimes(1)
  expect(screen.queryByText('Public login')).toBeNull()
  await act(async () => finish({ error: null }))
  await screen.findByText('Public login')
  expect(screen.getByRole('status').textContent).toContain('You have signed out')
})
it('keeps the dialog open and shows an error when Supabase refuses sign-out', async () => {
  mocks.signOut.mockResolvedValue({ error: new Error('offline') })
  show(); const user = await openDialog()
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Sign Out' }))
  expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveProperty('textContent', 'Unable to sign out. Please try again.')
  expect(screen.queryByText('Public login')).toBeNull()
})
