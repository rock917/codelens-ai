import { useEffect, useState, useRef } from 'react'
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

  const color = isFailed && isActive ? '#ef4444'
    : isDone ? '#22c55e'
    : isActive ? '#6366f1'
    : '#334155'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '8px'
    }}>
      <div style={{
        width: '20px', height: '20px', borderRadius: '50%',
        border: `2px solid ${color}`,
        background: isDone ? '#22c55e' : 'transparent',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0, transition: 'all 0.3s'
      }}>
        {isDone && <CheckCircle size={12} color="white" />}
        {isActive && !isFailed && (
          <div style={{
            width: '8px', height: '8px', borderRadius: '50%',
            background: '#6366f1',
            animation: 'pulse 1.5s infinite'
          }} />
        )}
      </div>
      <span style={{
        fontSize: '11px', fontWeight: isActive ? '600' : '400',
        color: isDone ? '#22c55e' : isActive ? '#6366f1' : '#334155'
      }}>
        {step.charAt(0) + step.slice(1).toLowerCase()}
      </span>
    </div>
  )
}

export default function ProgressTracker({ repoId, repoName, onReady }: Props) {
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [repoId])

  function connect() {
    try {
      const wsUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace('https://', 'wss://')
  .replace('http://', 'ws://')
const ws = new WebSocket(`${wsUrl}/ws/progress/${repoId}`)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)

      ws.onmessage = (e) => {
        try {
          const data: ProgressData = JSON.parse(e.data)
          setProgress(data)
          if (data.status === 'READY' && onReady) {
            setTimeout(onReady, 1000)
          }
        } catch { }
      }

      ws.onclose = () => setConnected(false)
      ws.onerror = () => setConnected(false)
    } catch (err) {
      console.error('WebSocket error:', err)
    }
  }

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
              ? 'rgba(34,197,94,0.15)'
              : isFailed
              ? 'rgba(239,68,68,0.15)'
              : 'var(--primary-glow)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            {isReady
              ? <CheckCircle size={14} color="#22c55e" />
              : isFailed
              ? <XCircle size={14} color="#ef4444" />
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
          background: isReady ? 'rgba(34,197,94,0.15)'
            : isFailed ? 'rgba(239,68,68,0.15)'
            : 'var(--primary-glow)',
          color: isReady ? '#22c55e'
            : isFailed ? '#ef4444'
            : 'var(--primary)',
          border: `1px solid ${isReady ? 'rgba(34,197,94,0.3)'
            : isFailed ? 'rgba(239,68,68,0.3)'
            : 'rgba(99,102,241,0.3)'}`
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
              background: 'linear-gradient(90deg, #6366f1, #a855f7)',
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
                background: '#22c55e'
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