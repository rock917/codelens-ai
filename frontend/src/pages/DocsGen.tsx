import { useEffect, useState } from 'react'
import {
  FileText, GitBranch, Loader,
  Zap, Copy, CheckCheck,
  BookOpen, Code2, Layout
} from 'lucide-react'
import TopBar from '../components/layout/TopBar'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getRepositories, generateDocs } from '../services/api'
import type { Repository } from '../types'

const DOC_TYPES = [
  {
    id: 'readme',
    label: 'README',
    icon: BookOpen,
    description: 'Complete README with features, setup, and usage',
    color: '#22c55e'
  },
  {
    id: 'architecture',
    label: 'Architecture',
    icon: Layout,
    description: 'System design, components, and data flow',
    color: '#6366f1'
  },
  {
    id: 'api',
    label: 'API Docs',
    icon: Code2,
    description: 'API endpoints, functions, and parameters',
    color: '#a855f7'
  },
]

export default function DocsGen() {
  const [repos, setRepos] = useState<Repository[]>([])
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null)
  const [selectedType, setSelectedType] = useState('readme')
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => { loadRepos() }, [])

  async function loadRepos() {
    try {
      const res = await getRepositories()
      const ready = res.data.filter((r: Repository) => r.status === 'READY')
      setRepos(ready)
      if (ready.length > 0) setSelectedRepo(ready[0])
    } catch (err) { console.error(err) }
  }

  async function handleGenerate() {
    if (!selectedRepo) return
    setGenerating(true)
    setResult(null)
    try {
      const res = await generateDocs(
        selectedRepo.id,
        selectedType as 'readme' | 'architecture' | 'api'
      )
      setResult(res.data)
    } catch (err) { console.error(err) }
    finally { setGenerating(false) }
  }

  async function handleCopy() {
    if (!result?.content) return
    await navigator.clipboard.writeText(result.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <TopBar title="Docs Generator" subtitle="Generate documentation for your codebase" />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Left panel */}
        <div style={{
          width: '260px', minWidth: '260px',
          borderRight: '1px solid var(--border)',
          background: 'var(--bg-surface)',
          display: 'flex', flexDirection: 'column',
          padding: '12px', gap: '16px', overflow: 'auto'
        }}>
          {/* Repo */}
          <div>
            <div style={{
              fontSize: '10px', color: 'var(--text-muted)',
              textTransform: 'uppercase', letterSpacing: '0.05em',
              marginBottom: '8px', fontWeight: '600'
            }}>Repository</div>
            {repos.map(repo => (
              <button key={repo.id} onClick={() => { setSelectedRepo(repo); setResult(null) }}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '7px 10px', borderRadius: '6px', border: 'none',
                  cursor: 'pointer', width: '100%', textAlign: 'left',
                  background: selectedRepo?.id === repo.id ? 'var(--primary-glow)' : 'transparent',
                  color: selectedRepo?.id === repo.id ? 'var(--primary)' : 'var(--text-muted)',
                  fontSize: '12px', fontWeight: '500', transition: 'all 0.15s', marginBottom: '2px'
                }}
                onMouseEnter={e => { if (selectedRepo?.id !== repo.id) e.currentTarget.style.background = 'var(--bg-elevated)' }}
                onMouseLeave={e => { if (selectedRepo?.id !== repo.id) e.currentTarget.style.background = 'transparent' }}
              >
                <GitBranch size={12} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {repo.name}
                </span>
              </button>
            ))}
          </div>

          {/* Doc type */}
          <div>
            <div style={{
              fontSize: '10px', color: 'var(--text-muted)',
              textTransform: 'uppercase', letterSpacing: '0.05em',
              marginBottom: '8px', fontWeight: '600'
            }}>Doc Type</div>
            {DOC_TYPES.map(({ id, label, icon: Icon, description, color }) => (
              <button key={id} onClick={() => { setSelectedType(id); setResult(null) }}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: '10px',
                  padding: '10px', borderRadius: '8px',
                  border: `1px solid ${selectedType === id ? color + '50' : 'var(--border)'}`,
                  background: selectedType === id ? color + '10' : 'transparent',
                  cursor: 'pointer', width: '100%', textAlign: 'left',
                  transition: 'all 0.15s', marginBottom: '6px'
                }}>
                <div style={{
                  width: '28px', height: '28px', borderRadius: '6px',
                  background: color + '20', display: 'flex',
                  alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <Icon size={13} color={color} />
                </div>
                <div>
                  <div style={{
                    fontSize: '12px', fontWeight: '600',
                    color: selectedType === id ? color : 'var(--text)',
                    marginBottom: '2px'
                  }}>
                    {label}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                    {description}
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Generate button */}
          <button
            className="btn-primary"
            onClick={handleGenerate}
            disabled={!selectedRepo || generating}
            style={{
              display: 'flex', alignItems: 'center',
              justifyContent: 'center', gap: '6px', marginTop: 'auto'
            }}
          >
            {generating
              ? <><Loader size={13} style={{ animation: 'spin 1s linear infinite' }} /> Generating...</>
              : <><Zap size={13} /> Generate {DOC_TYPES.find(t => t.id === selectedType)?.label}</>
            }
          </button>
        </div>

        {/* Main content */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {!result && !generating && (
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              color: 'var(--text-muted)', textAlign: 'center', padding: '40px'
            }}>
              <div style={{
                width: '64px', height: '64px', borderRadius: '16px',
                background: 'linear-gradient(135deg, #6366f120, #a855f720)',
                border: '1px solid var(--border-bright)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: '16px'
              }}>
                <FileText size={28} color="var(--primary)" style={{ opacity: 0.5 }} />
              </div>
              <p style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px', color: 'var(--text)' }}>
                Generate Documentation
              </p>
              <p style={{ fontSize: '12px', maxWidth: '300px' }}>
                Select a repository and doc type from the sidebar, then click Generate
              </p>
            </div>
          )}

          {generating && (
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: '16px'
            }}>
              <div style={{
                width: '56px', height: '56px', borderRadius: '14px',
                background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 0 30px rgba(99,102,241,0.3)',
                animation: 'pulse-glow 2s infinite'
              }}>
                <Zap size={24} color="white" />
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '15px', fontWeight: '600', marginBottom: '6px' }}>
                  Generating {DOC_TYPES.find(t => t.id === selectedType)?.label}...
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Analyzing {selectedRepo?.name} codebase
                </div>
              </div>
            </div>
          )}

          {result && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              {/* Result header */}
              <div style={{
                padding: '12px 24px', borderBottom: '1px solid var(--border)',
                background: 'var(--bg-surface)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {(() => {
                    const docType = DOC_TYPES.find(t => t.id === result.doc_type)
                    const Icon = docType?.icon || FileText
                    return (
                      <>
                        <div style={{
                          width: '28px', height: '28px', borderRadius: '6px',
                          background: (docType?.color || '#6366f1') + '20',
                          display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}>
                          <Icon size={13} color={docType?.color || '#6366f1'} />
                        </div>
                        <div>
                          <div style={{ fontSize: '13px', fontWeight: '700' }}>
                            {docType?.label} — {selectedRepo?.name}
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                            AI-generated documentation
                          </div>
                        </div>
                      </>
                    )
                  })()}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn-ghost" onClick={handleCopy}
                    style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
                    {copied ? <><CheckCheck size={13} color="var(--success)" /> Copied!</> : <><Copy size={13} /> Copy Markdown</>}
                  </button>
                  <button className="btn-primary" onClick={handleGenerate}
                    style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
                    <Zap size={12} /> Regenerate
                  </button>
                </div>
              </div>

              {/* Doc content */}
              <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
                <div className="card" style={{ padding: '32px', maxWidth: '860px', margin: '0 auto' }}>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({ node, ...props }) => (
                        <h1 style={{
                          fontSize: '22px', fontWeight: '800', marginBottom: '16px',
                          color: 'var(--text)', borderBottom: '2px solid var(--border)',
                          paddingBottom: '12px'
                        }} {...props} />
                      ),
                      h2: ({ node, ...props }) => (
                        <h2 style={{
                          fontSize: '16px', fontWeight: '700', marginTop: '24px',
                          marginBottom: '10px', color: 'var(--text)',
                          display: 'flex', alignItems: 'center', gap: '8px'
                        }} {...props} />
                      ),
                      h3: ({ node, ...props }) => (
                        <h3 style={{
                          fontSize: '14px', fontWeight: '600', marginTop: '16px',
                          marginBottom: '8px', color: 'var(--primary)'
                        }} {...props} />
                      ),
                      p: ({ node, ...props }) => (
                        <p style={{
                          fontSize: '13px', lineHeight: '1.7',
                          marginBottom: '12px', color: 'var(--text)'
                        }} {...props} />
                      ),
                      code: ({ node, inline, children, ...props }: any) => (
                        inline
                          ? <code style={{
                              background: 'var(--bg-elevated)', padding: '2px 6px',
                              borderRadius: '4px', fontSize: '12px',
                              fontFamily: 'monospace', color: 'var(--primary)',
                              border: '1px solid var(--border)'
                            }}>{children}</code>
                          : <pre style={{
                              background: 'var(--bg-elevated)', padding: '16px',
                              borderRadius: '8px', overflowX: 'auto',
                              border: '1px solid var(--border)', margin: '12px 0'
                            }}>
                              <code style={{
                                fontFamily: 'JetBrains Mono, monospace',
                                fontSize: '12px', color: 'var(--text)', lineHeight: '1.6'
                              }} {...props}>{children}</code>
                            </pre>
                      ),
                      table: ({ node, ...props }) => (
                        <div style={{ overflowX: 'auto', margin: '12px 0', borderRadius: '8px', border: '1px solid var(--border)' }}>
                          <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '12px' }} {...props} />
                        </div>
                      ),
                      th: ({ node, ...props }) => (
                        <th style={{
                          padding: '8px 14px', textAlign: 'left',
                          background: 'var(--bg-elevated)',
                          borderBottom: '1px solid var(--border-bright)',
                          color: 'var(--text-muted)', fontWeight: '600', fontSize: '11px'
                        }} {...props} />
                      ),
                      td: ({ node, ...props }) => (
                        <td style={{
                          padding: '8px 14px', borderBottom: '1px solid var(--border)', color: 'var(--text)'
                        }} {...props} />
                      ),
                      ul: ({ node, ...props }) => (
                        <ul style={{ paddingLeft: '20px', marginBottom: '12px' }} {...props} />
                      ),
                      li: ({ node, ...props }) => (
                        <li style={{ fontSize: '13px', lineHeight: '1.6', marginBottom: '4px' }} {...props} />
                      ),
                      blockquote: ({ node, ...props }) => (
                        <blockquote style={{
                          margin: '12px 0', padding: '10px 16px',
                          borderLeft: '3px solid var(--primary)',
                          background: 'var(--bg-elevated)', borderRadius: '0 6px 6px 0',
                          color: 'var(--text-muted)', fontSize: '13px'
                        }} {...props} />
                      ),
                      hr: ({ node, ...props }) => (
                        <hr style={{
                          border: 'none', borderTop: '1px solid var(--border)', margin: '20px 0'
                        }} {...props} />
                      ),
                    }}
                  >
                    {result.content}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes pulse-glow {
          0%, 100% { box-shadow: 0 0 10px rgba(99,102,241,0.3); }
          50% { box-shadow: 0 0 30px rgba(99,102,241,0.6); }
        }
      `}</style>
    </div>
  )
}