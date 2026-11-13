import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import TestGen from '../src/pages/TestGen'

const api = vi.hoisted(() => ({ getRepositories: vi.fn(), getRepositoryFiles: vi.fn(), getTestableSymbols: vi.fn(), generateTests: vi.fn() }))
vi.mock('../src/services/api', () => api)
vi.mock('../src/components/layout/TopBar', () => ({ default: () => <header>Tests</header> }))
beforeEach(() => {
  api.getRepositories.mockResolvedValue({ data: [{ id: 'repo', name: 'Example', status: 'READY' }] })
  api.getRepositoryFiles.mockResolvedValue({ data: ['java', 'go', 'cpp'].map(language => ({ id: language, path: `sample.${language}`, language, num_functions: 2 })) })
  api.getTestableSymbols.mockResolvedValue({ data: [
    { id: 'first', name: 'run', signature: 'int run(int n)', start_line: 2, end_line: 4 },
    { id: 'second', name: 'run', signature: 'int run(String n)', start_line: 6, end_line: 8 },
  ] })
  api.generateTests.mockResolvedValue({ data: { generated_tests: 'Proposed tests', file_path: 'sample.java', language: 'java' } })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })

it('offers all three languages and submits the selected overload ID', async () => {
  await act(async () => { render(<TestGen />) })
  for (const name of ['sample.java', 'sample.go', 'sample.cpp']) expect(screen.getByText(name)).toBeTruthy()
  await act(async () => { fireEvent.click(screen.getByText('sample.java')) })
  fireEvent.change(screen.getByRole('combobox', { name: 'Function to test' }), { target: { value: 'second' } })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Generate Tests' })) })
  expect(api.generateTests).toHaveBeenCalledWith('repo', 'java', 'run', 'second')
  expect(screen.getByText('Proposed tests')).toBeTruthy()
  expect(screen.getByText(/Generated tests are suggestions/)).toBeTruthy()
})
