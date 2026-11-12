import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react'
import UsageBanner from '../src/components/UsageBanner'
import { UploadModal } from '../src/pages/Repositories'

const api = vi.hoisted(() => ({ getAnalysisUsage: vi.fn(), ingestGithub: vi.fn(), uploadRepository: vi.fn() }))
vi.mock('../src/services/api', () => api)
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('shows completed and reserved usage separately, with a recoverable error', async () => {
  api.getAnalysisUsage.mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ data: { used: 8, reserved: 2, remaining: 0, limit: 10 } })
  render(<UsageBanner />)
  fireEvent.click(await screen.findByRole('button', { name: 'Retry' }))
  await screen.findByText('8 of 10 lifetime analyses used')
  expect(screen.getByText(/2 in progress · 0 available/)).toBeTruthy()
})

it('requires explicit confirmation of the current revision before a new credit is reserved', async () => {
  api.ingestGithub.mockRejectedValueOnce({ response: { data: { detail: { code: 'revision_confirmation', revision: 'new-sha', message: 'New revision uses one credit.' } } } })
    .mockResolvedValue({ data: { id: 'r2', reused: false, message: 'Import started' } })
  const success = vi.fn()
  render(<UploadModal onClose={vi.fn()} onSuccess={success} />)
  fireEvent.click(screen.getByRole('button', { name: /GitHub URL/ }))
  fireEvent.change(screen.getByPlaceholderText('https://github.com/username/repo'), { target: { value: 'https://github.com/test/repo' } })
  fireEvent.click(screen.getByRole('button', { name: 'Check & Analyze' }))
  const confirm = await screen.findByRole('button', { name: 'Analyze new revision · 1 credit' })
  expect(success).not.toHaveBeenCalled()
  expect(api.ingestGithub).toHaveBeenCalledTimes(1)
  fireEvent.click(confirm)
  await waitFor(() => expect(success).toHaveBeenCalledWith({ id: 'r2', reused: false, message: 'Import started' }))
  expect(api.ingestGithub).toHaveBeenLastCalledWith('https://github.com/test/repo', undefined, 'new-sha')
})

it('renders quota errors and keeps cached-result submissions available', async () => {
  api.ingestGithub.mockRejectedValueOnce({ response: { data: { detail: { code: 'analysis_limit', message: 'All 10 slots are used.' } } } })
    .mockResolvedValue({ data: { id: 'saved', reused: true, message: 'No credit used' } })
  const success = vi.fn()
  render(<UploadModal onClose={vi.fn()} onSuccess={success} />)
  fireEvent.click(screen.getByRole('button', { name: /GitHub URL/ }))
  fireEvent.change(screen.getByPlaceholderText('https://github.com/username/repo'), { target: { value: 'https://github.com/test/repo' } })
  fireEvent.click(screen.getByRole('button', { name: 'Check & Analyze' }))
  await screen.findByText('All 10 slots are used.')
  fireEvent.click(screen.getByRole('button', { name: 'Check & Analyze' }))
  await waitFor(() => expect(success).toHaveBeenCalledWith({ id: 'saved', reused: true, message: 'No credit used' }))
})
