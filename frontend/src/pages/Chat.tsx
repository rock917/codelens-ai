import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useEffect, useState, useRef } from 'react'
import {
  Send,
  Bot,
  User,
  GitBranch,
  FileCode,
  ChevronRight,
  MessageSquare,
  Plus,
  Pencil,
  Trash2,
  X,
  Check,
  Zap,
} from 'lucide-react'
import TopBar from '../components/layout/TopBar'
import './chat.css'
import {
  getRepositories,
  sendMessageStream,
  getConversations, getChatHistory, renameConversation, deleteConversation,
} from '../services/api'
import type {
  Repository,
  ChatMessage,
  Conversation,
  SourceReference,
} from '../types'


// ============================================================
// CLEAN AI RESPONSE
// ============================================================

function cleanAssistantMarkdown(
  content: string,
  hasSources: boolean = false
): string {
  if (!content) return ''

  let text = content

  // ==========================================================
  // BASIC NORMALIZATION
  // ==========================================================

  text = text
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/[\u200B-\u200D\uFEFF]/g, '')

  // ==========================================================
  // REMOVE AI-GENERATED SOURCES SECTION
  //
  // The real sources are rendered by the frontend below the
  // message, so the AI should not render its own duplicate
  // source section.
  //
  // Examples:
  //
  // **Sources · 8**
  // Sources · 8
  // ### Sources
  // Sources:
  // ==========================================================

  if (hasSources) {
    text = text.replace(
      /(?:^|\n)\s*(?:#{1,4}\s*)?(?:\*\*)?\s*Sources(?:\s*·\s*\d+)?\s*(?:\*\*)?\s*:?\s*\n[\s\S]*$/i,
      '\n'
    )
  }

  // ==========================================================
  // REMOVE STANDALONE SVG ARTIFACTS
  // ==========================================================

  text = text.replace(
    /^\s*svg\s*$/gim,
    ''
  )

  text = text.replace(
    /^\s*svgSources(?:\s*[·•\-]\s*\d+)?\s*$/gim,
    ''
  )

  // ==========================================================
  // REMOVE CONCATENATED SOURCE ARTIFACTS
  //
  // Examples:
  //
  // svgauth.tsL24-27
  // svgsecurity.pysvgrequire_authL65-83
  // svgcelery_worker.pyL1-12
  // svgauth.tsL47-50
  // ==========================================================

  text = text.replace(
    /^\s*svg[A-Za-z0-9_.\/\\-]+(?:L\d+(?:-\d+)?)?(?:svg[A-Za-z0-9_.\/\\-]+(?:L\d+(?:-\d+)?)?)*\s*$/gim,
    ''
  )

  // ==========================================================
  // REMOVE SOURCE ARTIFACTS THAT MAY APPEAR INSIDE A LINE
  // ==========================================================

  text = text.replace(
    /svgSources(?:\s*[·•\-]\s*\d+)?/gi,
    ''
  )

  // Remove "svg" directly before common source filenames
  text = text.replace(
    /\bsvg(?=[A-Za-z0-9_.\/\\-]+\.(?:py|ts|tsx|js|jsx|java|cpp|c|h|go|rs|rb|php|json|md|yml|yaml))\b/gi,
    ''
  )

  // ==========================================================
  // REMOVE COMMON SVG UI LABELS
  // ==========================================================

  text = text.replace(
    /\bsvg(?:frontend|backend|source|sources|file|files|icon|iconfile)\b/gi,
    ''
  )

  // ==========================================================
  // REMOVE STRAY "code" LINES
  //
  // Sometimes the model produces:
  //
  // code
  // useAuth
  // code
  //
  // instead of normal Markdown.
  // ==========================================================

  text = text.replace(
    /^\s*code\s*$/gim,
    ''
  )

  // ==========================================================
  // REMOVE RANDOM GENERATED ID ATTRIBUTES
  //
  // Example:
  //
  // ``` id="f5x1p6"
  // ==========================================================

  text = text.replace(
    /```[\t ]+id=["'][^"']+["']/gi,
    '```'
  )

  // ==========================================================
  // CLEAN SINGLE-LINE FENCED CODE BLOCKS
  //
  // Example:
  //
  // ```
  // useAuth
  // ```
  //
  // becomes:
  //
  // `useAuth`
  // ==========================================================

  text = text.replace(
    /```(?:[a-zA-Z0-9_+-]+)?\s*\n\s*([^`\n]+?)\s*\n\s*```/g,
    (_match, code) => {
      const value = String(code).trim()

      if (!value) {
        return ''
      }

      // Keep expressions/code snippets as proper code blocks.
      if (
        value.includes('=') ||
        value.includes('(') ||
        value.includes('{') ||
        value.includes('}') ||
        value.includes('=>') ||
        value.includes(';')
      ) {
        return _match
      }

      return `\`${value}\``
    }
  )

  // ==========================================================
  // CLEAN MALFORMED MARKDOWN TABLES
  //
  // If the AI returns a proper table, ReactMarkdown can render it.
  //
  // If it returns something malformed like:
  //
  // | **LayerWhat it doesKey code** | | |
  // | ----------------------------- | --- |
  //
  // we convert it into readable bullet points.
  // ==========================================================

  const lines = text.split('\n')
  const result: string[] = []

  let tableBuffer: string[] = []

  function flushTable() {
    if (tableBuffer.length === 0) {
      return
    }

    const rows = tableBuffer
      .filter(line => line.includes('|'))
      .map(line => {
        const cells = line
          .split('|')
          .map(cell => cell.trim())
          .filter(Boolean)

        // Ignore separator row
        if (
          cells.length > 0 &&
          cells.every(cell =>
            /^:?-{2,}:?$/.test(cell)
          )
        ) {
          return null
        }

        return cells.join(' — ')
      })
      .filter(
        (row): row is string =>
          Boolean(row && row.trim())
      )

    if (rows.length > 0) {
      rows.forEach(row => {
        result.push(`- ${row}`)
      })
    }

    tableBuffer = []
  }

  for (const line of lines) {
    const trimmed = line.trim()

    const isTableRow =
      trimmed.startsWith('|') &&
      trimmed.endsWith('|')

    const isSeparator =
      /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?$/.test(
        trimmed
      )

    if (isTableRow || isSeparator) {
      tableBuffer.push(line)
    } else {
      if (tableBuffer.length > 0) {
        flushTable()
      }

      result.push(line)
    }
  }

  if (tableBuffer.length > 0) {
    flushTable()
  }

  text = result.join('\n')

  // ==========================================================
  // FINAL CLEANUP
  // ==========================================================

  text = text
    .replace(/^[ \t]+$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  return text
}


// ============================================================
// SOURCE CARD
// ============================================================

function SourceCard({
  source,
}: {
  source: SourceReference
}) {
  const fileName =
    source.file_path.split('/').pop() ||
    source.file_path

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '5px 10px',
        borderRadius: '6px',
        background: 'var(--bg-base)',
        border: '1px solid var(--border-bright)',
        fontSize: '11px',
        cursor: 'pointer',
        transition: 'all 0.15s',
        maxWidth: '100%',
        minWidth: 0,
      }}
      title={source.file_path}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor =
          'var(--primary)'

        e.currentTarget.style.background =
          'var(--primary-glow)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor =
          'var(--border-bright)'

        e.currentTarget.style.background =
          'var(--bg-base)'
      }}
    >
      <FileCode
        size={10}
        color="var(--primary)"
        style={{ flexShrink: 0 }}
      />

      <span
        style={{
          color: 'var(--text)',
          fontFamily:
            'JetBrains Mono, Consolas, monospace',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {fileName}
      </span>

      {source.symbol_name && (
        <>
          <ChevronRight
            size={10}
            color="var(--text-muted)"
            style={{ flexShrink: 0 }}
          />

          <span
            style={{
              color: 'var(--primary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {source.symbol_name}
          </span>
        </>
      )}

      <span
        style={{
          color: 'var(--text-muted)',
          whiteSpace: 'nowrap',
          flexShrink: 0,
        }}
      >
        L{source.start_line}-{source.end_line}
      </span>
    </div>
  )
}


// ============================================================
// MESSAGE BUBBLE
// ============================================================

function MessageBubble({
  message,
}: {
  message: ChatMessage
}) {
  const isUser = message.role === 'user'

  const sources: SourceReference[] =
    message.sources || []

  const displayContent = isUser
    ? message.content
    : cleanAssistantMarkdown(
        message.content,
        sources.length > 0
      )

  return (
    <div
      className="animate-fade-in"
      style={{
        display: 'flex',
        gap: '12px',
        flexDirection: isUser
          ? 'row-reverse'
          : 'row',
        marginBottom: '24px',
        width: '100%',
      }}
    >
      {/* Avatar */}
      <div
        style={{
          width: '32px',
          height: '32px',
          borderRadius: '8px',
          background: isUser
            ? 'var(--brand-gradient)'
            : 'linear-gradient(135deg, var(--bg-surface), var(--border))',
          border:
            '1px solid var(--border-bright)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          boxShadow: isUser
            ? '0 0 12px color-mix(in srgb,var(--primary) 30%,transparent)'
            : 'none',
        }}
      >
        {isUser ? (
          <User size={14} color="var(--on-primary)" />
        ) : (
          <Zap
            size={14}
            color="var(--primary)"
          />
        )}
      </div>

      {/* Content */}
      <div
        style={{
          maxWidth: '80%',
          minWidth: '200px',
          overflow: 'hidden',
        }}
      >
        {/* Role label */}
        <div
          style={{
            fontSize: '11px',
            color: 'var(--text-muted)',
            marginBottom: '6px',
            fontWeight: '500',
            textAlign: isUser
              ? 'right'
              : 'left',
          }}
        >
          {isUser
            ? 'You'
            : 'CodeLens AI'}
        </div>

        {/* Message bubble */}
        <div
          style={{
            padding: '12px 16px',
            borderRadius: isUser
              ? '12px 4px 12px 12px'
              : '4px 12px 12px 12px',
            background: isUser
              ? 'var(--brand-gradient)'
              : 'var(--bg-surface)',
            border: isUser
              ? 'none'
              : '1px solid var(--border)',
            color: isUser ? 'var(--on-primary)' : 'var(--text)',
            fontSize: '13px',
            lineHeight: '1.6',
            wordBreak: 'break-word',
            overflowWrap: 'anywhere',
          }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // ==================================================
              // PARAGRAPH
              // ==================================================

              p: ({ node, ...props }) => (
                <p
                  style={{
                    margin:
                      '0 0 10px 0',
                    lineHeight: '1.65',
                  }}
                  {...props}
                />
              ),

              // ==================================================
              // HEADINGS
              // ==================================================

              h1: ({
                node,
                ...props
              }) => (
                <h1
                  style={{
                    fontSize: '17px',
                    fontWeight: '700',
                    margin:
                      '14px 0 8px',
                    color:
                      'inherit',
                    lineHeight:
                      '1.35',
                  }}
                  {...props}
                />
              ),

              h2: ({
                node,
                ...props
              }) => (
                <h2
                  style={{
                    fontSize: '15px',
                    fontWeight: '700',
                    margin:
                      '14px 0 8px',
                    color:
                      'inherit',
                    lineHeight:
                      '1.4',
                  }}
                  {...props}
                />
              ),

              h3: ({
                node,
                ...props
              }) => (
                <h3
                  style={{
                    fontSize: '14px',
                    fontWeight: '600',
                    margin:
                      '12px 0 6px',
                    color:
                      'inherit',
                    lineHeight:
                      '1.4',
                  }}
                  {...props}
                />
              ),

              h4: ({
                node,
                ...props
              }) => (
                <h4
                  style={{
                    fontSize: '13px',
                    fontWeight: '600',
                    margin:
                      '10px 0 6px',
                    color:
                      'inherit',
                  }}
                  {...props}
                />
              ),

              // ==================================================
              // STRONG
              // ==================================================

              strong: ({
                node,
                ...props
              }) => (
                <strong
                  style={{
                    fontWeight: '650',
                    color:
                      'inherit',
                  }}
                  {...props}
                />
              ),

              // ==================================================
              // EMPHASIS
              // ==================================================

              em: ({
                node,
                ...props
              }) => (
                <em
                  style={{
                    color:
                      'inherit',
                  }}
                  {...props}
                />
              ),

              // ==================================================
              // UNORDERED LIST
              // ==================================================

              ul: ({
                node,
                ...props
              }) => (
                <ul
                  style={{
                    paddingLeft: '20px',
                    margin:
                      '6px 0 10px',
                  }}
                  {...props}
                />
              ),

              // ==================================================
              // ORDERED LIST
              // ==================================================

              ol: ({
                node,
                ...props
              }) => (
                <ol
                  style={{
                    paddingLeft: '22px',
                    margin:
                      '6px 0 10px',
                  }}
                  {...props}
                />
              ),

              // ==================================================
              // LIST ITEM
              // ==================================================

              li: ({
                node,
                ...props
              }) => (
                <li
                  style={{
                    marginBottom:
                      '5px',
                    lineHeight:
                      '1.55',
                    paddingLeft:
                      '2px',
                  }}
                  {...props}
                />
              ),

              // ==================================================
              // CODE
              // ==================================================

              code: ({
                node,
                inline,
                className,
                children,
                ...props
              }: any) => {
                if (inline) {
                  return (
                    <code
                      style={{
                        background:
                          'var(--bg-elevated)',
                        padding:
                          '2px 6px',
                        borderRadius:
                          '4px',
                        fontSize:
                          '12px',
                        fontFamily:
                          'JetBrains Mono, Consolas, monospace',
                        color:
                          'var(--primary)',
                        border:
                          '1px solid var(--border)',
                      }}
                      {...props}
                    >
                      {children}
                    </code>
                  )
                }

                return (
                  <pre
                    style={{
                      background:
                        'var(--bg-base)',
                      padding: '12px',
                      borderRadius:
                        '7px',
                      overflowX:
                        'auto',
                      fontSize:
                        '12px',
                      border:
                        '1px solid var(--border)',
                      margin:
                        '10px 0',
                      maxWidth:
                        '100%',
                      whiteSpace:
                        'pre',
                    }}
                  >
                    <code
                      className={
                        className
                      }
                      style={{
                        fontFamily:
                          'JetBrains Mono, Consolas, monospace',
                        color:
                          'var(--text)',
                        lineHeight:
                          '1.55',
                      }}
                      {...props}
                    >
                      {children}
                    </code>
                  </pre>
                )
              },

              // ==================================================
              // BLOCKQUOTE
              // ==================================================

              blockquote: ({
                node,
                ...props
              }) => (
                <blockquote
                  style={{
                    margin:
                      '10px 0',
                    padding:
                      '8px 12px',
                    borderLeft:
                      '3px solid var(--primary)',
                    background:
                      'var(--bg-elevated)',
                    color:
                      'var(--text-muted)',
                    borderRadius:
                      '0 5px 5px 0',
                  }}
                  {...props}
                />
              ),

              // ==================================================
              // LINKS
              // ==================================================

              a: ({
                node,
                ...props
              }) => (
                <a
                  style={{
                    color:
                      isUser ? 'var(--on-primary)' : 'var(--primary)',
                    textDecoration:
                      'underline',
                    textUnderlineOffset:
                      '2px',
                  }}
                  target="_blank"
                  rel="noopener noreferrer"
                  {...props}
                />
              ),

              // ==================================================
              // HORIZONTAL RULE
              // ==================================================

              hr: ({
                node,
                ...props
              }) => (
                <hr
                  style={{
                    border: 'none',
                    borderTop:
                      '1px solid var(--border)',
                    margin:
                      '14px 0',
                  }}
                  {...props}
                />
              ),

              // ==================================================
              // TABLE
              // ==================================================

              table: ({
                node,
                ...props
              }) => (
                <div
                  style={{
                    width: '100%',
                    overflowX:
                      'auto',
                    margin:
                      '10px 0',
                    border:
                      '1px solid var(--border)',
                    borderRadius:
                      '7px',
                  }}
                >
                  <table
                    style={{
                      background: 'var(--bg-base)',
                      borderCollapse:
                        'collapse',
                      width: '100%',
                      minWidth:
                        '420px',
                      fontSize:
                        '12px',
                    }}
                    {...props}
                  />
                </div>
              ),

              thead: ({
                node,
                ...props
              }) => (
                <thead
                  style={{
                    background:
                      'var(--bg-elevated)',
                  }}
                  {...props}
                />
              ),

              tbody: ({
                node,
                ...props
              }) => (
                <tbody
                  {...props}
                />
              ),

              tr: ({
                node,
                ...props
              }) => (
                <tr
                  style={{
                    borderBottom:
                      '1px solid var(--border)',
                  }}
                  {...props}
                />
              ),

              th: ({
                node,
                ...props
              }) => (
                <th
                  style={{
                    padding:
                      '7px 10px',
                    textAlign:
                      'left',
                    borderBottom:
                      '1px solid var(--border-bright)',
                    color:
                      'var(--text-muted)',
                    fontWeight:
                      '600',
                    fontSize:
                      '11px',
                    whiteSpace:
                      'nowrap',
                  }}
                  {...props}
                />
              ),

              td: ({
                node,
                ...props
              }) => (
                <td
                  style={{
                    padding:
                      '7px 10px',
                    borderBottom:
                      '1px solid var(--border)',
                    color:
                      'var(--text)',
                    verticalAlign:
                      'top',
                  }}
                  {...props}
                />
              ),

              // ==================================================
              // IMAGE
              // ==================================================

              img: ({
                node,
                ...props
              }) => (
                <img
                  style={{
                    maxWidth:
                      '100%',
                    borderRadius:
                      '6px',
                  }}
                  {...props}
                />
              ),

              // ==================================================
              // STRIKETHROUGH
              // ==================================================

              del: ({
                node,
                ...props
              }) => (
                <del
                  style={{
                    color:
                      isUser ? 'var(--on-primary)' : 'var(--text-muted)',
                  }}
                  {...props}
                />
              ),
            }}
          >
            {displayContent}
          </ReactMarkdown>
        </div>


        {/* ======================================================
            REAL SOURCES FROM BACKEND
        ====================================================== */}

        {!isUser &&
          sources.length > 0 && (
            <div
              style={{
                marginTop: '10px',
              }}
            >
              <div
                style={{
                  fontSize: '10px',
                  color:
                    'var(--text-muted)',
                  marginBottom:
                    '6px',
                  fontWeight: '500',
                  textTransform:
                    'uppercase',
                  letterSpacing:
                    '0.05em',
                }}
              >
                Sources ·{' '}
                {sources.length}
              </div>

              <div
                style={{
                  display:
                    'flex',
                  flexWrap:
                    'wrap',
                  gap: '6px',
                }}
              >
                {sources
                  .slice(0, 6)
                  .map((src, i) => (
                    <SourceCard
                      key={`${src.file_path}-${src.start_line}-${i}`}
                      source={src}
                    />
                  ))}
              </div>

              {sources.length >
                6 && (
                <div
                  style={{
                    marginTop:
                      '6px',
                    fontSize:
                      '10px',
                    color:
                      'var(--text-muted)',
                  }}
                >
                  +
                  {sources.length -
                    6}{' '}
                  more sources
                </div>
              )}
            </div>
          )}
      </div>
    </div>
  )
}


// ============================================================
// TYPING INDICATOR
// ============================================================

function TypingIndicator() {
  return (
    <div
      className="animate-fade-in"
      style={{
        display: 'flex',
        gap: '12px',
        marginBottom: '24px',
      }}
    >
      <div
        style={{
          width: '32px',
          height: '32px',
          borderRadius: '8px',
          background:
            'linear-gradient(135deg, var(--bg-surface), var(--border))',
          border:
            '1px solid var(--border-bright)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <Zap
          size={14}
          color="var(--primary)"
        />
      </div>

      <div
        style={{
          padding: '12px 16px',
          borderRadius:
            '4px 12px 12px 12px',
          background:
            'var(--bg-surface)',
          border:
            '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
        }}
      >
        {[0, 1, 2].map(i => (
          <div
            key={i}
            style={{
              width: '6px',
              height: '6px',
              borderRadius:
                '50%',
              background:
                'var(--primary)',
              animation:
                `bounce 1.2s ease-in-out ${
                  i * 0.2
                }s infinite`,
            }}
          />
        ))}
      </div>
    </div>
  )
}


// ============================================================
// SUGGESTED QUESTIONS
// ============================================================

const SUGGESTED_QUESTIONS = [
  'How does authentication work?',
  'Explain the main entry point',
  'What are the database models?',
  'Find any security issues',
  'How is error handling done?',
  'What are the API endpoints?',
]


// ============================================================
// MAIN CHAT COMPONENT
// ============================================================

export default function Chat() {
  const [repos, setRepos] = useState<Repository[]>([])
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedConv, setSelectedConv] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [loadingList, setLoadingList] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [editing, setEditing] = useState<Conversation | null>(null)
  const [title, setTitle] = useState('')
  const [deleting, setDeleting] = useState<Conversation | null>(null)
  const [mutating, setMutating] = useState(false)
  const [actionError, setActionError] = useState('')
  const selection = useRef(0)
  const listRequest = useRef(0)
  const stream = useRef<AbortController | null>(null)
  const pollTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  function changeSelection() {
    stream.current?.abort()
    clearTimeout(pollTimer.current)
    selection.current += 1
    setLoading(false); setLoadingHistory(false); setLoadingList(false)
    setError(''); setSaved(false); setInput(''); setEditing(null); setDeleting(null)
    return selection.current
  }

  useEffect(() => {
    let active = true
    void getRepositories().then(res => {
      if (!active) return
      const ready = res.data.filter((repo: Repository) => repo.status === 'READY')
      setRepos(ready)
      if (ready.length) void selectRepo(ready[0])
    }).catch(() => { if (active) setError('Unable to load repositories. Refresh the page to retry.') })
    return () => {
      active = false; selection.current += 1
      stream.current?.abort(); clearTimeout(pollTimer.current)
    }
  }, [])

  useEffect(() => { messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' }) }, [messages, loading])

  async function refreshConversations(repoId: string, version: number) {
    const request = ++listRequest.current
    const { data } = await getConversations(repoId)
    if (selection.current === version && listRequest.current === request) setConversations(data)
    return data as Conversation[]
  }

  async function readConversation(convId: string, repoId: string, version: number) {
    const request = ++listRequest.current
    try {
      const [history, list] = await Promise.all([getChatHistory(convId), getConversations(repoId)])
      if (selection.current !== version) return
      setMessages(history.data)
      if (listRequest.current === request) setConversations(list.data)
      const pending = list.data.some((c: Conversation) => c.id === convId && c.is_generating)
      setLoading(pending); setLoadingHistory(false); setSaved(!pending)
      if (pending) pollTimer.current = setTimeout(() => void readConversation(convId, repoId, version), 2000)
    } catch {
      if (selection.current === version) {
        setLoadingHistory(false); setLoading(false)
        setError('Unable to load saved messages. Reopen the conversation to retry.')
      }
    }
  }

  async function selectRepo(repo: Repository) {
    const version = changeSelection()
    setSelectedRepo(repo); setSelectedConv(null); setMessages([]); setConversations([]); setLoadingList(true)
    try {
      const list = await refreshConversations(repo.id, version)
      if (selection.current !== version) return
      if (list.length) {
        setSelectedConv(list[0].id); setLoadingHistory(true)
        await readConversation(list[0].id, repo.id, version)
      }
    } catch {
      if (selection.current === version) setError('Unable to load conversations. Select the repository again to retry.')
    } finally { if (selection.current === version) setLoadingList(false) }
  }

  function selectConversation(convId: string) {
    if (!selectedRepo) return
    const version = changeSelection()
    setSelectedConv(convId); setMessages([]); setLoadingHistory(true)
    void readConversation(convId, selectedRepo.id, version)
  }

  function startNewChat() {
    changeSelection(); setSelectedConv(null); setMessages([])
    inputRef.current?.focus()
  }

  async function handleSend(text?: string) {
    const question = (text || input).trim()
    if (!question || !selectedRepo || loading || loadingHistory || loadingList || mutating) return
    const version = selection.current
    const repoId = selectedRepo.id
    const controller = new AbortController()
    stream.current = controller
    const active = () => selection.current === version && !controller.signal.aborted
    setInput(''); setLoading(true); setError(''); setSaved(false)
    let convId = selectedConv
    let complete = false
    let failure = ''
    const assistantId = crypto.randomUUID()
    setMessages(prev => [...prev,
      { id: crypto.randomUUID(), role: 'user', content: question, created_at: new Date().toISOString() },
      { id: assistantId, role: 'assistant', content: '', sources: [], created_at: new Date().toISOString() },
    ])
    let content = ''
    await sendMessageStream(repoId, question, convId || undefined,
      token => {
        if (!active()) return
        content += token
        setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content } : m))
      },
      sources => { if (active()) setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, sources } : m)) },
      meta => {
        if (!active()) return
        convId = meta.conversation_id; setSelectedConv(convId)
        void refreshConversations(repoId, version).catch(() => {})
      },
      () => { complete = true },
      message => { failure = message },
      controller.signal,
    )
    if (!active()) return
    setSaved(complete)
    if (failure) {
      setError(failure)
      // Partial streamed text is not a completed, saved answer.
      setMessages(prev => prev.filter(m => m.id !== assistantId))
    }
    try {
      await refreshConversations(repoId, version)
      if (convId) {
        const history = await getChatHistory(convId)
        if (active()) { setMessages(history.data); setSaved(true) }
      }
    } catch { if (active()) setError('Unable to refresh saved history. Reopen the conversation to check it.') }
    if (active()) { setLoading(false); inputRef.current?.focus() }
  }

  async function saveTitle() {
    if (!editing || !title.trim() || !selectedRepo) return
    const version = selection.current
    setMutating(true); setActionError('')
    try {
      await renameConversation(editing.id, title.trim())
      await refreshConversations(selectedRepo.id, version)
      if (selection.current === version) setEditing(null)
    } catch { if (selection.current === version) setActionError('Unable to rename this conversation. Please try again.') }
    finally { setMutating(false) }
  }

  async function removeConversation() {
    if (!deleting || !selectedRepo) return
    const version = selection.current
    const convId = deleting.id
    setMutating(true); setActionError('')
    try {
      await deleteConversation(convId)
      const list = await refreshConversations(selectedRepo.id, version)
      if (selection.current !== version) return
      setDeleting(null)
      if (convId === selectedConv) {
        if (list.length) selectConversation(list[0].id)
        else startNewChat()
      }
    } catch { if (selection.current === version) setActionError('Unable to delete. If a reply is running, wait for it to finish and try again.') }
    finally { setMutating(false) }
  }

  const current = conversations.find(c => c.id === selectedConv)
  const unanswered = saved && selectedConv && !loading && !loadingHistory && messages.at(-1)?.role === 'user'
  return <div className="chat-page">
    <TopBar title="AI Chat" subtitle="Private conversations, saved with your repositories" />
    <div className="chat-layout">
      <aside className="chat-sidebar" aria-label="Chat history">
        <label className="chat-label" htmlFor="chat-repository">Repository</label>
        <select id="chat-repository" value={selectedRepo?.id || ''} disabled={mutating}
          onChange={e => { const repo = repos.find(r => r.id === e.target.value); if (repo) void selectRepo(repo) }}>
          {!repos.length && <option value="">No ready repositories</option>}
          {repos.map(repo => <option key={repo.id} value={repo.id}>{repo.name}</option>)}
        </select>
        <button className="chat-new" onClick={startNewChat} disabled={!selectedRepo || loadingList || mutating}><Plus size={15} /> New conversation</button>
        <div className="chat-label">Saved conversations</div>
        {loadingList ? <p role="status">Loading history…</p> : conversations.length === 0 && <p className="chat-muted">Your conversations will appear here after your first question.</p>}
        <div className="conversation-list">
          {conversations.map(conv => <div className={`conversation-row ${selectedConv === conv.id ? 'selected' : ''}`} key={conv.id}>
            <button className="conversation-open" disabled={mutating} onClick={() => selectConversation(conv.id)} aria-pressed={selectedConv === conv.id}>
              <MessageSquare size={14} /><span><strong>{conv.title || 'Conversation'}</strong><small>{conv.is_generating ? 'Reply in progress…' : new Date(conv.updated_at || conv.created_at).toLocaleDateString()}</small></span>
            </button>
            <div className="conversation-actions">
              <button aria-label={`Rename ${conv.title || 'conversation'}`} title="Rename" disabled={mutating} onClick={() => { setEditing(conv); setTitle(conv.title || ''); setActionError('') }}><Pencil size={13} /></button>
              <button aria-label={`Delete ${conv.title || 'conversation'}`} title="Delete" disabled={mutating || conv.is_generating || (loading && selectedConv === conv.id)} onClick={() => { setDeleting(conv); setActionError('') }}><Trash2 size={13} /></button>
            </div>
          </div>)}
        </div>
        <p className="chat-history-note">Saved to your account. Reopen a conversation on any device.</p>
      </aside>
      <section className="chat-main" aria-label="Conversation">
        {error && <p className="chat-error" role="alert">{error}</p>}
        {!selectedRepo ? <div className="chat-empty"><Bot size={40} /><h2>Select a repository to start chatting</h2><p>Analyze a repository first, then return here to ask questions.</p></div> : <>
          <header className="chat-heading"><div><GitBranch size={16} /><span>{selectedRepo.name}<small>{current?.title || 'New conversation'}</small></span></div>
            <span className="chat-save-state" role="status">{loading ? 'Generating reply…' : loadingHistory ? 'Loading…' : saved ? <><Check size={13} /> Saved</> : 'Private chat'}</span>
          </header>
          <div className="chat-messages">
            {!messages.length && !loadingHistory && !loadingList && <div className="chat-empty"><Zap size={32} /><h2>Ask about {selectedRepo.name}</h2><p>Explore its architecture, trace a function, or find your next improvement.</p>
              <div className="chat-suggestions">{SUGGESTED_QUESTIONS.map(question => <button key={question} disabled={loading || mutating} onClick={() => void handleSend(question)}>{question}</button>)}</div>
            </div>}
            {loadingHistory && <p role="status">Loading saved messages…</p>}
            {messages.map(message => <MessageBubble key={message.id} message={message} />)}
            {loading && <TypingIndicator />}
            {unanswered && <div className="chat-unanswered">Your question is saved, but there is no completed reply. <button onClick={() => { setInput(messages.at(-1)!.content); inputRef.current?.focus() }}>Use this question again</button></div>}
            <div ref={messagesEndRef} />
          </div>
          <form className="chat-composer" onSubmit={e => { e.preventDefault(); void handleSend() }}>
            <div><textarea ref={inputRef} aria-label="Question" placeholder="Ask about your code…" value={input} maxLength={12000} rows={2}
              disabled={loadingHistory || loadingList || mutating} onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void handleSend() } }} />
              <button type="submit" aria-label="Send question" disabled={!input.trim() || loading || loadingHistory || loadingList || mutating}><Send size={17} /></button></div>
            <small>Enter to send · Shift + Enter for a new line · Completed replies are saved automatically</small>
          </form>
        </>}
      </section>
    </div>
    {(editing || deleting) && <div className="chat-modal-backdrop"><section className="chat-modal" role="dialog" aria-modal="true" aria-labelledby="chat-dialog-title" onKeyDown={e => {
      if (e.key === 'Escape' && !mutating) { setEditing(null); setDeleting(null) }
      if (e.key === 'Tab') {
        const controls = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)'))
        const first = controls[0], last = controls.at(-1)
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() }
      }
    }}>
      <button className="chat-modal-close" aria-label="Close dialog" disabled={mutating} onClick={() => { setEditing(null); setDeleting(null) }}><X size={18} /></button>
      <h2 id="chat-dialog-title">{editing ? 'Rename conversation' : 'Delete conversation?'}</h2>
      {editing ? <form onSubmit={e => { e.preventDefault(); void saveTitle() }}><label htmlFor="conversation-title">Title</label><input id="conversation-title" autoFocus maxLength={120} required value={title} disabled={mutating} onChange={e => setTitle(e.target.value)} /><button className="btn-primary" disabled={mutating || !title.trim()}>{mutating ? 'Saving…' : 'Save title'}</button></form>
        : <><p>“{deleting?.title || 'Conversation'}” and its saved messages will be permanently deleted. Your repository and other conversations will remain.</p><button autoFocus className="btn-secondary" disabled={mutating} onClick={() => setDeleting(null)}>Keep conversation</button><button className="chat-delete-confirm" disabled={mutating} onClick={() => void removeConversation()}>{mutating ? 'Deleting…' : 'Delete permanently'}</button></>}
      {actionError && <p className="chat-error" role="alert">{actionError}</p>}
    </section></div>}
  </div>
}
