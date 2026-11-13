import { Check, Palette } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useTheme } from './ThemeProvider'
import { themes } from './preferences'
import './appearance.css'

export default function Appearance() {
  const { theme, selectTheme, saving, message } = useTheme()
  const { hash } = useLocation()
  const section = useRef<HTMLElement>(null)
  useEffect(() => {
    if (hash === '#appearance') section.current?.scrollIntoView?.({ block: 'start' })
  }, [hash])
  return <section ref={section} id="appearance" className="card appearance" aria-labelledby="appearance-title">
    <h2 id="appearance-title"><Palette size={19} aria-hidden="true" />Appearance</h2>
    <p>Make this workspace yours. Choose a theme to preview it instantly.</p>
    <div className="theme-options" role="group" aria-label="Application theme">
      {themes.map(option => <button key={option.id} type="button" className="theme-option" aria-pressed={theme === option.id}
        onClick={() => selectTheme(option.id)} aria-label={option.name}>
        <span className="theme-preview" data-theme={option.id} aria-hidden="true">
          <span className="theme-preview-sidebar"><i /><i /><i /><i /></span>
          <span className="theme-preview-main"><span className="theme-preview-heading" /><span className="theme-preview-cards"><i /><i /><i /></span><span className="theme-preview-code"><i /><i /><i /></span></span>
        </span>
        <span className="theme-option-label"><strong>{option.name}</strong>{theme === option.id && <Check size={17} aria-hidden="true" />}</span>
        <span className="theme-description">{option.description}</span>
        <span className="theme-state">{theme === option.id ? 'Selected' : option.id === 'midnight-violet' ? 'Default theme' : 'Select theme'}</span>
      </button>)}
    </div>
    <p className="theme-save-status" role="status">{saving ? 'Saving your preference…' : message || 'Midnight Violet is the default. Your choice follows your account.'}</p>
  </section>
}
