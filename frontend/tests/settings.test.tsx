import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, act } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import Settings from '../src/pages/Settings'

const mocks = vi.hoisted(() => ({ getDeletionStatus: vi.fn(), deleteAccount: vi.fn(), signOut: vi.fn() }))
vi.mock('../src/services/api', () => mocks)
vi.mock('../src/auth/client', () => ({ supabase: { auth: { signOut: mocks.signOut } } }))
vi.mock('../src/auth/AuthProvider', () => ({ useAuth: () => ({ session: { user: { id: 'owner', email: 'owner@example.com' } } }) }))
beforeEach(() => {
  mocks.getDeletionStatus.mockResolvedValue({ data: { enabled: true, pending: false, recent_sign_in: true } })
  mocks.deleteAccount.mockResolvedValue({ data: { status: 'pending' } })
  mocks.signOut.mockResolvedValue({ error: null })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })
const show = () => render(<MemoryRouter initialEntries={['/settings']}><Routes><Route path="/settings" element={<Settings />} /><Route path="/login" element={<p>Public login</p>} /></Routes></MemoryRouter>)

it('requires both email and DELETE and supports cancellation', async () => {
  show()
  fireEvent.click(await screen.findByText('Delete Account'))
  fireEvent.change(screen.getByLabelText('Type DELETE to confirm'), { target: { value: 'DELETE' } })
  expect((screen.getByText('Permanently Delete Account') as HTMLButtonElement).disabled).toBe(true)
  expect(screen.getByText('Enter your account email in the field above to enable deletion.')).toBeTruthy()
  expect(screen.getByPlaceholderText('Enter your account email')).toBeTruthy()
  fireEvent.click(screen.getByText('Cancel'))
  expect(mocks.deleteAccount).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText('Delete Account'))
  fireEvent.change(screen.getByLabelText('Confirm your account email'), { target: { value: 'owner@example.com' } })
  fireEvent.change(screen.getByLabelText('Type DELETE to confirm'), { target: { value: 'DELETE' } })
  expect((screen.getByText('Permanently Delete Account') as HTMLButtonElement).disabled).toBe(false)
  fireEvent.click(screen.getByText('Permanently Delete Account'))
  await waitFor(() => expect(mocks.deleteAccount).toHaveBeenCalledWith('owner@example.com', 'DELETE'))
  expect((await screen.findByText(/Deletion is in progress/)).getAttribute('role')).toBe('status')
})
it('requires reauthentication for an old sign-in', async () => {
  mocks.getDeletionStatus.mockResolvedValue({ data: { enabled: true, pending: false, recent_sign_in: false } })
  show()
  fireEvent.click(await screen.findByText('Sign out and sign in again'))
  await waitFor(() => expect(mocks.signOut).toHaveBeenCalledWith({ scope: 'local' }))
  expect(mocks.deleteAccount).not.toHaveBeenCalled()
})
it('does not offer deletion until server configuration is ready', async () => {
  mocks.getDeletionStatus.mockResolvedValue({ data: { enabled: false, pending: false, recent_sign_in: true } })
  show()
  await screen.findByText(/Self-service deletion is not available yet/)
  expect(screen.queryByText('Delete Account')).toBeNull()
})
it('shows backend refusal without claiming success', async () => {
  mocks.deleteAccount.mockRejectedValue({ response: { status: 409, data: { detail: 'Wait for your imports to finish.' } } })
  show()
  fireEvent.click(await screen.findByText('Delete Account'))
  fireEvent.change(screen.getByLabelText('Confirm your account email'), { target: { value: 'owner@example.com' } })
  fireEvent.change(screen.getByLabelText('Type DELETE to confirm'), { target: { value: 'DELETE' } })
  fireEvent.click(screen.getByText('Permanently Delete Account'))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Wait for your imports to finish.')
  expect(mocks.signOut).not.toHaveBeenCalled()
})

it('keeps pending deletion on Settings without redirecting or clearing the session', async () => {
  show()
  fireEvent.click(await screen.findByText('Delete Account'))
  fireEvent.change(screen.getByLabelText('Confirm your account email'), { target: { value: 'owner@example.com' } })
  fireEvent.change(screen.getByLabelText('Type DELETE to confirm'), { target: { value: 'DELETE' } })
  fireEvent.click(screen.getByText('Permanently Delete Account'))
  await screen.findByText(/Deletion is in progress/)
  expect(mocks.signOut).not.toHaveBeenCalled()
  expect(screen.queryByText('Public login')).toBeNull()
})

it('blocks duplicate submission and Escape while awaiting confirmed deletion', async () => {
  let finish!: (result: { data: { status: string } }) => void
  mocks.deleteAccount.mockImplementation(() => new Promise(resolve => { finish = resolve }))
  show(); const user = userEvent.setup()
  await user.click(await screen.findByText('Delete Account'))
  await user.type(screen.getByLabelText('Confirm your account email'), 'owner@example.com')
  await user.type(screen.getByLabelText('Type DELETE to confirm'), 'DELETE')
  await user.click(screen.getByText('Permanently Delete Account'))
  const busy = screen.getByRole('button', { name: 'Deleting account...' }) as HTMLButtonElement
  expect(busy.disabled).toBe(true)
  await user.click(busy); await user.keyboard('{Escape}')
  expect(screen.getByRole('dialog')).toBeTruthy()
  expect(mocks.deleteAccount).toHaveBeenCalledTimes(1)
  expect(mocks.signOut).not.toHaveBeenCalled()
  await act(async () => finish({ data: { status: 'deleted' } }))
  await screen.findByText('Public login')
  expect(mocks.signOut).toHaveBeenCalledWith({ scope: 'local' })
})

it('allows Escape before submission and resets the confirmation fields', async () => {
  show(); const user = userEvent.setup()
  await user.click(await screen.findByText('Delete Account'))
  await user.type(screen.getByLabelText('Type DELETE to confirm'), 'DELETE')
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(mocks.deleteAccount).not.toHaveBeenCalled()
  await user.click(screen.getByText('Delete Account'))
  expect((screen.getByLabelText('Type DELETE to confirm') as HTMLInputElement).value).toBe('')
})
