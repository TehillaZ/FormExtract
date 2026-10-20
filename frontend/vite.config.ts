import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The API has no /api prefix; the dev server strips it, so the browser never needs CORS.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': { target: process.env.API_PROXY_TARGET ?? 'http://localhost:8000', rewrite: (path) => path.replace(/^\/api/, '') },
    },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],   // e2e/ belongs to Playwright
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    restoreMocks: true,
  },
})
