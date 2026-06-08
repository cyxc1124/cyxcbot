import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const buildVersion =
  process.env.GIT_TAG ||
  process.env.GIT_COMMIT ||
  process.env.BUILD_VERSION ||
  'dev'

export default defineConfig({
  plugins: [react()],
  define: {
    'import.meta.env.VITE_BUILD_VERSION': JSON.stringify(buildVersion),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8081',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
