import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Explorer from '../src/pages/Explorer'

const api = vi.hoisted(() => ({ getRepositories: vi.fn(), getRepositoryFiles: vi.fn(), getFileSymbols: vi.fn(), getFileSummary: vi.fn(), getFileContent: vi.fn() }))
vi.mock('../src/services/api', () => api)
vi.mock('../src/components/layout/TopBar', () => ({ default: () => <header>Explorer</header> }))
beforeEach(() => {
  api.getRepositories.mockResolvedValue({ data: [{ id: 'repo', name: 'Example', status: 'READY' }] })
  api.getRepositoryFiles.mockResolvedValue({ data: [{ id: 'file', path: 'sample.py', language: 'python', importance_level: 'LOW', loc: 2 }] })
  api.getFileSymbols.mockResolvedValue({ data: [] })
  api.getFileContent.mockResolvedValue({ data: { content: 'print("hello")' } })
  api.getFileSummary.mockResolvedValue({ data: { summary: 'Saved summary', cached: true } })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })

it.each(['java', 'go', 'cpp'])('shows %s parse coverage and receiver methods without a local type declaration', async language => {
  api.getRepositoryFiles.mockResolvedValue({ data: [{ id: 'file', path: `sample.${language}`, language, importance_level: 'LOW', loc: 2 }] })
  api.getFileContent.mockResolvedValue({ data: { content: 'int run() { return 1; }', parsing: { status: 'partial', diagnostics: ['Partial parse: file excluded from health scoring.'] } } })
  api.getFileSymbols.mockResolvedValue({ data: [{ id: 'method', name: 'run', type: 'method', parent_name: 'Elsewhere', signature: 'run()', start_line: 1, end_line: 1, complexity: 1 }] })
  await act(async () => { render(<MemoryRouter><Explorer /></MemoryRouter>) })
  await act(async () => { fireEvent.click(screen.getByText(`sample.${language}`)) })
  expect(screen.getByText('Partial parse: file excluded from health scoring.')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: /Symbols/ }))
  expect(screen.getByText('run()')).toBeTruthy()
})

it('still shows document validation when summary generation rejects invalid content', async () => {
  api.getRepositoryFiles.mockResolvedValue({ data: [{ id: 'file', path: 'broken.json', language: 'json', importance_level: 'LOW', loc: 0 }] })
  api.getFileSummary.mockRejectedValue(new Error('No indexed content'))
  api.getFileContent.mockResolvedValue({ data: { content: '', document: { valid: false, searchable: false, content: '', warnings: ['Invalid JSON'], cells: [], sections: [], kernel: null, analysis_label: 'Not scored' } } })
  await act(async () => { render(<MemoryRouter><Explorer /></MemoryRouter>) })
  await act(async () => { fireEvent.click(screen.getByText('broken.json')) })
  expect(screen.getByText('Not indexed: validation failed')).toBeTruthy()
  expect(screen.getByText('Invalid JSON')).toBeTruthy()
})

async function openSummary() {
  await act(async () => { render(<MemoryRouter><Explorer /></MemoryRouter>) })
  await act(async () => { fireEvent.click(screen.getByText('sample.py')) })
  fireEvent.click(screen.getByRole('button', { name: 'AI Summary' }))
}

it('shows reuse and refreshes the selected summary with force=true', async () => {
  await openSummary()
  expect(screen.getByText('Using saved results')).toBeTruthy()
  api.getFileSummary.mockResolvedValue({ data: { summary: 'Fresh summary', cached: false } })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Refresh summary' })) })
  expect(api.getFileSummary).toHaveBeenLastCalledWith('file', true)
  expect(screen.getByText('Fresh summary')).toBeTruthy()
  expect(screen.getByText('Summary refreshed')).toBeTruthy()
})

it('retains previous results when refresh fails and blocks duplicate clicks', async () => {
  await openSummary()
  let reject!: (error: Error) => void
  api.getFileSummary.mockImplementation(() => new Promise((_resolve, fail) => { reject = fail }))
  const button = screen.getByRole('button', { name: 'Refresh summary' })
  await act(async () => { fireEvent.click(button); fireEvent.click(button) })
  expect(api.getFileSummary).toHaveBeenCalledTimes(2) // Initial load + one refresh.
  expect(button.hasAttribute('disabled')).toBe(true)
  await act(async () => { reject(new Error('Unavailable')) })
  expect(screen.getByText('Saved summary')).toBeTruthy()
  expect(screen.getByText(/Could not refresh/)).toBeTruthy()
})
