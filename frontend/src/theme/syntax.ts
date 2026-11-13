import type { CSSProperties } from 'react'

// highlight.js categories remain distinct in every palette, including Arctic Light.
export const syntaxTheme: Record<string, CSSProperties> = {
  "hljs": {
    "display": "block",
    "overflowX": "auto",
    "padding": "0.5em",
    "color": "var(--text)",
    "background": "var(--bg-base)"
  },
  "hljs-comment": {
    "color": "var(--syntax-comment)",
    "fontStyle": "italic"
  },
  "hljs-quote": {
    "color": "var(--syntax-comment)",
    "fontStyle": "italic"
  },
  "hljs-doctag": {
    "color": "var(--syntax-keyword)"
  },
  "hljs-keyword": {
    "color": "var(--syntax-keyword)"
  },
  "hljs-formula": {
    "color": "var(--syntax-keyword)"
  },
  "hljs-section": {
    "color": "var(--syntax-tag)"
  },
  "hljs-name": {
    "color": "var(--syntax-tag)"
  },
  "hljs-selector-tag": {
    "color": "var(--syntax-tag)"
  },
  "hljs-deletion": {
    "color": "var(--syntax-tag)"
  },
  "hljs-subst": {
    "color": "var(--syntax-tag)"
  },
  "hljs-literal": {
    "color": "var(--syntax-literal)"
  },
  "hljs-string": {
    "color": "var(--syntax-string)"
  },
  "hljs-regexp": {
    "color": "var(--syntax-string)"
  },
  "hljs-addition": {
    "color": "var(--syntax-string)"
  },
  "hljs-attribute": {
    "color": "var(--syntax-string)"
  },
  "hljs-meta-string": {
    "color": "var(--syntax-string)"
  },
  "hljs-built_in": {
    "color": "var(--syntax-number)"
  },
  "hljs-class .hljs-title": {
    "color": "var(--syntax-number)"
  },
  "hljs-attr": {
    "color": "var(--syntax-number)"
  },
  "hljs-variable": {
    "color": "var(--syntax-number)"
  },
  "hljs-template-variable": {
    "color": "var(--syntax-number)"
  },
  "hljs-type": {
    "color": "var(--syntax-number)"
  },
  "hljs-selector-class": {
    "color": "var(--syntax-number)"
  },
  "hljs-selector-attr": {
    "color": "var(--syntax-number)"
  },
  "hljs-selector-pseudo": {
    "color": "var(--syntax-number)"
  },
  "hljs-number": {
    "color": "var(--syntax-number)"
  },
  "hljs-symbol": {
    "color": "var(--syntax-function)"
  },
  "hljs-bullet": {
    "color": "var(--syntax-function)"
  },
  "hljs-link": {
    "color": "var(--syntax-function)",
    "textDecoration": "underline"
  },
  "hljs-meta": {
    "color": "var(--syntax-function)"
  },
  "hljs-selector-id": {
    "color": "var(--syntax-function)"
  },
  "hljs-title": {
    "color": "var(--syntax-function)"
  },
  "hljs-emphasis": {
    "fontStyle": "italic"
  },
  "hljs-strong": {
    "fontWeight": "bold"
  }
};