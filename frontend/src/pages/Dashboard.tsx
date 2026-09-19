import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  GitBranch, FileCode, Layers, AlertTriangle,
  TrendingUp, Clock, Plus, ArrowRight,
  CheckCircle, XCircle, Loader, Zap
} from 'lucide-react'
import TopBar from '../components/layout/TopBar'
import { getRepositories, getAnalysisSummary, getRepositoryStats } from '../services/api'
import type { Repository } from '../types'

function StatCard({ icon: Icon, label, value, color = 'var(--primary)', sub }: any) {
  return (
    <div className="card card-glow" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {label}
        </div>
        <div style={{
          width: '32px', height: '32px', borderRadius: '8px',
          background: `${color}20`,
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <Icon size={15} color={color} />
        </div>
      </div>
      <div style={{ fontSize: '28px', fontWeight: '700', color: 'var(--text)', fontFamily: 'JetBrains Mono, monospace' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>{sub}</div>}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { color: string, icon: any, label: string }> = {
    READY: { color: 'var(--success)', icon: CheckCircle, label: 'Ready' },
    FAILED: { color: 'var(--danger)', icon: XCircle, label: 'Failed' },
    UPLOADING: { color: 'var(--primary)', icon: Loader, label: 'Uploading' },
    PARSING: { color: 'var(--primary)', icon: Loader, label: 'Parsing' },
    INDEXING: { color: 'var(--primary)', icon: Loader, label: 'Indexing' },
    ANALYZING: { color: 'var(--warning)', icon: Loader, label: 'Analyzing' },
  }
  const c = config[status] || config.READY
  const Icon = c.icon
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '2px 8px', borderRadius: '9999px', fontSize: '11px',
      fontWeight: '500', background: `${c.color}15`, color: c.color,
      border: `1px solid ${c.color}30`
    }}>
      <Icon size={10} />
      {c.label}
    </span>
  )
}

function HealthBar({ score }: { score: number }) {
  const color = score >= 80 ? 'var(--success)' : score >= 50 ? 'var(--warning)' : 'var(--danger)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div style={{
        flex: 1, height: '4px', background: 'var(--border)',
        borderRadius: '2px', overflow: 'hidden'
      }}>
        <div style={{
          width: `${score}%`, height: '100%',
          background: color, borderRadius: '2px',
          transition: 'width 0.5s ease'
        }} />
      </div>
      <span style={{ fontSize: '11px', color, fontWeight: '600', minWidth: '28px' }}>
        {score}
      </span>
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [repos, setRepos] = useState<Repository[]>([])
  const [stats, setStats] = useState<Record<string, any>>({})
  const [analysis, setAnalysis] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      const reposRes = await getRepositories()
      const repoList: Repository[] = reposRes.data
      setRepos(repoList)

      // Load stats and analysis for each ready repo
      const statsMap: Record<string, any> = {}
      const analysisMap: Record<string, any> = {}

      await Promise.all(repoList
        .filter(r => r.status === 'READY')
        .map(async (repo) => {
          try {
            const [statsRes, analysisRes] = await Promise.all([
              getRepositoryStats(repo.id),
              getAnalysisSummary(repo.id)
            ])
            statsMap[repo.id] = statsRes.data
            analysisMap[repo.id] = analysisRes.data
          } catch { }
        })
      )

      setStats(statsMap)
      setAnalysis(analysisMap)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const readyRepos = repos.filter(r => r.status === 'READY')
  const totalLOC = Object.values(stats).reduce((sum: number, s: any) => sum + (s?.total_loc || 0), 0)
  const totalFiles = Object.values(stats).reduce((sum: number, s: any) => sum + (s?.total_files || 0), 0)
  const totalIssues = Object.values(analysis).reduce((sum: number, a: any) => sum + (a?.total_issues || 0), 0)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <TopBar title="Dashboard" subtitle="Repository intelligence overview" />

      <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>

        {/* Hero if no repos */}
        {repos.length === 0 && !loading && (
          <div className="animate-fade-in" style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', padding: '80px 24px', textAlign: 'center'
          }}>
            <div style={{
              width: '64px', height: '64px', borderRadius: '16px',
              background: 'linear-gradient(135deg, #6366f1, #a855f7)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              marginBottom: '24px', boxShadow: '0 0 40px rgba(99,102,241,0.3)'
            }}>
              <Zap size={28} color="white" />
            </div>
            <h2 style={{ fontSize: '22px', fontWeight: '700', marginBottom: '8px' }}>
              Welcome to CodeLens AI
            </h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: '24px', maxWidth: '400px' }}>
              Upload a repository to get started. Get AI-powered insights, code analysis, and intelligent chat.
            </p>
            <button className="btn-primary" onClick={() => navigate('/repositories')}
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Plus size={14} /> Upload Repository
            </button>
          </div>
        )}

        {repos.length > 0 && (
          <>
            {/* Stats Grid */}
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
              gap: '16px', marginBottom: '24px'
            }}>
              <StatCard icon={GitBranch} label="Repositories" value={repos.length}
                sub={`${readyRepos.length} ready`} color="var(--primary)" />
              <StatCard icon={FileCode} label="Total Files" value={totalFiles.toLocaleString()}
                sub="across all repos" color="var(--accent)" />
              <StatCard icon={Layers} label="Lines of Code" value={totalLOC.toLocaleString()}
                sub="indexed" color="#22c55e" />
              <StatCard icon={AlertTriangle} label="Issues Found" value={totalIssues}
                sub="across all repos" color="var(--warning)" />
            </div>

            {/* Repository List */}
            <div style={{ marginBottom: '24px' }}>
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: '12px'
              }}>
                <h3 style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text)' }}>
                  Repositories
                </h3>
                <button className="btn-ghost"
                  style={{ fontSize: '12px', padding: '4px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
                  onClick={() => navigate('/repositories')}>
                  View all <ArrowRight size={11} />
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {repos.slice(0, 5).map(repo => {
                  const s = stats[repo.id]
                  const a = analysis[repo.id]
                  const langs = s?.languages ? Object.keys(s.languages) : []

                  return (
                    <div key={repo.id} className="card card-glow"
                      style={{ padding: '16px 20px', cursor: 'pointer' }}
                      onClick={() => navigate('/chat')}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div style={{
                            width: '36px', height: '36px', borderRadius: '8px',
                            background: 'linear-gradient(135deg, #6366f120, #a855f720)',
                            border: '1px solid var(--border-bright)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center'
                          }}>
                            <GitBranch size={16} color="var(--primary)" />
                          </div>
                          <div>
                            <div style={{ fontSize: '13px', fontWeight: '600', marginBottom: '2px' }}>
                              {repo.name}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <StatusBadge status={repo.status} />
                              {langs.slice(0, 3).map(lang => (
                                <span key={lang} style={{
                                  fontSize: '10px', color: 'var(--text-muted)',
                                  background: 'var(--bg-elevated)',
                                  padding: '1px 6px', borderRadius: '4px',
                                  border: '1px solid var(--border)'
                                }}>{lang}</span>
                              ))}
                            </div>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
                          {s && (
                            <>
                              <div style={{ textAlign: 'right' }}>
                                <div style={{ fontSize: '13px', fontWeight: '600', fontFamily: 'monospace' }}>
                                  {s.total_files}
                                </div>
                                <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>files</div>
                              </div>
                              <div style={{ textAlign: 'right' }}>
                                <div style={{ fontSize: '13px', fontWeight: '600', fontFamily: 'monospace' }}>
                                  {s.total_loc?.toLocaleString()}
                                </div>
                                <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>LOC</div>
                              </div>
                              <div style={{ textAlign: 'right' }}>
                                <div style={{ fontSize: '13px', fontWeight: '600', fontFamily: 'monospace' }}>
                                  {s.total_chunks}
                                </div>
                                <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>chunks</div>
                              </div>
                            </>
                          )}
                          {a && (
                            <div style={{ width: '120px' }}>
                              <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                                Health Score
                              </div>
                              <HealthBar score={a.health_score} />
                            </div>
                          )}
                          <ArrowRight size={14} color="var(--text-muted)" />
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Language Breakdown */}
            {Object.keys(stats).length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="card" style={{ padding: '20px' }}>
                  <h3 style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-muted)', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Languages
                  </h3>
                  {Object.entries(
                    Object.values(stats).reduce((acc: Record<string, number>, s: any) => {
                      if (s?.languages) {
                        Object.entries(s.languages).forEach(([lang, count]) => {
                          acc[lang] = (acc[lang] || 0) + (count as number)
                        })
                      }
                      return acc
                    }, {})
                  ).map(([lang, count]) => (
                    <div key={lang} style={{
                      display: 'flex', alignItems: 'center',
                      justifyContent: 'space-between', marginBottom: '8px'
                    }}>
                      <span style={{ fontSize: '12px', color: 'var(--text)' }}>{lang}</span>
                      <span style={{
                        fontSize: '11px', fontFamily: 'monospace',
                        color: 'var(--primary)', fontWeight: '600'
                      }}>{count as number} files</span>
                    </div>
                  ))}
                </div>

                <div className="card" style={{ padding: '20px' }}>
                  <h3 style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-muted)', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Quick Actions
                  </h3>
                  {[
                    { label: 'Upload Repository', icon: Plus, action: () => navigate('/repositories'), color: 'var(--primary)' },
                    { label: 'Start AI Chat', icon: TrendingUp, action: () => navigate('/chat'), color: 'var(--accent)' },
                    { label: 'Run Analysis', icon: AlertTriangle, action: () => navigate('/analysis'), color: 'var(--warning)' },
                    { label: 'Generate Tests', icon: Clock, action: () => navigate('/tests'), color: 'var(--success)' },
                  ].map(({ label, icon: Icon, action, color }) => (
                    <button key={label} onClick={action}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '10px',
                        width: '100%', padding: '8px', borderRadius: '6px',
                        background: 'transparent', border: 'none', cursor: 'pointer',
                        color: 'var(--text)', marginBottom: '4px',
                        transition: 'background 0.15s'
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-elevated)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                      <Icon size={14} color={color} />
                      <span style={{ fontSize: '12px' }}>{label}</span>
                      <ArrowRight size={11} color="var(--text-muted)" style={{ marginLeft: 'auto' }} />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}