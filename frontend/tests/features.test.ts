import { afterEach, expect, it, vi } from 'vitest'
afterEach(() => { vi.unstubAllEnvs(); vi.resetModules() })
it.each([undefined, '', 'false', 'true'])('email auth requires explicit opt-in: %s', async value => {
  vi.stubEnv('VITE_ENABLE_EMAIL_AUTH', value)
  vi.resetModules()
  const { emailAuthEnabled } = await import('../src/auth/features')
  expect(emailAuthEnabled).toBe(value === 'true')
})
