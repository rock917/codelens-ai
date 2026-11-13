import { readFileSync } from 'node:fs'
import { expect, it } from 'vitest'

const css = readFileSync('src/theme/tokens.css', 'utf8')
function luminance(hex: string) {
  const rgb = [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16) / 255)
    .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
  return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722
}
function contrast(a: string, b: string) {
  const values = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (values[0] + .05) / (values[1] + .05)
}
for (const theme of ['midnight-violet', 'cyber-cyan', 'emerald-matrix', 'arctic-light']) {
  it(`${theme} has readable text, syntax colors and filled buttons`, () => {
    const block = css.match(new RegExp(`\\[data-theme="${theme}"\\] \\{([^}]+)`))![1]
    const tokens = Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[\da-f]{6})/g)].map(match => [match[1], match[2]]))
    for (const foreground of ['text', 'text-muted', 'text-dim', 'primary', 'accent', 'success', 'warning', 'danger', 'syntax-keyword', 'syntax-string', 'syntax-number', 'syntax-function', 'syntax-tag', 'syntax-literal']) {
      for (const background of ['bg-base', 'bg-surface', 'bg-elevated']) {
        expect(contrast(tokens[foreground], tokens[background]), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5)
      }
    }
    for (const background of ['primary-strong', 'accent-strong']) expect(contrast(tokens['on-primary'], tokens[background])).toBeGreaterThanOrEqual(4.5)
    expect(contrast(tokens['on-danger'], tokens['danger-strong'])).toBeGreaterThanOrEqual(4.5)
    expect(contrast(tokens['on-soft'], tokens['soft-action'])).toBeGreaterThanOrEqual(4.5)
  })
}
