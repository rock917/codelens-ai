import ReactMarkdown from 'react-markdown'
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter'
import python from 'react-syntax-highlighter/dist/esm/languages/hljs/python'
import json from 'react-syntax-highlighter/dist/esm/languages/hljs/json'
import { syntaxTheme } from '../theme/syntax'

SyntaxHighlighter.registerLanguage('python', python)
SyntaxHighlighter.registerLanguage('json', json)

export interface DocumentData {
  content: string
  valid: boolean
  searchable: boolean
  kernel: string | null
  analysis_label: string
  warnings: string[]
  cells: { number: number; cell_type: string; source: string; start_line: number; end_line: number; header_line: number; analysis_supported: boolean; reason: string | null }[]
  sections: { name: string; start_line: number; end_line: number }[]
}

export default function DocumentView({ document, language, highlightLine }: { document: DocumentData; language: string; highlightLine: number | null }) {
  const code = (content: string, lang: string, start = 1) => <SyntaxHighlighter
    language={lang} style={syntaxTheme} showLineNumbers startingLineNumber={start} wrapLines
    lineProps={(line: number) => ({ id: `line-${line}`, style: { display: 'block', background: line === highlightLine ? 'var(--primary-glow)' : 'transparent' } })}
    customStyle={{ margin: 0, background: 'var(--bg-base)', fontSize: 12, lineHeight: 1.6 }}
  >{content || ' '}</SyntaxHighlighter>
  return <div style={{ padding: 20 }}>
    <div role="status" style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 16, lineHeight: 1.7 }}>
      <strong style={{ color: document.valid ? 'var(--success)' : 'var(--warning)' }}>{!document.valid ? 'Not indexed: validation failed' : document.searchable ? 'Indexed and searchable' : 'Valid document; no searchable content'}</strong>
      <div>{document.analysis_label}</div>
      <div>{language === 'notebook' ? `Kernel: ${document.kernel || 'unknown'}. Outputs and attachments are omitted. Code is never executed.` : 'Paths use JSON Pointer notation. Line numbers refer to this formatted view.'}</div>
      {language === 'notebook' && <div>Line numbers refer to the source-only notebook view; cell numbers match the original notebook.</div>}
    </div>
    {document.warnings.length > 0 && <details style={{ color: 'var(--warning)', marginBottom: 16 }} open={!document.valid}>
      <summary>{document.warnings.length} validation or coverage notice(s)</summary>
      <ul>{document.warnings.map((warning, i) => <li key={i} style={{ fontSize: 12, marginTop: 6 }}>{warning}</li>)}</ul>
    </details>}
    {document.valid && language === 'json' && code(document.content, 'json')}
    {document.valid && language === 'notebook' && document.cells.map(cell => <section key={cell.number} className="card" style={{ marginBottom: 16, overflow: 'hidden' }}>
      <h3 id={`line-${cell.header_line}`} style={{ padding: '10px 14px', fontSize: 13, borderBottom: '1px solid var(--border)' }}>Cell {cell.number} · {cell.cell_type}
        {cell.cell_type === 'code' && <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}> · {cell.analysis_supported ? 'Health analysis supported' : 'Not health-scanned'}</span>}
      </h3>
      {cell.cell_type === 'markdown' ? <div style={{ padding: 16, fontSize: 13, overflowWrap: 'anywhere' }}>
        <ReactMarkdown skipHtml components={{ img: () => null, a: ({ children }) => <span>{children}</span> }}>{cell.source}</ReactMarkdown>
        <details open={highlightLine !== null && highlightLine >= cell.start_line && highlightLine <= cell.end_line ? true : undefined} style={{ marginTop: 12 }}><summary>Markdown source · lines {cell.start_line}–{cell.end_line}</summary>{code(cell.source, 'text', cell.start_line)}</details>
      </div> : code(cell.source, cell.analysis_supported ? 'python' : 'text', cell.start_line)}
    </section>)}
    {document.valid && language === 'notebook' && document.cells.length === 0 && <p>This notebook has no cells.</p>}
  </div>
}
