import { defineConfig } from 'vitest/config'

export default defineConfig({
  // Tests never load project dotenv files or contact a real Supabase project.
  envDir: false,
  test: { environment: 'jsdom', include: ['tests/**/*.test.{ts,tsx}'], clearMocks: true },
})
