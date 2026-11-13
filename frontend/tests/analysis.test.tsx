import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, fireEvent, act } from '@testing-library/react'
import Analysis from '../src/pages/Analysis'
const api = vi.hoisted(() => ({ getRepositories: vi.fn(), triggerAnalysis: vi.fn(), getIssues: vi.fn(), getAnalysisSummary: vi.fn() }))
vi.mock('../src/services/api', () => api)
vi.mock('../src/components/layout/TopBar', () => ({ default: () => <header>Analysis</header> }))
const summary = (status: string, score: number | null = null) => ({ data: {
  analysis_status: status, health_score: score, by_severity: {}, by_type: {}, total_issues: 0,
  coverage: status === 'COMPLETED' ? { scanned_files: 1, scanned_loc: 20, unsupported_files: 0 } : null,
} })
beforeEach(() => {
  vi.useFakeTimers()
  api.getRepositories.mockResolvedValue({ data: [{ id: 'a', name: 'First', status: 'READY' }, { id: 'b', name: 'Second', status: 'READY' }] })
  api.getIssues.mockResolvedValue({ data: [] })
  api.triggerAnalysis.mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.resetAllMocks() })
it('polls until completion instead of stopping after three seconds', async () => {
  api.getAnalysisSummary.mockResolvedValue(summary('NOT_RUN'))
  await act(async () => { render(<Analysis />) })
  expect(screen.getByText('Not scored')).toBeTruthy()
  fireEvent.click(screen.getAllByRole('button', { name: /Run Analysis/ })[0])
  api.getAnalysisSummary.mockResolvedValue(summary('RUNNING'))
  await act(async () => { await Promise.resolve() })
  await act(async () => { await vi.advanceTimersByTimeAsync(4000) })
  expect(screen.getByRole('button', { name: /Running/ }).hasAttribute('disabled')).toBe(true)
  api.getAnalysisSummary.mockResolvedValue(summary('COMPLETED', 100))
  await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
  expect(screen.getByText('100')).toBeTruthy()
  expect(screen.getByText('No findings in scanned files')).toBeTruthy()
  const count = api.getAnalysisSummary.mock.calls.length
  await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
  expect(api.getAnalysisSummary.mock.calls.length).toBe(count)
})
it('ignores a stale response after switching repositories', async () => {
  let finish: (value: unknown) => void = () => {}
  api.getAnalysisSummary.mockImplementation((id: string) => id === 'a' ? new Promise(resolve => { finish = resolve }) : Promise.resolve(summary('COMPLETED', 75)))
  await act(async () => { render(<Analysis />) })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Second' })) })
  expect(screen.getByText('75')).toBeTruthy()
  await act(async () => { finish(summary('COMPLETED', 12)) })
  expect(screen.queryByText('12')).toBeNull()
  expect(screen.getByText('75')).toBeTruthy()
})

it('shows a real cache hit and offers an explicit fresh scan', async () => {
  api.getAnalysisSummary.mockResolvedValue(summary('COMPLETED', 80))
  api.triggerAnalysis.mockResolvedValue({ data: { cached: true } })
  await act(async () => { render(<Analysis />) })
  await act(async () => { fireEvent.click(screen.getAllByRole('button', { name: 'Run Analysis' })[0]) })
  expect(api.triggerAnalysis).toHaveBeenLastCalledWith('a', false)
  expect(screen.getByText('Using saved results. No new scan was needed.')).toBeTruthy()
  api.triggerAnalysis.mockResolvedValue({ data: { cached: false } })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Run fresh scan' })) })
  expect(api.triggerAnalysis).toHaveBeenLastCalledWith('a', true)
  expect(screen.queryByText('Using saved results. No new scan was needed.')).toBeNull()
})
it('blocks repeated submissions while the trigger request is pending', async () => {
  api.getAnalysisSummary.mockResolvedValue(summary('COMPLETED', 80))
  let finish!: (value: unknown) => void
  api.triggerAnalysis.mockImplementation(() => new Promise(resolve => { finish = resolve }))
  await act(async () => { render(<Analysis />) })
  const button = screen.getAllByRole('button', { name: 'Run Analysis' })[0]
  await act(async () => { fireEvent.click(button); fireEvent.click(button) })
  expect(api.triggerAnalysis).toHaveBeenCalledTimes(1)
  await act(async () => { finish({ data: { cached: true } }) })
})
