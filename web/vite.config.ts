import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const gitTag = process.env.GIT_TAG?.trim() || ''
const gitBranch = process.env.GIT_BRANCH?.trim() || ''
const gitCommit = process.env.GIT_COMMIT?.trim() || ''
const shortCommit = gitCommit ? gitCommit.slice(0, 8) : ''
const buildVersion =
  gitTag ||
  (gitBranch && shortCommit
    ? `${gitBranch}@${shortCommit}`
    : gitBranch || shortCommit || process.env.BUILD_VERSION?.trim() || 'dev')

export default defineConfig({
  plugins: [react()],
  define: {
    'import.meta.env.VITE_BUILD_VERSION': JSON.stringify(buildVersion),
    'import.meta.env.VITE_GIT_BRANCH': JSON.stringify(gitBranch || null),
    'import.meta.env.VITE_BUILD_TIME': JSON.stringify(
      process.env.BUILD_TIME?.trim() || null,
    ),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8081',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
