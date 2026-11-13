import React from 'react'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import DocumentView from '../src/components/DocumentView'
import type { DocumentData } from '../src/components/DocumentView'

afterEach(cleanup)
const base: DocumentData = { content: '', cells: [], sections: [], warnings: [], valid: true, searchable: true, kernel: null, analysis_label: 'JSON validated; no code health score' }

it('renders formatted JSON with an explicit unscored validation status', () => {
  render(<DocumentView document={{ ...base, content: '{\n  "enabled": true\n}' }} language="json" highlightLine={2} />)
  expect(screen.getByText('Indexed and searchable')).toBeTruthy()
  expect(screen.getByText('JSON validated; no code health score')).toBeTruthy()
  expect(document.getElementById('line-2')).toBeTruthy()
})

it('renders notebook cells safely with preserved source line references', () => {
  const view: DocumentData = { ...base, kernel: 'python', analysis_label: 'Python code cells scanned; other cells excluded', cells: [
    { number: 1, cell_type: 'markdown', source: '# Forecast\n![tracking](https://example.com/track.png)\n<script>alert(1)</script>', start_line: 2, end_line: 4, header_line: 1, analysis_supported: false, reason: null },
    { number: 2, cell_type: 'code', source: 'eval(value)', start_line: 7, end_line: 7, header_line: 6, analysis_supported: true, reason: null },
  ] }
  render(<DocumentView document={view} language="notebook" highlightLine={7} />)
  expect(screen.getByText('Forecast')).toBeTruthy()
  expect(screen.getByText(/Cell 2/)).toBeTruthy()
  expect(screen.getByText(/Health analysis supported/)).toBeTruthy()
  expect(document.querySelector('img')).toBeNull()
  expect(document.querySelector('script')).toBeNull()
  expect(document.getElementById('line-7')).toBeTruthy()
  fireEvent.click(screen.getByText(/Markdown source/))
  expect(document.getElementById('line-2')).toBeTruthy()
})

it('shows invalid and empty documents without claiming they are searchable', () => {
  const { rerender } = render(<DocumentView document={{ ...base, valid: false, searchable: false, warnings: ['Expected a Jupyter notebook in nbformat 4'] }} language="notebook" highlightLine={null} />)
  expect(screen.getByText('Not indexed: validation failed')).toBeTruthy()
  expect(screen.getByText('Expected a Jupyter notebook in nbformat 4')).toBeTruthy()
  rerender(<DocumentView document={{ ...base, searchable: false }} language="notebook" highlightLine={null} />)
  expect(screen.getByText('Valid document; no searchable content')).toBeTruthy()
  expect(screen.getByText('This notebook has no cells.')).toBeTruthy()
})
