import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import DataExport from '../src/components/DataExport'

const mocks = vi.hoisted(() => ({ exportAccountData: vi.fn() }))
vi.mock('../src/services/api', () => mocks)
const click = vi.fn()
beforeEach(() => {
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(click)
  vi.stubGlobal('URL', { createObjectURL: vi.fn().mockReturnValue('blob:private-download'), revokeObjectURL: vi.fn() })
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.clearAllMocks() })

it('downloads the real response only after completion and prevents duplicate requests', async () => {
  let finish!: (value: { data: Blob }) => void
  mocks.exportAccountData.mockImplementation(() => new Promise(resolve => { finish = resolve }))
  render(<DataExport accountId="a" />)
  fireEvent.click(screen.getByRole('button', { name: /Download my data/ }))
  const busy = screen.getByRole('button', { name: 'Preparing export...' }) as HTMLButtonElement
  expect(busy.disabled).toBe(true)
  fireEvent.click(busy)
  expect(mocks.exportAccountData).toHaveBeenCalledTimes(1)
  expect(click).not.toHaveBeenCalled()
  const blob = new Blob(['{"account":{"id":"a"}}'], { type: 'application/json' })
  await act(async () => finish({ data: blob }))
  expect(URL.createObjectURL).toHaveBeenCalledWith(blob)
  expect(click).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('status').textContent).toContain('Download started')
  expect(document.querySelector('a[download]')).toBeNull()
})

it('shows backend errors without starting a download and allows retry', async () => {
  const blob = new Blob()
  blob.text = async () => JSON.stringify({ detail: 'Please wait before downloading another export.' })
  mocks.exportAccountData.mockRejectedValue({ response: { data: blob } })
  render(<DataExport accountId="a" />)
  fireEvent.click(screen.getByRole('button', { name: /Download my data/ }))
  expect((await screen.findByRole('alert')).textContent).toContain('Please wait')
  expect(click).not.toHaveBeenCalled()
  expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(false)
})

it('aborts on account change and ignores stale responses', async () => {
  let finish!: (value: { data: Blob }) => void
  mocks.exportAccountData.mockImplementation(() => new Promise(resolve => { finish = resolve }))
  const view = render(<DataExport accountId="a" />)
  fireEvent.click(screen.getByRole('button'))
  const signal = mocks.exportAccountData.mock.calls[0][0] as AbortSignal
  view.rerender(<DataExport accountId="b" />)
  expect(signal.aborted).toBe(true)
  await act(async () => finish({ data: new Blob(['private account a data']) }))
  expect(click).not.toHaveBeenCalled()
  expect(screen.queryByRole('status')).toBeNull()
})

it('cancels in-flight work on unmount and disables signed-out downloads', () => {
  mocks.exportAccountData.mockImplementation(() => new Promise(() => {}))
  const view = render(<DataExport />)
  expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true)
  view.rerender(<DataExport accountId="a" />)
  fireEvent.click(screen.getByRole('button'))
  const signal = mocks.exportAccountData.mock.calls[0][0] as AbortSignal
  view.unmount()
  expect(signal.aborted).toBe(true)
})
