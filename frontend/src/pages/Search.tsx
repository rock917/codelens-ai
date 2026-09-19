import { useState } from 'react'
import {
  Search, GitBranch, FileCode,
  ChevronRight, Zap, Loader,
  Code2, SlidersHorizontal
} from 'lucide-react'
import TopBar from '../components/layout/TopBar'
import { searchCode, getRepositories } from '../services/api'
import type { Repository, SearchResult } from '../types'
import { useEffect } from 'react'
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter'
import python from 'react-syntax-highlighter/dist/esm/languages/hljs/python'
import javascript from 'react-syntax-highlighter/dist/esm/languages/hljs/javascript'
import typescript from 'react-syntax-highlighter/dist/esm/languages/hljs/typescript'
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs'

SyntaxHighlighter.registerLanguage('python', python)
SyntaxHighlighter.registerLanguage('javascript', javascript)
SyntaxHighlighter.registerLanguage('typescript', typescript)

const EXAMPLE_QUERIES = [
  'authentication and JWT tokens',
  'database connection setup',
  'error handling middleware',
  'API route definitions',
  'user validation logic',
  'configuration and settings',
]

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = pct >= 40 ? '#22c55e' : pct >= 20 ? '#f59e0b' : '#64748b'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <div style={{
        width: '60px', height: '4px', background: 'var(--border)',
        borderRadius: '2px', overflow: 'hidden'
      }}>
        <div style={{
          width: `${Math.min(pct * 2, 100)}%`,
          height: '100%', background: color, borderRadius: '2px'
        }} />
      </div>
      <span style={{ fontSize: '10px', color, fontFamily: 'monospace', fontWeight: '600' }}>
        {pct}%
      </span>
    </div>
  )
}

function ResultCard({ result, index, onClick, selected }: {
  result: SearchResult
  index: number
  onClick: () => void
  selected: boolean
}) {
  const getLang = (lang: string) => {
    const map: Record<string, string> = {
      python: 'python', javascript: 'javascript',
      typescript: 'typescript', jsx: 'javascript', tsx: 'typescript'
    }
    return map[lang] || 'text'
  }

  return (
    <div
      className="card"
      onClick={onClick}
      style={{
        cursor: 'pointer', overflow: 'hidden',
        border: selected ? '1px solid var(--primary)' : '1px solid var(--border)',
        boxShadow: selected ? '0 0 0 1px var(--primary)' : 'none',
        transition: 'all 0.15s'
      }}
    >
      {/* Header */}
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: '10px',
        background: selected ? 'var(--primary-glow)' : 'var(--bg-elevated)'
      }}>
        {/* Rank */}
        <div style={{
          width: '22px', height: '22px', borderRadius: '6px',
          background: selected ? 'var(--primary)' : 'var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '10px', fontWeight: '800', color: 'white',
          flexShrink: 0, fontFamily: 'monospace'
        }}>
          {index + 1}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            marginBottom: '2px', flexWrap: 'wrap'
          }}>
            <FileCode size={11} color="var(--primary)" />
            <span style={{
              fontSize: '12px', fontFamily: 'monospace',
              color: 'var(--text)', fontWeight: '600',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
            }}>
              {result.file_path.split('/').pop()}
            </span>
            {result.symbol_name && (
              <>
                <ChevronRight size={10} color="var(--text-muted)" />
                <span style={{
                  fontSize: '11px', color: 'var(--primary)',
                  fontFamily: 'monospace'
                }}>
                  {result.symbol_name}
                </span>
                <span style={{
                  fontSize: '10px', padding: '1px 6px',
                  borderRadius: '3px', background: 'rgba(99,102,241,0.1)',
                  color: 'var(--primary)', fontFamily: 'monospace'
                }}>
                  {result.symbol_type}
                </span>
              </>
            )}
          </div>
          <div style={{
            fontSize: '10px', color: 'var(--text-muted)',
            fontFamily: 'monospace', overflow: 'hidden',
            textOverflow: 'ellipsis', whiteSpace: 'nowrap'
          }}>
            {result.file_path} · L{result.start_line}–{result.end_line}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', flexShrink: 0 }}>
          <ScoreBar score={result.score} />
          <span style={{
            fontSize: '9px', color: 'var(--text-muted)',
            background: 'var(--bg-elevated)', padding: '1px 6px',
            borderRadius: '3px', border: '1px solid var(--border)'
          }}>
            {result.language}
          </span>
        </div>
      </div>

      {/* Code preview */}
      <div style={{ maxHeight: selected ? '400px' : '120px', overflow: 'hidden', transition: 'max-height 0.3s ease' }}>
        <SyntaxHighlighter
          language={getLang(result.language)}
          style={atomOneDark}
          showLineNumbers
          startingLineNumber={result.start_line}
          customStyle={{
            margin: 0, borderRadius: 0,
            background: '#0a0a0f',
            fontSize: '11px', lineHeight: '1.5',
            fontFamily: 'JetBrains Mono, monospace',
            padding: '10px 14px'
          }}
          lineNumberStyle={{
            color: '#334155', minWidth: '36px',
            paddingRight: '12px', userSelect: 'none'
          }}
        >
          {result.content}
        </SyntaxHighlighter>
      </div>
    </div>
  )
}

export default function SearchPage() {
  const [repos, setRepos] = useState<Repository[]>([])
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searched, setSearched] = useState(false)
  const [selectedResult, setSelectedResult] = useState<number | null>(null)
  const [nResults, setNResults] = useState(10)
  const [showSettings, setShowSettings] = useState(false)

  useEffect(() => { loadRepos() }, [])

  async function loadRepos() {
    try {
      const res = await getRepositories()
      const ready = res.data.filter((r: Repository) => r.status === 'READY')
      setRepos(ready)
      if (ready.length > 0) setSelectedRepo(ready[0])
    } catch (err) { console.error(err) }
  }

  async function handleSearch(q?: string) {
    const searchQuery = q || query.trim()
    if (!searchQuery || !selectedRepo) return

    if (q) setQuery(q)
    setSearching(true)
    setResults([])
    setSearched(false)
    setSelectedResult(null)

    try {
      const res = await searchCode(selectedRepo.id, searchQuery, nResults)
      setResults(res.data.results || [])
      setSearched(true)
    } catch (err) {
      console.error(err)
    } finally {
      setSearching(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <TopBar title="Semantic Search" subtitle="Find relevant code using natural language" />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Left sidebar */}
        <div style={{
          width: '220px', minWidth: '220px',
          borderRight: '1px solid var(--border)',
          background: 'var(--bg-surface)',
          display: 'flex', flexDirection: 'column',
          padding: '12px', gap: '12px'
        }}>
          {/* Repo selector */}
          <div>
            <div style={{
              fontSize: '10px', color: 'var(--text-muted)',
              textTransform: 'uppercase', letterSpacing: '0.05em',
              marginBottom: '8px', fontWeight: '600'
            }}>Repository</div>
            {repos.map(repo => (
              <button key={repo.id}
                onClick={() => { setSelectedRepo(repo); setResults([]); setSearched(false) }}
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

          {/* Settings */}
          <div>
            <button
              onClick={() => setShowSettings(!showSettings)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '6px 10px', borderRadius: '6px', border: 'none',
                cursor: 'pointer', width: '100%', textAlign: 'left',
                background: 'transparent', color: 'var(--text-muted)',
                fontSize: '11px', fontWeight: '600',
                textTransform: 'uppercase', letterSpacing: '0.05em'
              }}
            >
              <SlidersHorizontal size={11} />
              Settings
            </button>

            {showSettings && (
              <div style={{ padding: '8px 10px' }} className="animate-fade-in">
                <div style={{
                  fontSize: '10px', color: 'var(--text-muted)',
                  marginBottom: '6px'
                }}>
                  Results: {nResults}
                </div>
                <input
                  type="range" min={5} max={30} value={nResults}
                  onChange={e => setNResults(Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--primary)' }}
                />
                <div style={{
                  display: 'flex', justifyContent: 'space-between',
                  fontSize: '9px', color: 'var(--text-muted)'
                }}>
                  <span>5</span><span>30</span>
                </div>
              </div>
            )}
          </div>

          {/* Stats */}
          {searched && (
            <div className="animate-fade-in" style={{
              padding: '10px', borderRadius: '8px',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)'
            }}>
              <div style={{
                fontSize: '10px', color: 'var(--text-muted)',
                marginBottom: '6px', fontWeight: '600',
                textTransform: 'uppercase'
              }}>
                Results
              </div>
              <div style={{ fontSize: '22px', fontWeight: '800', fontFamily: 'monospace', color: 'var(--primary)' }}>
                {results.length}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                chunks matched
              </div>
              {results.length > 0 && (
                <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                  Top score:{' '}
                  <span style={{ color: '#22c55e', fontWeight: '700' }}>
                    {Math.round(results[0].score * 100)}%
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Main content */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {/* Search bar */}
          <div style={{
            padding: '16px 24px',
            borderBottom: '1px solid var(--border)',
            background: 'var(--bg-surface)'
          }}>
            <div style={{
              display: 'flex', gap: '10px', alignItems: 'center',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-bright)',
              borderRadius: '10px', padding: '10px 16px',
              transition: 'border-color 0.2s'
            }}>
              <Search size={16} color="var(--text-muted)" />
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="Search code semantically... e.g. 'authentication logic' or 'database queries'"
                style={{
                  flex: 1, background: 'none', border: 'none',
                  color: 'var(--text)', fontSize: '13px', outline: 'none',
                  fontFamily: 'Inter, sans-serif'
                }}
              />
              {query && (
                <button
                  onClick={() => handleSearch()}
                  disabled={searching}
                  style={{
                    background: 'linear-gradient(135deg, #6366f1, #7c3aed)',
                    border: 'none', borderRadius: '6px',
                    padding: '6px 14px', color: 'white',
                    cursor: 'pointer', fontSize: '12px', fontWeight: '600',
                    display: 'flex', alignItems: 'center', gap: '6px',
                    flexShrink: 0, boxShadow: '0 0 12px rgba(99,102,241,0.3)'
                  }}
                >
                  {searching
                    ? <Loader size={12} style={{ animation: 'spin 1s linear infinite' }} />
                    : <Zap size={12} />
                  }
                  {searching ? 'Searching...' : 'Search'}
                </button>
              )}
            </div>
          </div>

          {/* Results area */}
          <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px' }}>

            {/* Empty state */}
            {!searched && !searching && (
              <div className="animate-fade-in" style={{
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                minHeight: '60%', textAlign: 'center', padding: '40px'
              }}>
                <div style={{
                  width: '56px', height: '56px', borderRadius: '14px',
                  background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginBottom: '16px',
                  boxShadow: '0 0 30px rgba(99,102,241,0.3)'
                }}>
                  <Search size={24} color="white" />
                </div>
                <h3 style={{ fontSize: '16px', fontWeight: '700', marginBottom: '8px' }}>
                  Semantic Code Search
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: '24px', maxWidth: '400px' }}>
                  Search your codebase using natural language. Find functions, classes, and logic by describing what they do.
                </p>

                {/* Example queries */}
                <div style={{
                  display: 'grid', gridTemplateColumns: '1fr 1fr',
                  gap: '8px', maxWidth: '500px', width: '100%'
                }}>
                  {EXAMPLE_QUERIES.map(q => (
                    <button key={q} onClick={() => handleSearch(q)}
                      style={{
                        padding: '10px 14px', borderRadius: '8px',
                        border: '1px solid var(--border-bright)',
                        background: 'var(--bg-surface)', color: 'var(--text)',
                        cursor: 'pointer', fontSize: '12px', textAlign: 'left',
                        transition: 'all 0.15s', lineHeight: '1.4'
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.borderColor = 'var(--primary)'
                        e.currentTarget.style.background = 'var(--primary-glow)'
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.borderColor = 'var(--border-bright)'
                        e.currentTarget.style.background = 'var(--bg-surface)'
                      }}
                    >
                      <Code2 size={11} color="var(--primary)"
                        style={{ marginBottom: '4px', display: 'block' }} />
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Searching state */}
            {searching && (
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
                  <Search size={20} color="white" />
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '14px', fontWeight: '600', marginBottom: '4px' }}>
                    Searching codebase...
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Running semantic retrieval + reranking
                  </div>
                </div>
              </div>
            )}

            {/* No results */}
            {searched && results.length === 0 && !searching && (
              <div style={{
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                padding: '60px', textAlign: 'center'
              }}>
                <Search size={40} color="var(--text-muted)"
                  style={{ marginBottom: '12px', opacity: 0.3 }} />
                <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '6px' }}>
                  No results found
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                  Try different search terms or select a different repository
                </p>
              </div>
            )}

            {/* Results */}
            {results.length > 0 && !searching && (
              <div className="animate-fade-in">
                <div style={{
                  display: 'flex', alignItems: 'center',
                  justifyContent: 'space-between', marginBottom: '12px'
                }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    <span style={{ color: 'var(--text)', fontWeight: '700' }}>
                      {results.length}
                    </span> results for{' '}
                    <span style={{
                      color: 'var(--primary)', fontFamily: 'monospace',
                      background: 'var(--primary-glow)', padding: '1px 6px',
                      borderRadius: '4px'
                    }}>
                      "{query}"
                    </span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Click to expand
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {results.map((result, i) => (
                    <ResultCard
                      key={i}
                      result={result}
                      index={i}
                      selected={selectedResult === i}
                      onClick={() => setSelectedResult(selectedResult === i ? null : i)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
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