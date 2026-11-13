import { getAccessToken } from '../auth/client'
import { useEffect, useState, useRef } from 'react'
import { getRepositoryStatus, API_BASE_URL } from '../services/api'
import {
  CheckCircle, XCircle, Loader,
  FileCode, Layers, Zap
} from 'lucide-react'

interface ProgressData {
  type: string
  status: string
  total_files: number
  processed_files: number
  total_chunks: number
  message: string
}

interface Props {
  repoId: string
  repoName: string
  onReady?: () => void
}

const STATUS_STEPS = [
  'UPLOADING',
  'PARSING',
  'INDEXING',
  'ANALYZING',
  'READY'
]

function StepIndicator({ step, currentStatus }: {
  step: string
  currentStatus: string
}) {
  const currentIdx = STATUS_STEPS.indexOf(currentStatus)
  const stepIdx = STATUS_STEPS.indexOf(step)
  const isDone = stepIdx < currentIdx || currentStatus === 'READY'
  const isActive = stepIdx === currentIdx && currentStatus !== 'READY'
  const isFailed = currentStatus === 'FAILED'

  const color = isFailed && isActive ? 'var(--danger)'
    : isDone ? 'var(--success)'
    : isActive ? 'var(--primary)'
    : 'var(--text-dim)'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '8px'
    }}>
      <div style={{
        width: '20px', height: '20px', borderRadius: '50%',
        border: `2px solid ${color}`,
        background: isDone ? 'var(--success)' : 'transparent',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0, transition: 'all 0.3s'
      }}>
        {isDone && <CheckCircle size={12} color="var(--bg-base)" />}
        {isActive && !isFailed && (
          <div style={{
            width: '8px', height: '8px', borderRadius: '50%',
            background: 'var(--primary)',
            animation: 'pulse 1.5s infinite'
          }} />
        )}
      </div>
      <span style={{
        fontSize: '11px', fontWeight: isActive ? '600' : '400',
        color: isDone ? 'var(--success)' : isActive ? 'var(--primary)' : 'var(--text-dim)'
      }}>
        {step.charAt(0) + step.slice(1).toLowerCase()}
      </span>
    </div>
  )
}

export default function ProgressTracker({ repoId, repoName, onReady }: Props) {
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [connected, setConnected] = useState(false)
  const onReadyRef = useRef(onReady)
  useEffect(() => { onReadyRef.current = onReady }, [onReady])

  useEffect(() => {
    let disposed = false
    let terminal = false
    let ws: WebSocket | undefined
    let pollTimer: ReturnType<typeof setTimeout> | undefined
    setProgress(null)
    setConnected(false)

    function accept(data: ProgressData) {
      if (disposed || terminal) return
      setProgress(data)
      if (data.status === 'READY' || data.status === 'FAILED') {
        terminal = true
        clearTimeout(pollTimer)
        ws?.close()
        onReadyRef.current?.()
      }
    }

    async function poll() {
      try {
        const { data } = await getRepositoryStatus(repoId)
        accept({ ...data, type: 'status', message: data.error_message || `Status: ${data.status}` })
      } catch {
        // Transient cold starts/network failures must not stop polling.
      } finally {
        if (!disposed && !terminal) pollTimer = setTimeout(poll, 3000)
      }
    }
    void poll()
    try {
      const wsUrl = new URL(API_BASE_URL, window.location.origin)
      wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:'
      wsUrl.pathname = `${wsUrl.pathname.replace(/\/$/, '')}/ws/progress/${repoId}`
      ws = new WebSocket(wsUrl)
      ws.onopen = () => {
        void getAccessToken().then(token => {
          if (!disposed && ws?.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'authenticate', access_token: token }))
          }
        }).catch(() => ws?.close())
      }
      ws.onmessage = (e) => {
        try {
          if (!disposed) setConnected(true)
          accept(JSON.parse(e.data))
        } catch { }
      }
      ws.onclose = ws.onerror = () => { if (!disposed) setConnected(false) }
    } catch (err) {
      console.error('WebSocket error:', err)
    }
    return () => {
      disposed = true
      clearTimeout(pollTimer)
      ws?.close()
    }
  }, [repoId])

  if (!progress) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '10px 14px', borderRadius: '8px',
        background: 'var(--bg-elevated)', border: '1px solid var(--border)'
      }}>
        <Loader size={14} color="var(--primary)"
          style={{ animation: 'spin 1s linear infinite' }} />
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Connecting to {repoName}...
        </span>
      </div>
    )
  }

  const isReady = progress.status === 'READY'
  const isFailed = progress.status === 'FAILED'
  const progressPct = progress.total_files > 0
    ? Math.round((progress.processed_files / progress.total_files) * 100)
    : 0

  return (
    <div className="card animate-fade-in" style={{ padding: '16px' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', marginBottom: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '28px', height: '28px', borderRadius: '7px',
            background: isReady
              ? 'color-mix(in srgb,var(--success) 15%,transparent)'
              : isFailed
              ? 'color-mix(in srgb,var(--danger) 15%,transparent)'
              : 'var(--primary-glow)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            {isReady
              ? <CheckCircle size={14} color="var(--success)" />
              : isFailed
              ? <XCircle size={14} color="var(--danger)" />
              : <Zap size={14} color="var(--primary)"
                  style={{ animation: 'pulse-glow 2s infinite' }} />
            }
          </div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: '700' }}>
              {repoName}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              {progress.message}
            </div>
          </div>
        </div>

        <span style={{
          fontSize: '11px', padding: '3px 10px', borderRadius: '9999px',
          fontWeight: '600',
          background: isReady ? 'color-mix(in srgb,var(--success) 15%,transparent)'
            : isFailed ? 'color-mix(in srgb,var(--danger) 15%,transparent)'
            : 'var(--primary-glow)',
          color: isReady ? 'var(--success)'
            : isFailed ? 'var(--danger)'
            : 'var(--primary)',
          border: `1px solid ${isReady ? 'color-mix(in srgb,var(--success) 30%,transparent)'
            : isFailed ? 'color-mix(in srgb,var(--danger) 30%,transparent)'
            : 'color-mix(in srgb,var(--primary) 30%,transparent)'}`
        }}>
          {progress.status}
        </span>
      </div>

      {/* Progress bar */}
      {!isReady && !isFailed && (
        <div style={{ marginBottom: '14px' }}>
          <div style={{
            height: '4px', background: 'var(--border)',
            borderRadius: '2px', overflow: 'hidden'
          }}>
            <div style={{
              height: '100%',
              width: progress.total_files > 0 ? `${progressPct}%` : '100%',
              background: 'linear-gradient(90deg, var(--primary), var(--accent))',
              borderRadius: '2px',
              animation: progress.total_files === 0 ? 'shimmer 1.5s infinite' : 'none',
              backgroundSize: '200% 100%',
              transition: 'width 0.5s ease'
            }} />
          </div>
          {progress.total_files > 0 && (
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              marginTop: '4px', fontSize: '10px', color: 'var(--text-muted)'
            }}>
              <span>{progress.processed_files} / {progress.total_files} files</span>
              <span>{progressPct}%</span>
            </div>
          )}
        </div>
      )}

      {/* Steps */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
        gap: '4px', marginBottom: '12px'
      }}>
        {STATUS_STEPS.filter(s => s !== 'READY').map(step => (
          <StepIndicator
            key={step}
            step={step}
            currentStatus={progress.status}
          />
        ))}
      </div>

      {/* Stats */}
      {(progress.total_files > 0 || progress.total_chunks > 0) && (
        <div style={{
          display: 'flex', gap: '12px',
          padding: '8px 12px', borderRadius: '6px',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <FileCode size={11} color="var(--primary)" />
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              <span style={{
                fontWeight: '700', color: 'var(--text)',
                fontFamily: 'monospace'
              }}>
                {progress.total_files}
              </span> files
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={11} color="var(--accent)" />
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              <span style={{
                fontWeight: '700', color: 'var(--text)',
                fontFamily: 'monospace'
              }}>
                {progress.total_chunks}
              </span> chunks
            </span>
          </div>
          {connected && (
            <div style={{
              marginLeft: 'auto', display: 'flex',
              alignItems: 'center', gap: '4px'
            }}>
              <div style={{
                width: '5px', height: '5px', borderRadius: '50%',
                background: 'var(--success)'
              }} />
              <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                live
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
