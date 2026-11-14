import { Code2, Folder, FileCode2, ChevronRight, ShieldCheck, Sparkles, TriangleAlert, MessageSquare, Layers, LockKeyhole } from 'lucide-react'

export function LandingStory() {
  return <section className="landing-story" aria-label="About CodeLens AI">
    <div className="landing-eyebrow"><span /> YOUR CODE. A CLEARER PICTURE.</div>
    <h1>Clarity starts with<br />your <em>code.</em></h1>
    <p className="landing-intro">A private workspace to explore repositories, understand your code, and ask better questions.</p>
    <div className="landing-bento">
      <article className="landing-tile explorer-tile">
        <div className="tile-heading"><span className="tile-icon"><Folder size={24} aria-hidden="true" /></span><h2>Explore your repository</h2></div>
        <p>Browse files, understand structure, and get context across your codebase.</p>
        <div className="landing-file-tree" aria-label="Illustrative repository file tree">
          <div className="tree-title"><Code2 size={16} aria-hidden="true" /> example-app <span>Demo preview</span></div>
          <div><ChevronRight size={14} className="tree-open" /><Folder size={16} /> src</div>
          <div className="tree-child tree-selected"><FileCode2 size={16} /><span>app.ts</span></div>
          <div className="tree-child"><FileCode2 size={16} /><span>routes.ts</span></div>
          <div className="tree-child"><FileCode2 size={16} /><span>utils.py</span></div>
          <div><ChevronRight size={14} /><Folder size={16} /> tests</div>
          <div><ChevronRight size={14} /><Folder size={16} /> notebooks</div>
          <div><FileCode2 size={16} /> package.json</div>
          <div><FileCode2 size={16} /> README.md</div>
        </div>
      </article>
      <article className="landing-tile health-tile">
        <div className="tile-heading"><span className="tile-icon"><ShieldCheck size={24} aria-hidden="true" /></span><h2>Health that makes sense</h2></div>
        <p>Focus on risk findings, with style suggestions kept separate from your health score.</p>
        <div className="landing-findings"><span><TriangleAlert size={17} />Risk findings</span><span><Sparkles size={17} />Style suggestions</span></div>
      </article>
      <article className="landing-tile chat-tile">
        <div className="tile-heading"><span className="tile-icon"><MessageSquare size={24} aria-hidden="true" /></span><h2>Ask your code</h2></div>
        <p>Chat with AI using your repository as context. Find explanations grounded in your code.</p>
        <div className="landing-question"><MessageSquare size={18} aria-hidden="true" /><span>How does authentication work in this repository?<small>Example question</small></span></div>
      </article>
    </div>
  </section>
}

const capabilities = [
  { icon: Code2, title: 'Repository exploration', copy: 'Navigate files, search symbols, and understand your codebase with context.' },
  { icon: MessageSquare, title: 'AI chat with context', copy: 'Ask questions, explore explanations, and return to saved conversations.' },
  { icon: ShieldCheck, title: 'Separate insights', copy: 'Meaningful health findings and practical style suggestions, clearly distinguished.' },
  { icon: Layers, title: 'Broad file support', copy: 'Python, JavaScript, TypeScript, Java, Go, C++, JSON, and notebooks.' },
  { icon: LockKeyhole, title: 'Private workspace', copy: 'Your repositories, chats, and analysis stay connected to your own account.' },
]

export function LandingCapabilities() {
  return <section className="landing-capabilities" id="capabilities" aria-labelledby="capabilities-heading">
    <h2 id="capabilities-heading">A clearer view. From the first file.</h2>
    <p>Everything you need to get familiar with a codebase, in one place.</p>
    <div className="capability-grid">{capabilities.map(({ icon: Icon, title, copy }) =>
      <article key={title}><Icon size={24} aria-hidden="true" /><h3>{title}</h3><p>{copy}</p></article>
    )}</div>
  </section>
}
