import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['packages/*/src/**/*.test.ts'],
    environment: 'node',
  },
  resolve: {
    alias: {
      '@opencareer/core': new URL('./packages/core/src/index.ts', import.meta.url).pathname,
    },
  },
})
