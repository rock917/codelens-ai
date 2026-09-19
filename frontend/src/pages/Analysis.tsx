import { useEffect, useState } from 'react'
import {
  Shield, AlertTriangle, XCircle,
  CheckCircle, Info, RefreshCw,
  GitBranch, FileCode, ChevronRight,
  Zap, Filter
} from 'lucide-react'
import TopBar from '../components/layout/TopBar'
import {
  getRepositories, triggerAnalysis,
  getIssues, getAnalysisSummary
} from '../services/api'
import type { Repository, AnalysisIssue, AnalysisSummary } from '../types'

function SeverityBadge({ severity }: { severity: string }) {
  const config: Record<string, { color: string, bg: string, border: string, icon: any }> = {
    CRITICAL: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)', icon: XCircle },
    HIGH:     { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)', icon: AlertTriangle },
    MEDIUM:   { color: '#6366f1', bg: 'rgba(99,102,241,0.12)', border: 'rgba(99,102,241,0.3)', icon: Info },
    LOW:      { color: '#64748b', bg: 'rgba(100,116,139,0.12)', border: 'rgba(100,116,139,0.3)', icon: Info },
  }
  const c = config[severity] || config.LOW
  const Icon = c.icon
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '3px 8px', borderRadius: '9999px', fontSize: '11px',
      fontWeight: '600', background: c.bg, color: c.color,
      border: `1px solid ${c.border}`
    }}>
      <Icon size={10} />
      {severity}
    </span>
  )
}

function IssueTypeTag({ type }: { type: string }) {
  const label = type.replace(/_/g, ' ')
  return (
    <span style={{
      fontSize: '10px', padding: '2px 8px', borderRadius: '4px',
      background: 'var(--bg-elevated)', color: 'var(--text-muted)',
      border: '1px solid var(--border)', fontFamily: 'monospace',
      textTransform: 'uppercase', letterSpacing: '0.03em'
    }}>
      {label}
    </span>
  )
}

function HealthRing({ score }: { score: number }) {
  const color = score >= 80 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#ef4444'
  const radius = 40
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score / 100) * circumference

  return (
    <div style={{ position: 'relative', width: '100px', height: '100px' }}>
      <svg width="100" height="100" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="50" cy="50" r={radius}
          fill="none" stroke="var(--border)" strokeWidth="8" />
        <circle cx="50" cy="50" r={radius}
          fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center'
      }}>
        <span style={{ fontSize: '20px', fontWeight: '800', color, fontFamily: 'monospace' }}>
          {score}
        </span>
        <span style={{ fontSize: '9px', color: 'var(--text-muted)', fontWeight: '600' }}>
          HEALTH
        </span>
      </div>
    </div>
  )
}

function StatBox({ label, value, color }: { label: string, value: number, color: string }) {
  return (
    <div style={{
      flex: 1, padding: '16px', borderRadius: '8px',
      background: `${color}10`, border: `1px solid ${color}25`,
      textAlign: 'center'
    }}>
      <div style={{
        fontSize: '24px', fontWeight: '800',
        color, fontFamily: 'monospace', lineHeight: 1
      }}>
        {value}
      </div>
      <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px', fontWeight: '600' }}>
        {label}
      </div>
    </div>
  )
}

export default function Analysis() {
  const [repos, setRepos] = useState<Repository[]>([])
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null)
  const [issues, setIssues] = useState<AnalysisIssue[]>([])
  const [summary, setSummary] = useState<AnalysisSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [severityFilter, setSeverityFilter] = useState<string>('ALL')
  const [expandedIssue, setExpandedIssue] = useState<string | null>(null)

  useEffect(() => { loadRepos() }, [])

  async function loadRepos() {
    try {
      const res = await getRepositories()
      const ready = res.data.filter((r: Repository) => r.status === 'READY')
      setRepos(ready)
      if (ready.length > 0) {
        await selectRepo(ready[0])
      }
    } catch (err) {
      console.error(err)
    }
  }

  async function selectRepo(repo: Repository) {
    setSelectedRepo(repo)
    setLoading(true)
    setIssues([])
    setSummary(null)
    try {
      const [issuesRes, summaryRes] = await Promise.all([
        getIssues(repo.id),
        getAnalysisSummary(repo.id)
      ])
      setIssues(issuesRes.data)
      setSummary(summaryRes.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  async function handleRunAnalysis() {
    if (!selectedRepo) return
    setRunning(true)
    try {
      await triggerAnalysis(selectedRepo.id)
      // Wait a moment then reload
      setTimeout(async () => {
        await selectRepo(selectedRepo)
        setRunning(false)
      }, 3000)
    } catch (err) {
      console.error(err)
      setRunning(false)
    }
  }

  const filteredIssues = severityFilter === 'ALL'
    ? issues
    : issues.filter(i => i.severity === severityFilter)

  const severities = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <TopBar title="Code Analysis" subtitle="Security, complexity and code quality" />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Left sidebar */}
        <div style={{
          width: '220px', minWidth: '220px',
          borderRight: '1px solid var(--border)',
          background: 'var(--bg-surface)',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden'
        }}>
          <div style={{ padding: '12px', borderBottom: '1px solid var(--border)' }}>
            <div style={{
              fontSize: '10px', color: 'var(--text-muted)',
              textTransform: 'uppercase', letterSpacing: '0.05em',
              marginBottom: '8px', fontWeight: '600'
            }}>
              Repository
            </div>
            {repos.map(repo => (
              <button key={repo.id} onClick={() => selectRepo(repo)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '8px 10px', borderRadius: '6px', border: 'none',
                  cursor: 'pointer', width: '100%', textAlign: 'left',
                  background: selectedRepo?.id === repo.id ? 'var(--primary-glow)' : 'transparent',
                  color: selectedRepo?.id === repo.id ? 'var(--primary)' : 'var(--text-muted)',
                  fontSize: '12px', fontWeight: '500', transition: 'all 0.15s'
                }}
                onMouseEnter={e => {
                  if (selectedRepo?.id !== repo.id)
                    e.currentTarget.style.background = 'var(--bg-elevated)'
                }}
                onMouseLeave={e => {
                  if (selectedRepo?.id !== repo.id)
                    e.currentTarget.style.background = 'transparent'
                }}
              >
                <GitBranch size={13} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {repo.name}
                </span>
              </button>
            ))}
          </div>

          {/* Issue type breakdown */}
          {summary && (
            <div style={{ padding: '12px', flex: 1, overflow: 'auto' }}>
              <div style={{
                fontSize: '10px', color: 'var(--text-muted)',
                textTransform: 'uppercase', letterSpacing: '0.05em',
                marginBottom: '8px', fontWeight: '600'
              }}>
                Issue Types
              </div>
              {Object.entries(summary.by_type)
                .sort(([, a], [, b]) => b - a)
                .map(([type, count]) => (
                  <div key={type} style={{
                    display: 'flex', alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '5px 0', borderBottom: '1px solid var(--border)'
                  }}>
                    <span style={{
                      fontSize: '10px', color: 'var(--text-muted)',
                      fontFamily: 'monospace',
                      overflow: 'hidden', textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap', maxWidth: '140px'
                    }}>
                      {type.replace(/_/g, ' ')}
                    </span>
                    <span style={{
                      fontSize: '11px', color: 'var(--text)',
                      fontWeight: '700', fontFamily: 'monospace',
                      flexShrink: 0
                    }}>
                      {count}
                    </span>
                  </div>
                ))}
            </div>
          )}
        </div>

        {/* Main content */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {!selectedRepo && (
            <div style={{
              flex: 1, display: 'flex', alignItems: 'center',
              justifyContent: 'center', color: 'var(--text-muted)'
            }}>
              <Shield size={48} style={{ opacity: 0.3 }} />
            </div>
          )}

          {selectedRepo && (
            <>
              {/* Summary bar */}
              <div style={{
                padding: '16px 24px',
                borderBottom: '1px solid var(--border)',
                background: 'var(--bg-surface)',
                display: 'flex', alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                  {summary && <HealthRing score={summary.health_score} />}
                  <div>
                    {summary && (
                      <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
                        <StatBox label="CRITICAL" value={summary.by_severity.CRITICAL || 0} color="#ef4444" />
                        <StatBox label="HIGH" value={summary.by_severity.HIGH || 0} color="#f59e0b" />
                        <StatBox label="MEDIUM" value={summary.by_severity.MEDIUM || 0} color="#6366f1" />
                        <StatBox label="LOW" value={summary.by_severity.LOW || 0} color="#64748b" />
                      </div>
                    )}
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      {issues.length} total issues in{' '}
                      <span style={{ color: 'var(--text)', fontWeight: '600' }}>
                        {selectedRepo.name}
                      </span>
                    </div>
                  </div>
                </div>

                <button
                  className="btn-primary"
                  onClick={handleRunAnalysis}
                  disabled={running}
                  style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  {running
                    ? <><RefreshCw size={13} style={{ animation: 'spin 1s linear infinite' }} /> Running...</>
                    : <><Zap size={13} /> Run Analysis</>
                  }
                </button>
              </div>

              {/* Severity filter */}
              <div style={{
                padding: '12px 24px',
                borderBottom: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', gap: '8px',
                background: 'var(--bg-surface)'
              }}>
                <Filter size={12} color="var(--text-muted)" />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginRight: '4px' }}>
                  Filter:
                </span>
                {severities.map(sev => (
                  <button key={sev} onClick={() => setSeverityFilter(sev)}
                    style={{
                      padding: '4px 12px', borderRadius: '9999px',
                      border: '1px solid',
                      borderColor: severityFilter === sev ? 'var(--primary)' : 'var(--border)',
                      background: severityFilter === sev ? 'var(--primary-glow)' : 'transparent',
                      color: severityFilter === sev ? 'var(--primary)' : 'var(--text-muted)',
                      cursor: 'pointer', fontSize: '11px', fontWeight: '600',
                      transition: 'all 0.15s'
                    }}>
                    {sev}
                    {sev !== 'ALL' && summary && (
                      <span style={{ marginLeft: '4px', opacity: 0.7 }}>
                        ({summary.by_severity[sev] || 0})
                      </span>
                    )}
                    {sev === 'ALL' && (
                      <span style={{ marginLeft: '4px', opacity: 0.7 }}>
                        ({issues.length})
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {/* Issues list */}
              <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px' }}>

                {loading && (
                  <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
                    <RefreshCw size={20} color="var(--primary)"
                      style={{ animation: 'spin 1s linear infinite' }} />
                  </div>
                )}

                {!loading && filteredIssues.length === 0 && (
                  <div style={{
                    display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                    padding: '60px', textAlign: 'center'
                  }}>
                    <CheckCircle size={40} color="var(--success)"
                      style={{ marginBottom: '12px' }} />
                    <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '6px' }}>
                      {issues.length === 0 ? 'No issues found yet' : 'No issues at this severity'}
                    </h3>
                    <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                      {issues.length === 0
                        ? 'Run analysis to detect security issues, code smells and complexity problems'
                        : `Try a different filter — ${issues.length} total issues exist`}
                    </p>
                    {issues.length === 0 && (
                      <button className="btn-primary"
                        style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}
                        onClick={handleRunAnalysis}>
                        <Zap size={13} /> Run Analysis
                      </button>
                    )}
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {filteredIssues.map(issue => (
                    <div key={issue.id}
                      className="card"
                      style={{
                        padding: '0',
                        cursor: 'pointer',
                        border: expandedIssue === issue.id
                          ? '1px solid var(--border-bright)'
                          : '1px solid var(--border)',
                        transition: 'all 0.15s'
                      }}
                      onClick={() => setExpandedIssue(
                        expandedIssue === issue.id ? null : issue.id
                      )}
                    >
                      {/* Issue header */}
                      <div style={{
                        padding: '12px 16px',
                        display: 'flex', alignItems: 'center',
                        gap: '12px'
                      }}>
                        {/* Severity indicator */}
                        <div style={{
                          width: '3px', height: '40px', borderRadius: '2px',
                          flexShrink: 0,
                          background: issue.severity === 'CRITICAL' ? '#ef4444'
                            : issue.severity === 'HIGH' ? '#f59e0b'
                            : issue.severity === 'MEDIUM' ? '#6366f1' : '#64748b'
                        }} />

                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            display: 'flex', alignItems: 'center',
                            gap: '8px', marginBottom: '4px', flexWrap: 'wrap'
                          }}>
                            <SeverityBadge severity={issue.severity} />
                            <IssueTypeTag type={issue.issue_type} />
                          </div>
                          <div style={{
                            fontSize: '13px', color: 'var(--text)',
                            fontWeight: '500', marginBottom: '4px'
                          }}>
                            {issue.message}
                          </div>
                          <div style={{
                            display: 'flex', alignItems: 'center',
                            gap: '6px', fontSize: '11px', color: 'var(--text-muted)'
                          }}>
                            <FileCode size={10} />
                            <span style={{ fontFamily: 'monospace' }}>
                              {issue.file_path.split('/').pop()}
                            </span>
                            {issue.line && (
                              <>
                                <ChevronRight size={10} />
                                <span style={{ fontFamily: 'monospace', color: 'var(--primary)' }}>
                                  Line {issue.line}
                                </span>
                              </>
                            )}
                          </div>
                        </div>

                        <ChevronRight
                          size={14} color="var(--text-muted)"
                          style={{
                            transform: expandedIssue === issue.id ? 'rotate(90deg)' : 'none',
                            transition: 'transform 0.2s', flexShrink: 0
                          }}
                        />
                      </div>

                      {/* Expanded details */}
                      {expandedIssue === issue.id && (
                        <div className="animate-fade-in" style={{
                          padding: '12px 16px',
                          borderTop: '1px solid var(--border)',
                          background: 'var(--bg-elevated)'
                        }}>
                          <div style={{ marginBottom: '12px' }}>
                            <div style={{
                              fontSize: '10px', color: 'var(--text-muted)',
                              fontWeight: '600', textTransform: 'uppercase',
                              letterSpacing: '0.05em', marginBottom: '4px'
                            }}>
                              File Path
                            </div>
                            <code style={{
                              fontSize: '12px', color: 'var(--primary)',
                              fontFamily: 'monospace',
                              background: 'var(--bg-base)',
                              padding: '4px 8px', borderRadius: '4px',
                              border: '1px solid var(--border)'
                            }}>
                              {issue.file_path}
                              {issue.line ? `:${issue.line}` : ''}
                            </code>
                          </div>

                          <div style={{
                            padding: '12px', borderRadius: '6px',
                            background: 'var(--bg-base)',
                            border: '1px solid var(--border-bright)',
                            display: 'flex', gap: '10px', alignItems: 'flex-start'
                          }}>
                            <Zap size={14} color="var(--primary)" style={{ marginTop: '1px', flexShrink: 0 }} />
                            <div>
                              <div style={{
                                fontSize: '11px', color: 'var(--primary)',
                                fontWeight: '600', marginBottom: '4px'
                              }}>
                                Suggestion
                              </div>
                              <div style={{ fontSize: '12px', color: 'var(--text)', lineHeight: '1.5' }}>
                                {issue.suggestion}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}