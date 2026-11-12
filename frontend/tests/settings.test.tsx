import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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
const show = () => render(<MemoryRouter><Settings /></MemoryRouter>)

it('requires both email and DELETE and supports cancellation', async () => {
  show()
  fireEvent.click(await screen.findByText('Delete my account…'))
  fireEvent.change(screen.getByLabelText('Type DELETE to confirm'), { target: { value: 'DELETE' } })
  expect((screen.getByText('Permanently delete my account') as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByText('Keep my account'))
  expect(mocks.deleteAccount).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText('Delete my account…'))
  fireEvent.change(screen.getByLabelText('Confirm your account email'), { target: { value: 'owner@example.com' } })
  fireEvent.change(screen.getByLabelText('Type DELETE to confirm'), { target: { value: 'DELETE' } })
  fireEvent.click(screen.getByText('Permanently delete my account'))
  await waitFor(() => expect(mocks.deleteAccount).toHaveBeenCalledWith('owner@example.com', 'DELETE'))
  expect(await screen.findByRole('status')).toHaveProperty('textContent', expect.stringContaining('Deletion is in progress'))
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
  expect(screen.queryByText('Delete my account…')).toBeNull()
})
it('shows backend refusal without claiming success', async () => {
  mocks.deleteAccount.mockRejectedValue({ response: { status: 409, data: { detail: 'Wait for your imports to finish.' } } })
  show()
  fireEvent.click(await screen.findByText('Delete my account…'))
  fireEvent.change(screen.getByLabelText('Confirm your account email'), { target: { value: 'owner@example.com' } })
  fireEvent.change(screen.getByLabelText('Type DELETE to confirm'), { target: { value: 'DELETE' } })
  fireEvent.click(screen.getByText('Permanently delete my account'))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Wait for your imports to finish.')
  expect(mocks.signOut).not.toHaveBeenCalled()
})
