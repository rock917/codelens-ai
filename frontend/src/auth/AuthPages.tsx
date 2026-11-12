import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { GitBranch, Zap, ArrowUpRight, ScanLine, MessageSquare, LockKeyhole, FileCode2 } from 'lucide-react'
import { supabase } from './client'
import { useAuth } from './AuthProvider'
import { emailAuthEnabled } from './features'
import './auth.css'

export function AuthFrame({ children, showcase = false }: { children: ReactNode, showcase?: boolean }) {
  return <main className={`auth-page ${showcase ? 'auth-landing' : ''}`}>
    {showcase && <header className="landing-header"><a href="/login" className="landing-logo"><span><Zap size={20} aria-hidden="true" /></span>CodeLens <b>AI</b></a><a href="/about.html">Explore the platform <ArrowUpRight size={15} aria-hidden="true" /></a></header>}
    <div className={showcase ? 'landing-layout' : 'auth-compact'}>
    {showcase && <section className="landing-story" aria-label="About CodeLens AI">
      <div className="landing-eyebrow"><span /> YOUR CODE. A CLEARER PICTURE.</div>
      <h1>Understand more.<br /><em>Build with confidence.</em></h1>
      <p className="landing-intro">Turn a repository into a workspace you can explore, question, and improve. Get from unfamiliar code to your next clear step.</p>
      <div className="code-preview" aria-label="Illustrative code exploration preview">
        <div className="preview-top"><span className="preview-dots"><i /><i /><i /></span><span>workspace / explore</span><span className="preview-label">PREVIEW</span></div>
        <div className="preview-body"><div className="preview-tree"><span><GitBranchIcon /> repository</span><span className="preview-file active"><FileCode2 size={13} /> app.py</span><span className="preview-file"><FileCode2 size={13} /> search.py</span><span className="preview-file"><FileCode2 size={13} /> tests.py</span></div>
          <div className="preview-code"><span className="code-comment"># Find the part that matters</span><pre><span>def</span> explore(repository):{'\n'}  context = index(repository){'\n'}  insights = analyze(context){'\n'}  <span>return</span> your_next_step</pre><div className="preview-insight"><ScanLine size={16} /><div>From code to context<small>Explore symbols. Follow connections.</small></div></div></div>
        </div>
      </div>
      <div className="landing-features"><div><ScanLine size={18} /><span>Find issues<small>Security & code quality</small></span></div><div><MessageSquare size={18} /><span>Ask your code<small>Answers with context</small></span></div><div><LockKeyhole size={18} /><span>Your workspace<small>Saved to your account</small></span></div></div>
    </section>}
    <section className="auth-card" aria-label="Account access">
    {!showcase && <div className="auth-brand"><Zap aria-hidden="true" /> CodeLens AI</div>}{children}
    <nav aria-label="Public information" className="auth-footer">
      <a href="/about.html">About</a><a href="/privacy.html">Privacy</a><a href="/terms.html">Terms</a>
    </nav>
  </section></div>
  {showcase && <footer className="landing-bottom"><span>A little clarity goes a long way.</span><span>CodeLens AI · Repository intelligence</span></footer>}
  </main>
}

function GitBranchIcon() { return <GitBranch size={14} aria-hidden="true" /> }

function GithubIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .8a11.2 11.2 0 0 0-3.54 21.83c.56.1.77-.24.77-.54v-2.08c-3.13.68-3.79-1.33-3.79-1.33-.51-1.3-1.25-1.65-1.25-1.65-1.02-.7.08-.68.08-.68 1.13.08 1.73 1.16 1.73 1.16 1 1.72 2.63 1.22 3.27.93.1-.73.39-1.22.71-1.5-2.5-.28-5.13-1.25-5.13-5.57 0-1.23.44-2.23 1.16-3.02-.12-.28-.5-1.43.11-2.98 0 0 .95-.3 3.08 1.15a10.7 10.7 0 0 1 5.6 0c2.13-1.45 3.07-1.15 3.07-1.15.62 1.55.23 2.7.12 2.98.72.79 1.15 1.79 1.15 3.02 0 4.33-2.64 5.29-5.15 5.57.4.35.76 1.03.76 2.08v3.07c0 .3.2.65.77.54A11.2 11.2 0 0 0 12 .8Z" /></svg>
}

function GoogleIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285f4" d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.88h5.38a4.6 4.6 0 0 1-2 3.02v2.51h3.24c1.9-1.75 2.98-4.32 2.98-7.36Z" /><path fill="#34a853" d="M12 22c2.7 0 4.96-.9 6.62-2.42l-3.24-2.51c-.9.6-2.04.97-3.38.97-2.6 0-4.81-1.76-5.6-4.12H3.06v2.59A10 10 0 0 0 12 22Z" /><path fill="#fbbc05" d="M6.4 13.92a6 6 0 0 1 0-3.84V7.49H3.06a10 10 0 0 0 0 9.02Z" /><path fill="#ea4335" d="M12 5.96c1.47 0 2.79.5 3.83 1.5L18.7 4.6A9.6 9.6 0 0 0 12 2a10 10 0 0 0-8.94 5.49l3.34 2.59A5.99 5.99 0 0 1 12 5.96Z" /></svg>
}

export function Login() {
  const { session, loading } = useAuth()
  const [mode, setMode] = useState<'login' | 'signup' | 'reset'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  if (loading) return <AuthFrame><p role="status">Loading your account...</p></AuthFrame>
  if (session) return <Navigate to="/" replace />
  const callback = `${window.location.origin}/auth/callback`
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!emailAuthEnabled || !supabase || busy) return
    setBusy(true); setError(''); setNotice('')
    try {
      if (mode === 'reset') {
        const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${callback}?next=reset` })
        if (error) throw error
        setNotice('If an account exists for this email, you will receive a password reset link. Open it in this browser.')
      } else if (mode === 'signup') {
        const { error } = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: callback } })
        if (error) throw error
        setNotice('Check your email for a confirmation link. Open it in this browser to finish creating your account.')
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
      }
    } catch (err) { setError(err instanceof Error ? err.message : 'Sign-in failed. Please try again.') }
    finally { setBusy(false) }
  }
  async function oauth(provider: 'google' | 'github') {
    if (!supabase || busy) return
    setBusy(true); setError('')
    try {
      const { error } = await supabase.auth.signInWithOAuth({ provider, options: { redirectTo: callback } })
      if (error) throw error
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to sign in.'); setBusy(false) }
  }
  function changeMode(next: typeof mode) { setMode(next); setPassword(''); setError(''); setNotice('') }
  return <AuthFrame showcase>
    <div className="auth-card-eyebrow">YOUR NEXT CHAPTER STARTS HERE</div>
    <h2>{mode === 'signup' ? 'Create your account' : mode === 'reset' ? 'Reset your password' : 'Welcome to CodeLens'}</h2>
    <p className="auth-subtitle">Your repositories, insights, and conversations in one private workspace.</p>
    {!supabase && <p role="alert">Sign-in is temporarily unavailable. Please try again later.</p>}
    <form onSubmit={submit}>
      <fieldset disabled={busy || !supabase}>
        {mode !== 'reset' && <><div className="auth-social">
          <button type="button" onClick={() => void oauth('google')}><GoogleIcon />Continue with Google</button>
          <button type="button" onClick={() => void oauth('github')}><GithubIcon /> Continue with GitHub</button>
        </div>{emailAuthEnabled && <div className="auth-divider">or use your email</div>}</>}
        {emailAuthEnabled && <>
        <label htmlFor="email">Email address</label>
        <input id="email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={e => setEmail(e.target.value)} />
        {mode !== 'reset' && <><label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required minLength={mode === 'signup' ? 12 : 1} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} />
          {mode === 'signup' && <small>Use at least 12 characters.</small>}
        </>}
        <button className="auth-primary" type="submit">{busy ? 'Please wait...' : mode === 'signup' ? 'Create account' : mode === 'reset' ? 'Send reset link' : 'Sign in'}</button>
        </>}
      </fieldset>
    </form>
    {error && <p className="auth-error" role="alert">{error}</p>}
    {notice && <p className="auth-notice" role="status">{notice}</p>}
    {emailAuthEnabled && <div className="auth-links">
      <button disabled={busy} onClick={() => changeMode(mode === 'login' ? 'signup' : 'login')}>{mode === 'login' ? 'New here? Create an account' : 'Back to sign in'}</button>
      {mode === 'login' && <button disabled={busy} onClick={() => changeMode('reset')}>Forgot password?</button>}
    </div>}
  </AuthFrame>
}

export function AuthCallback() {
  const navigate = useNavigate()
  const [error, setError] = useState(supabase ? '' : 'Sign-in is temporarily unavailable.')
  useEffect(() => {
    let active = true
    const target = emailAuthEnabled && new URLSearchParams(window.location.search).get('next') === 'reset' ? '/reset-password' : '/'
    if (!supabase) return
    // The SDK exchanges the PKCE code exactly once during initialization.
    void supabase.auth.getSession().then(({ data, error }) => {
      if (!active) return
      if (error || !data.session) setError('This sign-in link is invalid or expired. Request a new link and open it in the same browser.')
      else navigate(target, { replace: true })
    }).catch(() => { if (active) setError('Unable to complete sign-in. Please try again.') })
    return () => { active = false }
  }, [navigate])
  return <AuthFrame><h1>Completing sign-in</h1>{error ? <><p role="alert">{error}</p><Link to="/login">Return to sign in</Link></> : <p role="status">Please wait...</p>}</AuthFrame>
}

export function ResetPassword() {
  const { session, loading } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!emailAuthEnabled || !supabase || busy) return
    setBusy(true); setError('')
    try {
      const { error } = await supabase.auth.updateUser({ password })
      if (error) throw error
      navigate('/', { replace: true })
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to update password.') }
    finally { setBusy(false) }
  }
  if (!emailAuthEnabled) return <Navigate to="/login" replace />
  if (loading) return <AuthFrame><p role="status">Loading...</p></AuthFrame>
  if (!session) return <Navigate to="/login" replace />
  return <AuthFrame><h1>Choose a new password</h1><form onSubmit={submit}>
    <label htmlFor="new-password">New password</label>
    <input id="new-password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} />
    <small>Use at least 12 characters.</small>
    <button className="auth-primary" disabled={busy}>{busy ? 'Saving...' : 'Save password'}</button>
  </form>{error && <p role="alert">{error}</p>}</AuthFrame>
}
