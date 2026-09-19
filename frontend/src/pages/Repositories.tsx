import { useEffect, useState, useRef } from 'react'
import {
  GitBranch, Upload, Trash2,
  CheckCircle, XCircle, Loader, Plus,
  FileCode, Layers, AlertTriangle,
  RefreshCw
} from 'lucide-react'
import TopBar from '../components/layout/TopBar'
import {
  getRepositories, uploadRepository,
  ingestGithub, deleteRepository,
  getRepositoryStats, getAnalysisSummary
} from '../services/api'
import type { Repository } from '../types'
import ProgressTracker from '../components/ProgressTracker'
function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { color: string, icon: any, label: string }> = {
    READY:     { color: '#22c55e', icon: CheckCircle, label: 'Ready' },
    FAILED:    { color: '#ef4444', icon: XCircle,     label: 'Failed' },
    UPLOADING: { color: '#6366f1', icon: Loader,      label: 'Uploading' },
    PARSING:   { color: '#6366f1', icon: Loader,      label: 'Parsing' },
    INDEXING:  { color: '#6366f1', icon: Loader,      label: 'Indexing' },
    ANALYZING: { color: '#f59e0b', icon: Loader,      label: 'Analyzing' },
  }
  const c = config[status] || config.READY
  const Icon = c.icon
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '3px 10px', borderRadius: '9999px', fontSize: '11px',
      fontWeight: '500', background: `${c.color}15`,
      color: c.color, border: `1px solid ${c.color}30`
    }}>
      <Icon size={10} />
      {c.label}
    </span>
  )
}

function UploadModal({ onClose, onSuccess }: { onClose: () => void, onSuccess: () => void }) {
  const [tab, setTab] = useState<'zip' | 'github'>('zip')
  const [githubUrl, setGithubUrl] = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    if (!file.name.endsWith('.zip')) {
      setError('Only ZIP files are supported')
      return
    }
    setUploading(true)
    setError('')
    try {
      await uploadRepository(file)
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function handleGithub() {
    if (!githubUrl.trim()) {
      setError('Please enter a GitHub URL')
      return
    }
    setUploading(true)
    setError('')
    try {
      await ingestGithub(githubUrl.trim())
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to clone repository')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 100, backdropFilter: 'blur(4px)'
    }}>
      <div className="card animate-fade-in" style={{
        width: '480px', padding: '24px',
        border: '1px solid var(--border-bright)',
        boxShadow: '0 0 40px rgba(99,102,241,0.15)'
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
          <div>
            <h2 style={{ fontSize: '15px', fontWeight: '700' }}>Add Repository</h2>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Upload a ZIP or connect a GitHub repo
            </p>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: 'var(--text-muted)',
            cursor: 'pointer', fontSize: '18px', lineHeight: 1
          }}>✕</button>
        </div>

        {/* Tabs */}
        <div style={{
          display: 'flex', gap: '4px', marginBottom: '20px',
          background: 'var(--bg-elevated)', padding: '4px', borderRadius: '8px'
        }}>
          {(['zip', 'github'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              flex: 1, padding: '7px', borderRadius: '6px', border: 'none',
              cursor: 'pointer', fontSize: '12px', fontWeight: '500',
              background: tab === t ? 'var(--bg-surface)' : 'transparent',
              color: tab === t ? 'var(--text)' : 'var(--text-muted)',
              transition: 'all 0.15s',
              boxShadow: tab === t ? '0 1px 4px rgba(0,0,0,0.3)' : 'none'
            }}>
              {t === 'zip' ? '📦 ZIP Upload' : '🐙 GitHub URL'}
            </button>
          ))}
        </div>

        {/* ZIP Upload */}
        {tab === 'zip' && (
          <div
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => {
              e.preventDefault(); setDragging(false)
              const file = e.dataTransfer.files[0]
              if (file) handleFile(file)
            }}
            onClick={() => fileRef.current?.click()}
            style={{
              border: `2px dashed ${dragging ? 'var(--primary)' : 'var(--border-bright)'}`,
              borderRadius: '8px', padding: '40px 24px', textAlign: 'center',
              cursor: 'pointer', transition: 'all 0.2s',
              background: dragging ? 'var(--primary-glow)' : 'var(--bg-elevated)',
            }}>
            <Upload size={32} color={dragging ? 'var(--primary)' : 'var(--text-muted)'}
              style={{ margin: '0 auto 12px' }} />
            <div style={{ fontSize: '13px', fontWeight: '500', marginBottom: '4px' }}>
              Drop your ZIP file here
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              or click to browse · Max 100MB
            </div>
            <input ref={fileRef} type="file" accept=".zip" style={{ display: 'none' }}
              onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
          </div>
        )}

        {/* GitHub URL */}
        {tab === 'github' && (
          <div>
            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
                GitHub Repository URL
              </label>
              <input
                className="input"
                placeholder="https://github.com/username/repo"
                value={githubUrl}
                onChange={e => setGithubUrl(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleGithub()}
              />
            </div>
            <button
              className="btn-primary"
              style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
              onClick={handleGithub}
              disabled={uploading}
            >
              <GitBranch size={14} />
              {uploading ? 'Cloning...' : 'Clone Repository'}
            </button>
          </div>
        )}

        {error && (
          <div style={{
            marginTop: '12px', padding: '8px 12px', borderRadius: '6px',
            background: 'rgba(239,68,68,0.1)', color: '#ef4444',
            fontSize: '12px', border: '1px solid rgba(239,68,68,0.2)'
          }}>
            {error}
          </div>
        )}

        {uploading && (
          <div style={{
            marginTop: '12px', display: 'flex', alignItems: 'center',
            gap: '8px', color: 'var(--primary)', fontSize: '12px'
          }}>
            <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} />
            Processing repository...
          </div>
        )}
      </div>
    </div>
  )
}

export default function Repositories() {
  const [repos, setRepos] = useState<Repository[]>([])
  const [stats, setStats] = useState<Record<string, any>>({})
  const [analysis, setAnalysis] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const pollRef = useRef<any>(null)

  useEffect(() => {
    loadRepos()
    return () => clearInterval(pollRef.current)
  }, [])

  async function loadRepos() {
    try {
      const res = await getRepositories()
      const repoList: Repository[] = res.data
      setRepos(repoList)

      // Load stats for ready repos
      const statsMap: Record<string, any> = {}
      const analysisMap: Record<string, any> = {}
      await Promise.all(
        repoList.filter(r => r.status === 'READY').map(async repo => {
          try {
            const [s, a] = await Promise.all([
              getRepositoryStats(repo.id),
              getAnalysisSummary(repo.id)
            ])
            statsMap[repo.id] = s.data
            analysisMap[repo.id] = a.data
          } catch { }
        })
      )
      setStats(statsMap)
      setAnalysis(analysisMap)

      // Poll if any repo is processing
      const hasProcessing = repoList.some(
        r => !['READY', 'FAILED'].includes(r.status)
      )
      if (hasProcessing) {
        pollRef.current = setTimeout(loadRepos, 3000)
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    if (!confirm('Delete this repository?')) return
    setDeleting(id)
    try {
      await deleteRepository(id)
      await loadRepos()
    } catch (err) {
      console.error(err)
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <TopBar title="Repositories" subtitle="Manage your indexed codebases" />

      <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
        {/* Actions */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {repos.length} {repos.length === 1 ? 'repository' : 'repositories'}
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="btn-ghost"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px' }}
              onClick={loadRepos}>
              <RefreshCw size={13} /> Refresh
            </button>
            <button className="btn-primary"
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              onClick={() => setShowModal(true)}>
              <Plus size={13} /> Add Repository
            </button>
          </div>
        </div>

        {/* Empty state */}
        {!loading && repos.length === 0 && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', padding: '80px 24px', textAlign: 'center'
          }}>
            <GitBranch size={48} color="var(--text-muted)" style={{ marginBottom: '16px' }} />
            <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '8px' }}>No repositories yet</h3>
            <p style={{ color: 'var(--text-muted)', marginBottom: '20px' }}>
              Upload a ZIP file or connect a GitHub repository to get started
            </p>
            <button className="btn-primary"
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              onClick={() => setShowModal(true)}>
              <Plus size={14} /> Add Repository
            </button>
          </div>
        )}

        {/* Repository Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {repos.map(repo => {
            const s = stats[repo.id]
            const a = analysis[repo.id]
            const isProcessing = !['READY', 'FAILED'].includes(repo.status)
            const langs = s?.languages ? Object.entries(s.languages) : []

            return (
              <div key={repo.id} className="card card-glow animate-fade-in"
                style={{ padding: '20px' }}>
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '40px', height: '40px', borderRadius: '10px',
                      background: 'linear-gradient(135deg, #6366f120, #a855f720)',
                      border: '1px solid var(--border-bright)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      <GitBranch size={18} color="var(--primary)" />
                    </div>
                    <div>
                      <div style={{ fontSize: '14px', fontWeight: '700', marginBottom: '4px' }}>
                        {repo.name}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <StatusBadge status={repo.status} />
                        {repo.source_type === 'github' && (
                          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                            🐙 {repo.source_url}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <button onClick={e => handleDelete(repo.id, e)}
                    disabled={deleting === repo.id}
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: 'var(--text-muted)', padding: '4px',
                      borderRadius: '4px', transition: 'color 0.15s'
                    }}
                    onMouseEnter={e => (e.currentTarget.style.color = 'var(--danger)')}
                    onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}>
                    <Trash2 size={14} />
                  </button>
                </div>

                {/* Processing bar — WebSocket live progress */}
                {isProcessing && (
                  <div style={{ marginBottom: '16px' }}>
                    <ProgressTracker
                      repoId={repo.id}
                      repoName={repo.name}
                      onReady={loadRepos}
                    />
                  </div>
                )}

                {/* Stats */}
                {s && (
                  <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
                    gap: '12px', marginBottom: '16px'
                  }}>
                    {[
                      { icon: FileCode, label: 'Files', value: s.total_files },
                      { icon: Layers, label: 'LOC', value: s.total_loc?.toLocaleString() },
                      { icon: Layers, label: 'Chunks', value: s.total_chunks },
                      { icon: FileCode, label: 'Functions', value: s.total_functions },
                      { icon: AlertTriangle, label: 'Issues', value: a?.total_issues || 0 },
                    ].map(({ icon: Icon, label, value }) => (
                      <div key={label} style={{
                        background: 'var(--bg-elevated)', borderRadius: '6px',
                        padding: '10px', border: '1px solid var(--border)'
                      }}>
                        <Icon size={14} style={{ marginBottom: '4px' }} />
                        <div style={{ fontSize: '18px', fontWeight: '700', fontFamily: 'monospace' }}>
                          {value}
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
                          {label}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Languages + health */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {langs.map(([lang, count]) => (
                      <span key={lang} style={{
                        fontSize: '11px', padding: '2px 8px', borderRadius: '4px',
                        background: 'var(--bg-elevated)', color: 'var(--text-muted)',
                        border: '1px solid var(--border)'
                      }}>
                        {lang} · {count as number}
                      </span>
                    ))}
                  </div>

                  {a && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Health</span>
                      <div style={{
                        width: '80px', height: '4px', background: 'var(--border)',
                        borderRadius: '2px', overflow: 'hidden'
                      }}>
                        <div style={{
                          width: `${a.health_score}%`, height: '100%', borderRadius: '2px',
                          background: a.health_score >= 80 ? 'var(--success)' :
                            a.health_score >= 50 ? 'var(--warning)' : 'var(--danger)'
                        }} />
                      </div>
                      <span style={{
                        fontSize: '12px', fontWeight: '700',
                        color: a.health_score >= 80 ? 'var(--success)' :
                          a.health_score >= 50 ? 'var(--warning)' : 'var(--danger)'
                      }}>{a.health_score}</span>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {showModal && (
        <UploadModal
          onClose={() => setShowModal(false)}
          onSuccess={loadRepos}
        />
      )}
    </div>
  )
}