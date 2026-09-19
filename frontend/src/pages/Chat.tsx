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
  Loader,
  MessageSquare,
  Plus,
  Clock,
  Zap,
} from 'lucide-react'
import TopBar from '../components/layout/TopBar'
import {
  getRepositories,
  sendMessageStream,
  getConversations, getChatHistory,
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
            ? 'linear-gradient(135deg, #6366f1, #7c3aed)'
            : 'linear-gradient(135deg, #111118, #1e1e2e)',
          border:
            '1px solid var(--border-bright)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          boxShadow: isUser
            ? '0 0 12px rgba(99,102,241,0.3)'
            : 'none',
        }}
      >
        {isUser ? (
          <User size={14} color="white" />
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
              ? 'linear-gradient(135deg, #6366f1, #7c3aed)'
              : 'var(--bg-surface)',
            border: isUser
              ? 'none'
              : '1px solid var(--border)',
            color: 'var(--text)',
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
                      'var(--text)',
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
                      'var(--text)',
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
                      'var(--text)',
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
                      'var(--text)',
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
                      'var(--text)',
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
                      'var(--text)',
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
                      'var(--primary)',
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
                      'var(--text-muted)',
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
            'linear-gradient(135deg, #111118, #1e1e2e)',
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
  const [repos, setRepos] =
    useState<Repository[]>([])

  const [selectedRepo, setSelectedRepo] =
    useState<Repository | null>(null)

  const [conversations, setConversations] =
    useState<Conversation[]>([])

  const [selectedConv, setSelectedConv] =
    useState<string | null>(null)

  const [messages, setMessages] =
    useState<ChatMessage[]>([])

  const [input, setInput] =
    useState('')

  const [loading, setLoading] =
    useState(false)

  const [loadingHistory, setLoadingHistory] =
    useState(false)

  const messagesEndRef =
    useRef<HTMLDivElement>(null)

  const inputRef =
    useRef<HTMLTextAreaElement>(null)


  // ==========================================================
  // EFFECTS
  // ==========================================================

  useEffect(() => {
    loadRepos()
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])


  // ==========================================================
  // LOAD REPOSITORIES
  // ==========================================================

  async function loadRepos() {
    try {
      const res =
        await getRepositories()

      const ready =
        res.data.filter(
          (r: Repository) =>
            r.status === 'READY'
        )

      setRepos(ready)

      if (ready.length > 0) {
        selectRepo(ready[0])
      }
    } catch (err) {
      console.error(err)
    }
  }


  // ==========================================================
  // SELECT REPOSITORY
  // ==========================================================

  async function selectRepo(
    repo: Repository
  ) {
    setSelectedRepo(repo)
    setMessages([])
    setSelectedConv(null)

    try {
      const res =
        await getConversations(
          repo.id
        )

      setConversations(
        res.data
      )
    } catch (err) {
      console.error(err)
    }
  }


  // ==========================================================
  // SELECT CONVERSATION
  // ==========================================================

  async function selectConversation(
    convId: string
  ) {
    setSelectedConv(convId)
    setLoadingHistory(true)

    try {
      const res =
        await getChatHistory(
          convId
        )

      const msgs: ChatMessage[] =
        res.data.map(
          (m: any) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            sources:
              m.sources || [],
            created_at:
              m.created_at,
          })
        )

      setMessages(msgs)
    } catch (err) {
      console.error(err)
    } finally {
      setLoadingHistory(false)
    }
  }


  // ==========================================================
  // SEND MESSAGE
  // ==========================================================

    async function handleSend(text?: string) {
    const question = text || input.trim()
    if (!question || !selectedRepo || loading) return

    setInput('')
    setLoading(true)

    // Add user message immediately
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
      created_at: new Date().toISOString()
    }
    setMessages(prev => [...prev, userMsg])

    // Add empty assistant message for streaming
    const streamingId = (Date.now() + 1).toString()
    const streamingMsg: ChatMessage = {
      id: streamingId,
      role: 'assistant',
      content: '',
      sources: [],
      created_at: new Date().toISOString()
    }
    setMessages(prev => [...prev, streamingMsg])

    let fullContent = ''
    let convId = selectedConv

    await sendMessageStream(
      selectedRepo.id,
      question,
      selectedConv || undefined,

      // onToken — append each token
      (token: string) => {
        fullContent += token
        setMessages(prev => prev.map(m =>
          m.id === streamingId
            ? { ...m, content: fullContent }
            : m
        ))
      },

      // onSources — set sources when done
      (sources: any[]) => {
        setMessages(prev => prev.map(m =>
          m.id === streamingId
            ? { ...m, sources }
            : m
        ))
      },

      // onMeta — get conversation id
      (meta: any) => {
        if (meta.conversation_id && !convId) {
          convId = meta.conversation_id
          setSelectedConv(meta.conversation_id)
          getConversations(selectedRepo.id)
            .then(res => setConversations(res.data))
        }
      },

      // onDone
      () => {
        setLoading(false)
        inputRef.current?.focus()
      },

            // onError
      (_err: string) => {
        setMessages(prev => prev.map(m =>
          m.id === streamingId
            ? { ...m, content: '⚠️ Something went wrong. Please try again.' }
            : m
        ))
        setLoading(false)
      }
    )
  }


  // ==========================================================
  // SCROLL TO BOTTOM
  // ==========================================================

  function scrollToBottom() {
    messagesEndRef.current?.scrollIntoView({
      behavior: 'smooth',
    })
  }


  // ==========================================================
  // KEYBOARD HANDLER
  // ==========================================================

  function handleKeyDown(
    e: React.KeyboardEvent
  ) {
    if (
      e.key === 'Enter' &&
      !e.shiftKey
    ) {
      e.preventDefault()
      handleSend()
    }
  }


  // ==========================================================
  // START NEW CHAT
  // ==========================================================

  function startNewChat() {
    setSelectedConv(null)
    setMessages([])
    inputRef.current?.focus()
  }


  // ==========================================================
  // RENDER
  // ==========================================================

  return (
    <div
      style={{
        display: 'flex',
        flexDirection:
          'column',
        height: '100%',
      }}
    >
      <TopBar
        title="AI Chat"
        subtitle="Ask questions about your codebase"
      />

      <div
        style={{
          display: 'flex',
          flex: 1,
          overflow: 'hidden',
        }}
      >

        {/* ====================================================
            LEFT SIDEBAR
        ==================================================== */}

        <div
          style={{
            width: '240px',
            minWidth: '240px',
            borderRight:
              '1px solid var(--border)',
            display: 'flex',
            flexDirection:
              'column',
            background:
              'var(--bg-surface)',
            overflow: 'hidden',
          }}
        >

          {/* Repository selector */}
          <div
            style={{
              padding: '12px',
              borderBottom:
                '1px solid var(--border)',
            }}
          >
            <div
              style={{
                fontSize: '10px',
                color:
                  'var(--text-muted)',
                textTransform:
                  'uppercase',
                letterSpacing:
                  '0.05em',
                marginBottom:
                  '8px',
                fontWeight:
                  '600',
              }}
            >
              Repository
            </div>

            {repos.length === 0 ? (
              <div
                style={{
                  fontSize: '12px',
                  color:
                    'var(--text-muted)',
                }}
              >
                No ready repositories
              </div>
            ) : (
              <div
                style={{
                  display:
                    'flex',
                  flexDirection:
                    'column',
                  gap: '4px',
                }}
              >
                {repos.map(
                  repo => (
                    <button
                      key={repo.id}
                      onClick={() =>
                        selectRepo(
                          repo
                        )
                      }
                      style={{
                        display:
                          'flex',
                        alignItems:
                          'center',
                        gap: '8px',
                        padding:
                          '8px 10px',
                        borderRadius:
                          '6px',
                        border:
                          'none',
                        cursor:
                          'pointer',
                        textAlign:
                          'left',
                        width:
                          '100%',
                        background:
                          selectedRepo?.id ===
                          repo.id
                            ? 'var(--primary-glow)'
                            : 'transparent',
                        color:
                          selectedRepo?.id ===
                          repo.id
                            ? 'var(--primary)'
                            : 'var(--text-muted)',
                        transition:
                          'all 0.15s',
                        fontSize:
                          '12px',
                        fontWeight:
                          '500',
                      }}
                      onMouseEnter={e => {
                        if (
                          selectedRepo?.id !==
                          repo.id
                        ) {
                          e.currentTarget.style.background =
                            'var(--bg-elevated)'
                        }
                      }}
                      onMouseLeave={e => {
                        if (
                          selectedRepo?.id !==
                          repo.id
                        ) {
                          e.currentTarget.style.background =
                            'transparent'
                        }
                      }}
                    >
                      <GitBranch
                        size={13}
                      />

                      <span
                        style={{
                          overflow:
                            'hidden',
                          textOverflow:
                            'ellipsis',
                          whiteSpace:
                            'nowrap',
                        }}
                      >
                        {repo.name}
                      </span>
                    </button>
                  )
                )}
              </div>
            )}
          </div>


          {/* Conversations */}
          <div
            style={{
              flex: 1,
              overflow: 'auto',
              padding: '12px',
            }}
          >
            <div
              style={{
                display:
                  'flex',
                alignItems:
                  'center',
                justifyContent:
                  'space-between',
                marginBottom:
                  '8px',
              }}
            >
              <div
                style={{
                  fontSize:
                    '10px',
                  color:
                    'var(--text-muted)',
                  textTransform:
                    'uppercase',
                  letterSpacing:
                    '0.05em',
                  fontWeight:
                    '600',
                }}
              >
                Conversations
              </div>

              <button
                onClick={
                  startNewChat
                }
                style={{
                  background:
                    'none',
                  border:
                    'none',
                  cursor:
                    'pointer',
                  color:
                    'var(--text-muted)',
                  padding:
                    '2px',
                  borderRadius:
                    '4px',
                  display:
                    'flex',
                  alignItems:
                    'center',
                }}
                onMouseEnter={e =>
                  e.currentTarget.style.color =
                    'var(--primary)'
                }
                onMouseLeave={e =>
                  e.currentTarget.style.color =
                    'var(--text-muted)'
                }
                title="New conversation"
              >
                <Plus size={13} />
              </button>
            </div>


            {conversations.length ===
            0 ? (
              <div
                style={{
                  fontSize:
                    '11px',
                  color:
                    'var(--text-muted)',
                  textAlign:
                    'center',
                  padding:
                    '16px 0',
                }}
              >
                No conversations yet
              </div>
            ) : (
              <div
                style={{
                  display:
                    'flex',
                  flexDirection:
                    'column',
                  gap: '2px',
                }}
              >
                {conversations.map(
                  conv => (
                    <button
                      key={conv.id}
                      onClick={() =>
                        selectConversation(
                          conv.id
                        )
                      }
                      style={{
                        display:
                          'flex',
                        alignItems:
                          'center',
                        gap: '8px',
                        padding:
                          '8px 10px',
                        borderRadius:
                          '6px',
                        border:
                          'none',
                        cursor:
                          'pointer',
                        textAlign:
                          'left',
                        width:
                          '100%',
                        background:
                          selectedConv ===
                          conv.id
                            ? 'var(--primary-glow)'
                            : 'transparent',
                        color:
                          selectedConv ===
                          conv.id
                            ? 'var(--primary)'
                            : 'var(--text-muted)',
                        transition:
                          'all 0.15s',
                        fontSize:
                          '12px',
                      }}
                      onMouseEnter={e => {
                        if (
                          selectedConv !==
                          conv.id
                        ) {
                          e.currentTarget.style.background =
                            'var(--bg-elevated)'
                        }
                      }}
                      onMouseLeave={e => {
                        if (
                          selectedConv !==
                          conv.id
                        ) {
                          e.currentTarget.style.background =
                            'transparent'
                        }
                      }}
                    >
                      <Clock
                        size={11}
                        style={{
                          flexShrink:
                            0,
                        }}
                      />

                      <span
                        style={{
                          overflow:
                            'hidden',
                          textOverflow:
                            'ellipsis',
                          whiteSpace:
                            'nowrap',
                          fontSize:
                            '11px',
                        }}
                      >
                        {conv.title ||
                          'Conversation'}
                      </span>
                    </button>
                  )
                )}
              </div>
            )}
          </div>
        </div>


        {/* ====================================================
            MAIN CHAT AREA
        ==================================================== */}

        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection:
              'column',
            overflow: 'hidden',
            minWidth: 0,
          }}
        >

          {/* No repository selected */}
          {!selectedRepo && (
            <div
              style={{
                flex: 1,
                display:
                  'flex',
                flexDirection:
                  'column',
                alignItems:
                  'center',
                justifyContent:
                  'center',
                color:
                  'var(--text-muted)',
              }}
            >
              <Bot
                size={48}
                style={{
                  marginBottom:
                    '16px',
                  opacity: 0.3,
                }}
              />

              <p
                style={{
                  fontSize:
                    '14px',
                }}
              >
                Select a repository
                to start chatting
              </p>
            </div>
          )}


          {/* Chat interface */}
          {selectedRepo && (
            <>
              {/* ==================================================
                  REPOSITORY INDICATOR
              ================================================== */}

              <div
                style={{
                  padding:
                    '10px 20px',
                  borderBottom:
                    '1px solid var(--border)',
                  display:
                    'flex',
                  alignItems:
                    'center',
                  gap: '8px',
                  background:
                    'var(--bg-surface)',
                }}
              >
                <div
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius:
                      '5px',
                    background:
                      'linear-gradient(135deg, #6366f1, #a855f7)',
                    display:
                      'flex',
                    alignItems:
                      'center',
                    justifyContent:
                      'center',
                  }}
                >
                  <GitBranch
                    size={11}
                    color="white"
                  />
                </div>

                <span
                  style={{
                    fontSize:
                      '12px',
                    fontWeight:
                      '600',
                  }}
                >
                  {
                    selectedRepo.name
                  }
                </span>

                <span
                  style={{
                    fontSize:
                      '11px',
                    color:
                      'var(--text-muted)',
                  }}
                >
                  ·{' '}
                  {
                    selectedRepo.total_files
                  }{' '}
                  files ·{' '}
                  {
                    selectedRepo.total_chunks
                  }{' '}
                  chunks
                </span>
              </div>


              {/* ==================================================
                  MESSAGES
              ================================================== */}

              <div
                style={{
                  flex: 1,
                  overflow: 'auto',
                  padding: '24px',
                  minWidth: 0,
                }}
              >

                {/* Welcome state */}
                {messages.length ===
                  0 &&
                  !loadingHistory && (
                    <div
                      className="animate-fade-in"
                      style={{
                        display:
                          'flex',
                        flexDirection:
                          'column',
                        alignItems:
                          'center',
                        justifyContent:
                          'center',
                        minHeight:
                          '60%',
                        textAlign:
                          'center',
                        padding:
                          '40px',
                      }}
                    >
                      <div
                        style={{
                          width:
                            '56px',
                          height:
                            '56px',
                          borderRadius:
                            '14px',
                          background:
                            'linear-gradient(135deg, #6366f1, #a855f7)',
                          display:
                            'flex',
                          alignItems:
                            'center',
                          justifyContent:
                            'center',
                          marginBottom:
                            '16px',
                          boxShadow:
                            '0 0 30px rgba(99,102,241,0.3)',
                        }}
                      >
                        <Zap
                          size={24}
                          color="white"
                        />
                      </div>

                      <h3
                        style={{
                          fontSize:
                            '16px',
                          fontWeight:
                            '700',
                          marginBottom:
                            '8px',
                        }}
                      >
                        Ask anything
                        about{' '}
                        <span
                          style={{
                            background:
                              'linear-gradient(135deg, #6366f1, #a855f7)',
                            WebkitBackgroundClip:
                              'text',
                            WebkitTextFillColor:
                              'transparent',
                          }}
                        >
                          {
                            selectedRepo.name
                          }
                        </span>
                      </h3>

                      <p
                        style={{
                          color:
                            'var(--text-muted)',
                          fontSize:
                            '13px',
                          marginBottom:
                            '24px',
                          maxWidth:
                            '400px',
                        }}
                      >
                        I have indexed{' '}
                        {
                          selectedRepo.total_chunks
                        }{' '}
                        code chunks.
                        Ask me about
                        architecture,
                        functions,
                        security, or
                        anything else.
                      </p>


                      {/* Suggested questions */}
                      <div
                        style={{
                          display:
                            'grid',
                          gridTemplateColumns:
                            '1fr 1fr',
                          gap: '8px',
                          maxWidth:
                            '520px',
                          width:
                            '100%',
                        }}
                      >
                        {SUGGESTED_QUESTIONS.map(
                          q => (
                            <button
                              key={q}
                              onClick={() =>
                                handleSend(
                                  q
                                )
                              }
                              style={{
                                padding:
                                  '10px 14px',
                                borderRadius:
                                  '8px',
                                border:
                                  '1px solid var(--border-bright)',
                                background:
                                  'var(--bg-surface)',
                                color:
                                  'var(--text)',
                                cursor:
                                  'pointer',
                                fontSize:
                                  '12px',
                                textAlign:
                                  'left',
                                transition:
                                  'all 0.15s',
                                lineHeight:
                                  '1.4',
                              }}
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
                                  'var(--bg-surface)'
                              }}
                            >
                              <MessageSquare
                                size={
                                  11
                                }
                                color="var(--primary)"
                                style={{
                                  marginBottom:
                                    '4px',
                                  display:
                                    'block',
                                }}
                              />

                              {q}
                            </button>
                          )
                        )}
                      </div>
                    </div>
                  )}


                {/* Loading history */}
                {loadingHistory && (
                  <div
                    style={{
                      display:
                        'flex',
                      justifyContent:
                        'center',
                      padding:
                        '40px',
                    }}
                  >
                    <Loader
                      size={20}
                      color="var(--primary)"
                      style={{
                        animation:
                          'spin 1s linear infinite',
                      }}
                    />
                  </div>
                )}


                {/* Messages */}
                {messages.map(
                  msg => (
                    <MessageBubble
                      key={msg.id}
                      message={msg}
                    />
                  )
                )}


                {/* Typing indicator */}
                {loading && (
                  <TypingIndicator />
                )}

                <div
                  ref={
                    messagesEndRef
                  }
                />
              </div>


              {/* ==================================================
                  INPUT AREA
              ================================================== */}

              <div
                style={{
                  padding:
                    '16px 20px',
                  borderTop:
                    '1px solid var(--border)',
                  background:
                    'var(--bg-surface)',
                }}
              >
                <div
                  style={{
                    display:
                      'flex',
                    gap: '10px',
                    alignItems:
                      'flex-end',
                    background:
                      'var(--bg-elevated)',
                    border:
                      '1px solid var(--border-bright)',
                    borderRadius:
                      '12px',
                    padding:
                      '10px 14px',
                    transition:
                      'border-color 0.2s',
                  }}
                >
                  <textarea
                    ref={
                      inputRef
                    }
                    value={input}
                    onChange={e =>
                      setInput(
                        e.target
                          .value
                      )
                    }
                    onKeyDown={
                      handleKeyDown
                    }
                    placeholder="Ask about the codebase... (Enter to send, Shift+Enter for new line)"
                    rows={1}
                    style={{
                      flex: 1,
                      background:
                        'none',
                      border:
                        'none',
                      color:
                        'var(--text)',
                      fontSize:
                        '13px',
                      outline:
                        'none',
                      resize:
                        'none',
                      fontFamily:
                        'Inter, sans-serif',
                      lineHeight:
                        '1.5',
                      maxHeight:
                        '120px',
                      overflowY:
                        'auto',
                    }}
                    onInput={e => {
                      const t =
                        e.target as HTMLTextAreaElement

                      t.style.height =
                        'auto'

                      t.style.height =
                        Math.min(
                          t.scrollHeight,
                          120
                        ) + 'px'
                    }}
                  />

                  <button
                    onClick={() =>
                      handleSend()
                    }
                    disabled={
                      !input.trim() ||
                      loading
                    }
                    style={{
                      width:
                        '32px',
                      height:
                        '32px',
                      borderRadius:
                        '8px',
                      border:
                        'none',
                      cursor:
                        input.trim() &&
                        !loading
                          ? 'pointer'
                          : 'not-allowed',
                      background:
                        input.trim() &&
                        !loading
                          ? 'linear-gradient(135deg, #6366f1, #7c3aed)'
                          : 'var(--border)',
                      display:
                        'flex',
                      alignItems:
                        'center',
                      justifyContent:
                        'center',
                      transition:
                        'all 0.2s',
                      flexShrink:
                        0,
                      boxShadow:
                        input.trim() &&
                        !loading
                          ? '0 0 12px rgba(99,102,241,0.4)'
                          : 'none',
                    }}
                  >
                    {loading ? (
                      <Loader
                        size={14}
                        color="white"
                        style={{
                          animation:
                            'spin 1s linear infinite',
                        }}
                      />
                    ) : (
                      <Send
                        size={14}
                        color="white"
                      />
                    )}
                  </button>
                </div>

                <div
                  style={{
                    fontSize:
                      '10px',
                    color:
                      'var(--text-muted)',
                    textAlign:
                      'center',
                    marginTop:
                      '8px',
                  }}
                >
                  Answers are grounded
                  in your codebase ·
                  Sources shown with
                  every response
                </div>
              </div>
            </>
          )}
        </div>
      </div>


      {/* ========================================================
          ANIMATIONS
      ======================================================== */}

      <style>{`
        @keyframes bounce {
          0%, 80%, 100% {
            transform: scale(0.8);
            opacity: 0.5;
          }

          40% {
            transform: scale(1.2);
            opacity: 1;
          }
        }

        @keyframes spin {
          from {
            transform: rotate(0deg);
          }

          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  )
}