import { useEffect, useState } from 'react'
import {
  FlaskConical, GitBranch, FileCode,
  Zap, Copy, CheckCheck,
  Loader, FunctionSquare
} from 'lucide-react'
import TopBar from '../components/layout/TopBar'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  getRepositories, getRepositoryFiles,
  getTestableSymbols, generateTests
} from '../services/api'
import type { Repository, FileRecord, Symbol } from '../types'

export default function TestGen() {
  const [repos, setRepos] = useState<Repository[]>([])
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null)
  const [files, setFiles] = useState<FileRecord[]>([])
  const [selectedFile, setSelectedFile] = useState<FileRecord | null>(null)
  const [symbols, setSymbols] = useState<Symbol[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState<string>('')
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => { loadRepos() }, [])

  async function loadRepos() {
    try {
      const res = await getRepositories()
      const ready = res.data.filter((r: Repository) => r.status === 'READY')
      setRepos(ready)
      if (ready.length > 0) selectRepo(ready[0])
    } catch (err) { console.error(err) }
  }

  async function selectRepo(repo: Repository) {
    setSelectedRepo(repo)
    setSelectedFile(null)
    setSymbols([])
    setResult(null)
    try {
      const res = await getRepositoryFiles(repo.id)
      const sourceFiles = res.data.filter(
        (f: FileRecord) => ['python', 'javascript', 'typescript'].includes(f.language)
      )
      setFiles(sourceFiles)
    } catch (err) { console.error(err) }
  }

  async function selectFile(file: FileRecord) {
    setSelectedFile(file)
    setSelectedSymbol('')
    setResult(null)
    try {
      const res = await getTestableSymbols(selectedRepo!.id, file.id)
      setSymbols(res.data)
    } catch (err) { console.error(err) }
  }

  async function handleGenerate() {
    if (!selectedRepo || !selectedFile) return
    setGenerating(true)
    setResult(null)
    try {
      const res = await generateTests(
        selectedRepo.id,
        selectedFile.id,
        selectedSymbol || undefined
      )
      setResult(res.data)
    } catch (err) { console.error(err) }
    finally { setGenerating(false) }
  }

  async function handleCopy() {
    if (!result?.generated_tests) return
    await navigator.clipboard.writeText(result.generated_tests)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <TopBar title="Test Generator" subtitle="Generate unit tests for any function" />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Left panel */}
        <div style={{
          width: '260px', minWidth: '260px',
          borderRight: '1px solid var(--border)',
          background: 'var(--bg-surface)',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden'
        }}>
          {/* Repo selector */}
          <div style={{ padding: '12px', borderBottom: '1px solid var(--border)' }}>
            <div style={{
              fontSize: '10px', color: 'var(--text-muted)',
              textTransform: 'uppercase', letterSpacing: '0.05em',
              marginBottom: '8px', fontWeight: '600'
            }}>Repository</div>
            {repos.map(repo => (
              <button key={repo.id} onClick={() => selectRepo(repo)}
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

          {/* File list */}
          <div style={{ flex: 1, overflow: 'auto', padding: '12px' }}>
            <div style={{
              fontSize: '10px', color: 'var(--text-muted)',
              textTransform: 'uppercase', letterSpacing: '0.05em',
              marginBottom: '8px', fontWeight: '600'
            }}>Files</div>
            {files.map(file => (
              <button key={file.id} onClick={() => selectFile(file)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '7px 10px', borderRadius: '6px', border: 'none',
                  cursor: 'pointer', width: '100%', textAlign: 'left',
                  background: selectedFile?.id === file.id ? 'var(--primary-glow)' : 'transparent',
                  color: selectedFile?.id === file.id ? 'var(--primary)' : 'var(--text-muted)',
                  fontSize: '11px', transition: 'all 0.15s', marginBottom: '2px'
                }}
                onMouseEnter={e => { if (selectedFile?.id !== file.id) e.currentTarget.style.background = 'var(--bg-elevated)' }}
                onMouseLeave={e => { if (selectedFile?.id !== file.id) e.currentTarget.style.background = 'transparent' }}
              >
                <FileCode size={11} style={{ flexShrink: 0 }} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {file.path.split('/').pop()}
                </span>
                <span style={{
                  marginLeft: 'auto', fontSize: '9px', flexShrink: 0,
                  color: 'var(--text-muted)', fontFamily: 'monospace'
                }}>
                  {file.num_functions}fn
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Main content */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {!selectedFile ? (
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              color: 'var(--text-muted)', textAlign: 'center', padding: '40px'
            }}>
              <FlaskConical size={48} style={{ marginBottom: '16px', opacity: 0.3 }} />
              <p style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px' }}>
                Select a file to generate tests
              </p>
              <p style={{ fontSize: '12px' }}>
                Pick a repository and file from the sidebar
              </p>
            </div>
          ) : (
            <>
              {/* Config bar */}
              <div style={{
                padding: '16px 24px',
                borderBottom: '1px solid var(--border)',
                background: 'var(--bg-surface)',
                display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap'
              }}>
                <div style={{ flex: 1, minWidth: '200px' }}>
                  <div style={{
                    fontSize: '11px', color: 'var(--text-muted)',
                    marginBottom: '4px', fontWeight: '600'
                  }}>
                    Selected File
                  </div>
                  <div style={{
                    fontSize: '12px', fontFamily: 'monospace',
                    color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '6px'
                  }}>
                    <FileCode size={12} color="var(--primary)" />
                    {selectedFile.path}
                  </div>
                </div>

                {symbols.length > 0 && (
                  <div style={{ minWidth: '200px' }}>
                    <div style={{
                      fontSize: '11px', color: 'var(--text-muted)',
                      marginBottom: '4px', fontWeight: '600'
                    }}>
                      Function (optional)
                    </div>
                    <select
                      value={selectedSymbol}
                      onChange={e => setSelectedSymbol(e.target.value)}
                      style={{
                        background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                        borderRadius: '6px', padding: '6px 10px', color: 'var(--text)',
                        fontSize: '12px', outline: 'none', cursor: 'pointer',
                        width: '100%'
                      }}
                    >
                      <option value="">Entire file</option>
                      {symbols.map(sym => (
                        <option key={sym.id} value={sym.name}>
                          {sym.parent_name ? `${sym.parent_name}.` : ''}{sym.name}()
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <button
                  className="btn-primary"
                  onClick={handleGenerate}
                  disabled={generating}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '6px',
                    alignSelf: 'flex-end', whiteSpace: 'nowrap'
                  }}
                >
                  {generating
                    ? <><Loader size={13} style={{ animation: 'spin 1s linear infinite' }} /> Generating...</>
                    : <><Zap size={13} /> Generate Tests</>
                  }
                </button>
              </div>

              {/* Symbols quick view */}
              {symbols.length > 0 && !result && !generating && (
                <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border)' }}>
                  <div style={{
                    fontSize: '11px', color: 'var(--text-muted)',
                    fontWeight: '600', marginBottom: '8px',
                    textTransform: 'uppercase', letterSpacing: '0.05em'
                  }}>
                    Testable Functions · {symbols.length}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {symbols.map(sym => (
                      <button key={sym.id}
                        onClick={() => setSelectedSymbol(sym.name)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '6px',
                          padding: '4px 10px', borderRadius: '6px',
                          border: `1px solid ${selectedSymbol === sym.name ? 'var(--primary)' : 'var(--border)'}`,
                          background: selectedSymbol === sym.name ? 'var(--primary-glow)' : 'var(--bg-elevated)',
                          color: selectedSymbol === sym.name ? 'var(--primary)' : 'var(--text-muted)',
                          cursor: 'pointer', fontSize: '11px', fontFamily: 'monospace',
                          transition: 'all 0.15s'
                        }}>
                        <FunctionSquare size={10} />
                        {sym.parent_name ? `${sym.parent_name}.` : ''}{sym.name}
                        <span style={{ fontSize: '9px', opacity: 0.6 }}>
                          L{sym.start_line}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Result */}
              <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px' }}>
                {generating && (
                  <div style={{
                    display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                    padding: '60px', gap: '16px'
                  }}>
                    <div style={{
                      width: '48px', height: '48px', borderRadius: '12px',
                      background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      boxShadow: '0 0 20px rgba(99,102,241,0.3)',
                      animation: 'pulse-glow 2s infinite'
                    }}>
                      <Zap size={20} color="white" />
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '14px', fontWeight: '600', marginBottom: '4px' }}>
                        Generating tests...
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        Analyzing code structure and dependencies
                      </div>
                    </div>
                  </div>
                )}

                {result && (
                  <div className="animate-fade-in">
                    {/* Result header */}
                    <div style={{
                      display: 'flex', alignItems: 'center',
                      justifyContent: 'space-between', marginBottom: '16px'
                    }}>
                      <div>
                        <h3 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '4px' }}>
                          Generated Tests
                          {result.symbol_name && (
                            <span style={{ color: 'var(--primary)', marginLeft: '8px' }}>
                              · {result.symbol_name}()
                            </span>
                          )}
                        </h3>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {result.file_path} · {result.language}
                        </div>
                      </div>
                      <button
                        className="btn-ghost"
                        onClick={handleCopy}
                        style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
                      >
                        {copied ? <><CheckCheck size={13} color="var(--success)" /> Copied!</> : <><Copy size={13} /> Copy</>}
                      </button>
                    </div>

                    {/* Generated content */}
                    <div className="card" style={{ padding: '20px' }}>
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code: ({ node, inline, children, ...props }: any) => (
                            inline
                              ? <code style={{
                                  background: 'var(--bg-elevated)', padding: '2px 6px',
                                  borderRadius: '4px', fontSize: '12px',
                                  fontFamily: 'monospace', color: 'var(--primary)'
                                }} {...props}>{children}</code>
                              : <pre style={{
                                  background: 'var(--bg-base)', padding: '16px',
                                  borderRadius: '8px', overflowX: 'auto',
                                  border: '1px solid var(--border)', margin: '10px 0'
                                }}>
                                  <code style={{
                                    fontFamily: 'JetBrains Mono, monospace',
                                    fontSize: '12px', color: 'var(--text)', lineHeight: '1.6'
                                  }} {...props}>{children}</code>
                                </pre>
                          ),
                          h2: ({ node, ...props }) => (
                            <h2 style={{
                              fontSize: '13px', fontWeight: '700', marginTop: '16px',
                              marginBottom: '8px', color: 'var(--primary)',
                              borderBottom: '1px solid var(--border)', paddingBottom: '4px'
                            }} {...props} />
                          ),
                          p: ({ node, ...props }) => (
                            <p style={{ fontSize: '13px', lineHeight: '1.6', marginBottom: '8px' }} {...props} />
                          ),
                          li: ({ node, ...props }) => (
                            <li style={{ fontSize: '13px', lineHeight: '1.5', marginBottom: '4px' }} {...props} />
                          ),
                          table: ({ node, ...props }) => (
                            <table style={{
                              borderCollapse: 'collapse', width: '100%',
                              fontSize: '12px', margin: '10px 0',
                              border: '1px solid var(--border)', borderRadius: '6px'
                            }} {...props} />
                          ),
                          th: ({ node, ...props }) => (
                            <th style={{
                              padding: '8px 12px', textAlign: 'left',
                              background: 'var(--bg-elevated)',
                              borderBottom: '1px solid var(--border-bright)',
                              color: 'var(--text-muted)', fontWeight: '600', fontSize: '11px'
                            }} {...props} />
                          ),
                          td: ({ node, ...props }) => (
                            <td style={{
                              padding: '8px 12px', borderBottom: '1px solid var(--border)',
                              color: 'var(--text)'
                            }} {...props} />
                          ),
                        }}
                      >
                        {result.generated_tests}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes pulse-glow {
          0%, 100% { box-shadow: 0 0 10px rgba(99,102,241,0.3); }
          50% { box-shadow: 0 0 25px rgba(99,102,241,0.6); }
        }
      `}</style>
    </div>
  )
}