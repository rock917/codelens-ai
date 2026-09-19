import { useEffect, useState } from 'react'
import {
  FileCode, ChevronRight,
  ChevronDown, Folder, FolderOpen,
  Code2, Layers,
  Star, Zap, X, Info, Eye
} from 'lucide-react'
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter'
import python from 'react-syntax-highlighter/dist/esm/languages/hljs/python'
import javascript from 'react-syntax-highlighter/dist/esm/languages/hljs/javascript'
import typescript from 'react-syntax-highlighter/dist/esm/languages/hljs/typescript'
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs'
import TopBar from '../components/layout/TopBar'
import {
  getRepositories, getRepositoryFiles,
  getFileSymbols, getFileSummary, getFileContent
} from '../services/api'
import type { Repository, FileRecord, Symbol } from '../types'

SyntaxHighlighter.registerLanguage('python', python)
SyntaxHighlighter.registerLanguage('javascript', javascript)
SyntaxHighlighter.registerLanguage('typescript', typescript)

// ── File tree builder ─────────────────────────────────────────
interface TreeNode {
  name: string
  path: string
  type: 'file' | 'folder'
  children?: TreeNode[]
  file?: FileRecord
}

function buildTree(files: FileRecord[]): TreeNode[] {
  const root: TreeNode[] = []
  files.forEach(file => {
    const parts = file.path.split('/')
    let current = root
    parts.forEach((part, i) => {
      const isFile = i === parts.length - 1
      const existing = current.find(n => n.name === part)
      if (existing) {
        if (!isFile) current = existing.children!
      } else {
        const node: TreeNode = {
          name: part,
          path: parts.slice(0, i + 1).join('/'),
          type: isFile ? 'file' : 'folder',
          children: isFile ? undefined : [],
          file: isFile ? file : undefined
        }
        current.push(node)
        if (!isFile) current = node.children!
      }
    })
  })

  function sortNodes(nodes: TreeNode[]): TreeNode[] {
    return nodes
      .sort((a, b) => {
        if (a.type !== b.type) return a.type === 'folder' ? -1 : 1
        return a.name.localeCompare(b.name)
      })
      .map(n => ({ ...n, children: n.children ? sortNodes(n.children) : undefined }))
  }
  return sortNodes(root)
}

function importanceDot(level: string) {
  const colors: Record<string, string> = {
    HIGH: '#22c55e', MEDIUM: '#f59e0b', LOW: '#334155'
  }
  return (
    <div style={{
      width: '5px', height: '5px', borderRadius: '50%',
      background: colors[level] || colors.LOW, flexShrink: 0
    }} />
  )
}

// ── Tree Node ─────────────────────────────────────────────────
function TreeNodeItem({ node, depth, selectedFile, onSelect }: {
  node: TreeNode
  depth: number
  selectedFile: FileRecord | null
  onSelect: (file: FileRecord) => void
}) {
  const [open, setOpen] = useState(depth < 2)
  const isSelected = node.file && selectedFile?.id === node.file.id
  const isFolder = node.type === 'folder'

  return (
    <div>
      <div
        onClick={() => {
          if (isFolder) setOpen(!open)
          else if (node.file) onSelect(node.file)
        }}
        style={{
          display: 'flex', alignItems: 'center', gap: '5px',
          padding: '4px 8px', paddingLeft: `${8 + depth * 14}px`,
          borderRadius: '4px', cursor: 'pointer',
          background: isSelected ? 'var(--primary-glow)' : 'transparent',
          color: isSelected ? 'var(--primary)' : 'var(--text-muted)',
          fontSize: '12px', transition: 'all 0.1s', userSelect: 'none'
        }}
        onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'var(--bg-elevated)' }}
        onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent' }}
      >
        {isFolder ? (
          <>
            {open
              ? <ChevronDown size={11} style={{ flexShrink: 0 }} />
              : <ChevronRight size={11} style={{ flexShrink: 0 }} />
            }
            {open
              ? <FolderOpen size={12} color="#f59e0b" style={{ flexShrink: 0 }} />
              : <Folder size={12} color="#f59e0b" style={{ flexShrink: 0 }} />
            }
          </>
        ) : (
          <>
            <div style={{ width: '11px', flexShrink: 0 }} />
            <FileCode size={12}
              color={isSelected ? 'var(--primary)' : '#64748b'}
              style={{ flexShrink: 0 }}
            />
          </>
        )}
        <span style={{
          overflow: 'hidden', textOverflow: 'ellipsis',
          whiteSpace: 'nowrap', flex: 1,
          color: isSelected ? 'var(--primary)' : isFolder ? 'var(--text)' : 'var(--text-muted)'
        }}>
          {node.name}
        </span>
        {node.file && importanceDot(node.file.importance_level)}
      </div>

      {isFolder && open && node.children && (
        <div>
          {node.children.map(child => (
            <TreeNodeItem
              key={child.path} node={child} depth={depth + 1}
              selectedFile={selectedFile} onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────
export default function Explorer() {
  const [repos, setRepos] = useState<Repository[]>([])
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null)
  const [files, setFiles] = useState<FileRecord[]>([])
  const [tree, setTree] = useState<TreeNode[]>([])
  const [selectedFile, setSelectedFile] = useState<FileRecord | null>(null)
  const [symbols, setSymbols] = useState<Symbol[]>([])
  const [summary, setSummary] = useState<string>('')
  const [fileContent, setFileContent] = useState<string>('')
  const [loadingFile, setLoadingFile] = useState(false)
  const [activeTab, setActiveTab] = useState<'code' | 'symbols' | 'info' | 'summary'>('code')
  const [highlightLine, setHighlightLine] = useState<number | null>(null)

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
    setSummary('')
    setFileContent('')
    try {
      const res = await getRepositoryFiles(repo.id)
      setFiles(res.data)
      setTree(buildTree(res.data))
    } catch (err) { console.error(err) }
  }

  async function selectFile(file: FileRecord) {
    setSelectedFile(file)
    setLoadingFile(true)
    setFileContent('')
    setSymbols([])
    setSummary('')
    setActiveTab('code')
    setHighlightLine(null)

    try {
      const [symRes, sumRes, contentRes] = await Promise.all([
        getFileSymbols(file.id),
        getFileSummary(file.id),
        getFileContent(selectedRepo!.id, file.id)
      ])
      setSymbols(symRes.data)
      setSummary(sumRes.data?.summary || '')
      setFileContent(contentRes.data?.content || '')
    } catch (err) {
      console.error(err)
    } finally {
      setLoadingFile(false)
    }
  }

  function jumpToLine(line: number) {
    setHighlightLine(line)
    setActiveTab('code')
    setTimeout(() => {
      const el = document.getElementById(`line-${line}`)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
  }

  const getLang = (lang: string) => {
    const map: Record<string, string> = {
      python: 'python', javascript: 'javascript',
      typescript: 'typescript', jsx: 'javascript', tsx: 'typescript'
    }
    return map[lang] || 'text'
  }

  const importanceColor = (level: string) =>
    level === 'HIGH' ? '#22c55e' : level === 'MEDIUM' ? '#f59e0b' : '#64748b'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <TopBar title="Repository Explorer" subtitle="Browse files, symbols and structure" />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* File Tree */}
        <div style={{
          width: '240px', minWidth: '240px',
          borderRight: '1px solid var(--border)',
          background: 'var(--bg-surface)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden'
        }}>
          {/* Repo selector */}
          <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
            <select
              value={selectedRepo?.id || ''}
              onChange={e => {
                const repo = repos.find(r => r.id === e.target.value)
                if (repo) selectRepo(repo)
              }}
              style={{
                width: '100%', background: 'var(--bg-elevated)',
                border: '1px solid var(--border)', borderRadius: '6px',
                padding: '6px 10px', color: 'var(--text)',
                fontSize: '12px', outline: 'none', cursor: 'pointer'
              }}
            >
              {repos.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>

          {/* Stats */}
          {selectedRepo && (
            <div style={{
              padding: '8px 12px', borderBottom: '1px solid var(--border)',
              display: 'flex', gap: '8px'
            }}>
              {[
                { label: 'Files', value: files.length, color: 'var(--text)' },
                { label: 'HIGH', value: files.filter(f => f.importance_level === 'HIGH').length, color: '#22c55e' },
                { label: 'MED', value: files.filter(f => f.importance_level === 'MEDIUM').length, color: '#f59e0b' },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ textAlign: 'center', flex: 1 }}>
                  <div style={{ fontSize: '14px', fontWeight: '700', fontFamily: 'monospace', color }}>
                    {value}
                  </div>
                  <div style={{ fontSize: '9px', color: 'var(--text-muted)', fontWeight: '600' }}>
                    {label}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Legend */}
          <div style={{
            padding: '5px 12px', borderBottom: '1px solid var(--border)',
            display: 'flex', gap: '10px', alignItems: 'center'
          }}>
            {[{ color: '#22c55e', label: 'High' }, { color: '#f59e0b', label: 'Med' }, { color: '#334155', label: 'Low' }]
              .map(({ color, label }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: color }} />
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{label}</span>
                </div>
              ))}
          </div>

          {/* Tree */}
          <div style={{ flex: 1, overflow: 'auto', padding: '6px 4px' }}>
            {tree.map(node => (
              <TreeNodeItem
                key={node.path} node={node} depth={0}
                selectedFile={selectedFile} onSelect={selectFile}
              />
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
              <div style={{
                width: '64px', height: '64px', borderRadius: '16px',
                background: 'linear-gradient(135deg, #6366f120, #a855f720)',
                border: '1px solid var(--border-bright)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: '16px'
              }}>
                <Code2 size={28} color="var(--primary)" style={{ opacity: 0.5 }} />
              </div>
              <p style={{ fontSize: '14px', fontWeight: '600', marginBottom: '8px', color: 'var(--text)' }}>
                Select a file to explore
              </p>
              <p style={{ fontSize: '12px', maxWidth: '280px' }}>
                Click any file in the tree to view its code, symbols, and AI summary
              </p>

              {files.length > 0 && (
                <div style={{
                  display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: '12px', marginTop: '32px', maxWidth: '400px', width: '100%'
                }}>
                  {[
                    { icon: FileCode, label: 'Total Files', value: files.length, color: 'var(--primary)' },
                    { icon: Layers, label: 'Total LOC', value: files.reduce((s, f) => s + f.loc, 0).toLocaleString(), color: 'var(--accent)' },
                    { icon: Star, label: 'High Priority', value: files.filter(f => f.importance_level === 'HIGH').length, color: '#22c55e' },
                  ].map(({ icon: Icon, label, value, color }) => (
                    <div key={label} className="card" style={{ padding: '14px', textAlign: 'center' }}>
                      <Icon size={16} color={color} style={{ marginBottom: '6px' }} />
                      <div style={{ fontSize: '18px', fontWeight: '700', fontFamily: 'monospace', color }}>
                        {value}
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {label}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <>
              {/* File header */}
              <div style={{
                padding: '10px 20px', borderBottom: '1px solid var(--border)',
                background: 'var(--bg-surface)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <FileCode size={15} color="var(--primary)" />
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: '700', fontFamily: 'monospace' }}>
                      {selectedFile.path}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '2px' }}>
                      {[
                        { label: selectedFile.language },
                        { label: `${selectedFile.loc} lines` },
                        { label: `${(selectedFile.size / 1024).toFixed(1)} KB` },
                      ].map(({ label }) => (
                        <span key={label} style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                          {label}
                        </span>
                      ))}
                      <span style={{
                        fontSize: '10px', fontWeight: '700',
                        color: importanceColor(selectedFile.importance_level)
                      }}>
                        ● {selectedFile.importance_level}
                      </span>
                    </div>
                  </div>
                </div>
                <button onClick={() => setSelectedFile(null)} style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--text-muted)', display: 'flex', alignItems: 'center'
                }}>
                  <X size={14} />
                </button>
              </div>

              {/* Tabs */}
              <div style={{
                display: 'flex', borderBottom: '1px solid var(--border)',
                background: 'var(--bg-surface)', padding: '0 20px'
              }}>
                {[
                  { id: 'code', label: 'Code', icon: Eye },
                  { id: 'symbols', label: 'Symbols', icon: Code2 },
                  { id: 'info', label: 'Metadata', icon: Info },
                  { id: 'summary', label: 'AI Summary', icon: Zap },
                ].map(({ id, label, icon: Icon }) => (
                  <button key={id} onClick={() => setActiveTab(id as any)} style={{
                    padding: '10px 16px', border: 'none', background: 'transparent',
                    cursor: 'pointer', fontSize: '12px', fontWeight: '500',
                    color: activeTab === id ? 'var(--primary)' : 'var(--text-muted)',
                    borderBottom: activeTab === id ? '2px solid var(--primary)' : '2px solid transparent',
                    display: 'flex', alignItems: 'center', gap: '6px',
                    transition: 'all 0.15s', marginBottom: '-1px'
                  }}>
                    <Icon size={12} />
                    {label}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              <div style={{ flex: 1, overflow: 'auto' }}>

                {/* CODE TAB */}
                {activeTab === 'code' && (
                  <div style={{ height: '100%' }}>
                    {loadingFile ? (
                      <div style={{
                        display: 'flex', alignItems: 'center',
                        justifyContent: 'center', height: '100%',
                        color: 'var(--text-muted)'
                      }}>
                        <Zap size={20} color="var(--primary)"
                          style={{ animation: 'spin 1s linear infinite', marginRight: '8px' }} />
                        Loading file...
                      </div>
                    ) : fileContent ? (
                      <div style={{ position: 'relative' }}>
                        <SyntaxHighlighter
                          language={getLang(selectedFile.language)}
                          style={atomOneDark}
                          showLineNumbers
                          wrapLines
                          lineProps={(lineNumber: number) => ({
                            id: `line-${lineNumber}`,
                            style: {
                              display: 'block',
                              background: highlightLine === lineNumber
                                ? 'rgba(99,102,241,0.2)' : 'transparent',
                              borderLeft: highlightLine === lineNumber
                                ? '3px solid var(--primary)' : '3px solid transparent',
                              transition: 'background 0.3s'
                            }
                          })}
                          customStyle={{
                            margin: 0, borderRadius: 0,
                            background: '#0a0a0f',
                            fontSize: '12px',
                            lineHeight: '1.6',
                            minHeight: '100%',
                            fontFamily: 'JetBrains Mono, monospace'
                          }}
                          lineNumberStyle={{
                            color: '#334155', minWidth: '40px',
                            paddingRight: '16px', userSelect: 'none'
                          }}
                        >
                          {fileContent}
                        </SyntaxHighlighter>
                      </div>
                    ) : (
                      <div style={{
                        display: 'flex', alignItems: 'center',
                        justifyContent: 'center', height: '200px',
                        color: 'var(--text-muted)', fontSize: '13px'
                      }}>
                        No content available
                      </div>
                    )}
                  </div>
                )}

                {/* SYMBOLS TAB */}
                {activeTab === 'symbols' && (
                  <div className="animate-fade-in" style={{ padding: '16px 20px' }}>
                    {symbols.length === 0 ? (
                      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        <Code2 size={32} style={{ marginBottom: '12px', opacity: 0.3 }} />
                        <p>No symbols found</p>
                      </div>
                    ) : (
                      <div>
                        <div style={{
                          fontSize: '11px', color: 'var(--text-muted)',
                          fontWeight: '600', textTransform: 'uppercase',
                          letterSpacing: '0.05em', marginBottom: '12px'
                        }}>
                          {symbols.length} Symbols — click to jump to line
                        </div>

                        {(() => {
                          const classes = symbols.filter(s => s.type === 'class')
                          const functions = symbols.filter(s => s.type === 'function')
                          const methods = symbols.filter(s => s.type === 'method')

                          return (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                              {classes.map(cls => (
                                <div key={cls.id} className="card" style={{ overflow: 'hidden' }}>
                                  <div
                                    onClick={() => jumpToLine(cls.start_line)}
                                    style={{
                                      padding: '10px 14px',
                                      background: 'linear-gradient(135deg, rgba(99,102,241,0.08), rgba(168,85,247,0.08))',
                                      borderBottom: '1px solid var(--border)',
                                      display: 'flex', alignItems: 'center',
                                      gap: '8px', cursor: 'pointer'
                                    }}
                                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.15)'}
                                    onMouseLeave={e => e.currentTarget.style.background = 'linear-gradient(135deg, rgba(99,102,241,0.08), rgba(168,85,247,0.08))'}
                                  >
                                    <span style={{
                                      padding: '2px 8px', borderRadius: '4px',
                                      background: 'rgba(99,102,241,0.15)',
                                      color: 'var(--primary)', fontSize: '10px',
                                      fontWeight: '700', fontFamily: 'monospace'
                                    }}>class</span>
                                    <span style={{ fontSize: '13px', fontWeight: '700', fontFamily: 'monospace', flex: 1 }}>
                                      {cls.name}
                                    </span>
                                    <span style={{ fontSize: '10px', color: 'var(--primary)', fontFamily: 'monospace' }}>
                                      L{cls.start_line}
                                    </span>
                                  </div>

                                  {methods.filter(m => m.parent_name === cls.name).map(method => (
                                    <div
                                      key={method.id}
                                      onClick={() => jumpToLine(method.start_line)}
                                      style={{
                                        padding: '8px 14px 8px 28px',
                                        borderBottom: '1px solid var(--border)',
                                        display: 'flex', alignItems: 'center',
                                        gap: '8px', cursor: 'pointer',
                                        transition: 'background 0.1s'
                                      }}
                                      onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-elevated)'}
                                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                    >
                                      <span style={{
                                        padding: '1px 6px', borderRadius: '3px',
                                        background: 'rgba(168,85,247,0.1)',
                                        color: '#a855f7', fontSize: '9px',
                                        fontWeight: '700', fontFamily: 'monospace'
                                      }}>def</span>
                                      <span style={{ fontSize: '12px', fontFamily: 'monospace', color: 'var(--text)', flex: 1 }}>
                                        {method.signature || method.name + '()'}
                                      </span>
                                      <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
                                        {method.complexity > 3 && (
                                          <span style={{
                                            fontSize: '10px',
                                            color: method.complexity > 7 ? '#ef4444' : '#f59e0b',
                                            fontFamily: 'monospace'
                                          }}>
                                            cx:{method.complexity}
                                          </span>
                                        )}
                                        <span style={{ fontSize: '10px', color: 'var(--primary)', fontFamily: 'monospace' }}>
                                          L{method.start_line}
                                        </span>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              ))}

                              {functions.length > 0 && (
                                <div className="card" style={{ overflow: 'hidden' }}>
                                  <div style={{
                                    padding: '8px 14px', borderBottom: '1px solid var(--border)',
                                    fontSize: '10px', color: 'var(--text-muted)',
                                    fontWeight: '600', textTransform: 'uppercase'
                                  }}>
                                    Functions
                                  </div>
                                  {functions.map(fn => (
                                    <div
                                      key={fn.id}
                                      onClick={() => jumpToLine(fn.start_line)}
                                      style={{
                                        padding: '8px 14px', borderBottom: '1px solid var(--border)',
                                        display: 'flex', alignItems: 'center',
                                        gap: '8px', cursor: 'pointer', transition: 'background 0.1s'
                                      }}
                                      onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-elevated)'}
                                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                    >
                                      <span style={{
                                        padding: '1px 6px', borderRadius: '3px',
                                        background: 'rgba(34,197,94,0.1)',
                                        color: '#22c55e', fontSize: '9px',
                                        fontWeight: '700', fontFamily: 'monospace'
                                      }}>def</span>
                                      <span style={{ fontSize: '12px', fontFamily: 'monospace', color: 'var(--text)', flex: 1 }}>
                                        {fn.signature || fn.name + '()'}
                                      </span>
                                      <span style={{ fontSize: '10px', color: 'var(--primary)', fontFamily: 'monospace', flexShrink: 0 }}>
                                        L{fn.start_line}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )
                        })()}
                      </div>
                    )}
                  </div>
                )}

                {/* INFO TAB */}
                {activeTab === 'info' && (
                  <div className="animate-fade-in" style={{ padding: '16px 20px' }}>
                    <div style={{
                      display: 'grid', gridTemplateColumns: '1fr 1fr',
                      gap: '12px', marginBottom: '16px'
                    }}>
                      {[
                        { label: 'Language', value: selectedFile.language },
                        { label: 'Lines of Code', value: selectedFile.loc },
                        { label: 'File Size', value: `${(selectedFile.size / 1024).toFixed(2)} KB` },
                        { label: 'Classes', value: selectedFile.num_classes },
                        { label: 'Functions', value: selectedFile.num_functions },
                        { label: 'Complexity', value: selectedFile.complexity_score.toFixed(2) },
                        { label: 'Importance Score', value: selectedFile.importance_score.toFixed(1) },
                        { label: 'Importance Level', value: selectedFile.importance_level },
                      ].map(({ label, value }) => (
                        <div key={label} className="card" style={{ padding: '12px' }}>
                          <div style={{
                            fontSize: '10px', color: 'var(--text-muted)',
                            fontWeight: '600', marginBottom: '4px',
                            textTransform: 'uppercase', letterSpacing: '0.05em'
                          }}>{label}</div>
                          <div style={{
                            fontSize: '16px', fontWeight: '700',
                            fontFamily: 'monospace',
                            color: label === 'Importance Level'
                              ? importanceColor(value as string) : 'var(--text)'
                          }}>{value}</div>
                        </div>
                      ))}
                    </div>

                    <div className="card" style={{ padding: '14px' }}>
                      <div style={{
                        fontSize: '11px', color: 'var(--text-muted)',
                        fontWeight: '600', marginBottom: '8px'
                      }}>Complexity Score</div>
                      <div style={{
                        height: '6px', background: 'var(--border)',
                        borderRadius: '3px', overflow: 'hidden'
                      }}>
                        <div style={{
                          width: `${Math.min(selectedFile.complexity_score * 10, 100)}%`,
                          height: '100%', borderRadius: '3px',
                          background: selectedFile.complexity_score > 5 ? '#ef4444'
                            : selectedFile.complexity_score > 2 ? '#f59e0b' : '#22c55e',
                          transition: 'width 0.5s ease'
                        }} />
                      </div>
                      <div style={{
                        display: 'flex', justifyContent: 'space-between',
                        marginTop: '4px', fontSize: '10px', color: 'var(--text-muted)'
                      }}>
                        <span>Simple</span>
                        <span>Complex</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* SUMMARY TAB */}
                {activeTab === 'summary' && (
                  <div className="animate-fade-in" style={{ padding: '16px 20px' }}>
                    {!summary ? (
                      <div style={{
                        textAlign: 'center', padding: '40px', color: 'var(--text-muted)'
                      }}>
                        <Zap size={32} style={{ marginBottom: '12px', opacity: 0.3 }} />
                        <p style={{ fontSize: '13px', marginBottom: '8px' }}>No summary available</p>
                        <p style={{ fontSize: '11px' }}>
                          {selectedFile.importance_level === 'LOW'
                            ? 'Low importance files are summarized on demand via the Summary API'
                            : 'Summary will appear after indexing'}
                        </p>
                      </div>
                    ) : (
                      <div>
                        <div style={{
                          display: 'flex', alignItems: 'center',
                          gap: '8px', marginBottom: '12px'
                        }}>
                          <div style={{
                            width: '24px', height: '24px', borderRadius: '6px',
                            background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center'
                          }}>
                            <Zap size={12} color="white" />
                          </div>
                          <span style={{ fontSize: '12px', fontWeight: '600' }}>AI Summary</span>
                          <span style={{
                            fontSize: '10px', color: 'var(--primary)',
                            background: 'var(--primary-glow)', padding: '2px 8px',
                            borderRadius: '9999px', border: '1px solid rgba(99,102,241,0.2)'
                          }}>
                            {selectedFile.importance_level}
                          </span>
                        </div>
                        <div className="card" style={{
                          padding: '16px', fontSize: '13px',
                          lineHeight: '1.7', color: 'var(--text)'
                        }}>
                          {summary}
                        </div>
                      </div>
                    )}
                  </div>
                )}
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