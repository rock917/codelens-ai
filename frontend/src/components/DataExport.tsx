import { useEffect, useRef, useState } from 'react'
import { Download } from 'lucide-react'
import { exportAccountData } from '../services/api'
import { BusyLabel, useToast } from './ui/AccountFeedback'

export default function DataExport({ accountId }: { accountId?: string }) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const request = useRef<AbortController | null>(null)
  const notify = useToast()

  useEffect(() => {
    setBusy(false); setMessage(''); setError('')
    return () => { request.current?.abort(); request.current = null }
  }, [accountId])

  async function download() {
    if (!accountId || request.current) return
    const controller = new AbortController()
    request.current = controller
    setBusy(true); setMessage(''); setError('')
    try {
      const { data } = await exportAccountData(controller.signal)
      if (controller.signal.aborted) return
      const url = URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href = url
      link.download = `codelens-data-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
      try {
        document.body.appendChild(link)
        link.click()
      } finally {
        link.remove()
        // Allow the browser to consume the download before releasing its Blob.
        window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      }
      const success = 'Download started. Check your browser’s downloads for your JSON file.'
      setMessage(success); notify(success, 'success')
    } catch (failure: unknown) {
      if (controller.signal.aborted) return
      const response = (failure as { response?: { data?: unknown } }).response
      let detail = 'Unable to download your data. Please try again.'
      try {
        const body = response?.data instanceof Blob ? JSON.parse(await response.data.text()) : response?.data
        if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') detail = body.detail
      } catch { /* Keep the safe fallback for non-JSON proxy errors. */ }
      if (controller.signal.aborted) return
      setError(detail); notify(detail, 'error')
    } finally {
      if (request.current === controller) {
        request.current = null
        setBusy(false)
      }
    }
  }

  return <section className="card" style={{ padding: 24, marginTop: 24 }} aria-labelledby="export-heading" aria-busy={busy}>
    <h2 id="export-heading">Export your data</h2>
    <p style={{ marginTop: 12, lineHeight: 1.7 }}>Download your account details, repository and file metadata, saved summaries, analysis findings, chats, and usage history as JSON. This uses no analysis credits.</p>
    <p style={{ marginTop: 12, lineHeight: 1.7, color: 'var(--text-muted)' }}>Source-file archives and vector indexes are not included. Saved chats and findings may contain code excerpts. Keep your download private. Downloads are limited to 25 MiB; this is a data copy, not a full backup.</p>
    <button className="account-button" style={{ marginTop: 16 }} disabled={busy || !accountId} onClick={() => void download()}>
      {busy ? <BusyLabel>Preparing export...</BusyLabel> : <><Download size={17} aria-hidden="true" />Download my data (JSON)</>}
    </button>
    {message && <p role="status" style={{ marginTop: 12 }}>{message}</p>}
    {error && <p role="alert" style={{ marginTop: 12 }}>{error}</p>}
  </section>
}
