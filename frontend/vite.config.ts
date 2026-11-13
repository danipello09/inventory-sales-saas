import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  // These variables configure Vite's server and are not exposed via VITE_*.
  const env = loadEnv(mode, '.', 'DEV_')
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api/': {
          target: env.DEV_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        },
      },
      watch: {
        usePolling: env.DEV_USE_POLLING === 'true',
        interval: 300,
      },
    },
    test: {
      environment: 'node',
      include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    },
  }
})
