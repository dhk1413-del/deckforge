import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const rootDir = path.dirname(fileURLToPath(import.meta.url))
// 上层是仓库根（ui-design/ 的令牌 CSS 在 web/ 之外，需要放开 fs 白名单）
const repoRoot = path.resolve(rootDir, '..')

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5183,
    strictPort: true,
    // 显式绑 IPv4：macOS 上 Vite 默认只监听 ::1，curl 127.0.0.1 会连不上
    host: '127.0.0.1',
    // 允许读取仓库根下的 ui-design/*.css
    fs: { allow: [rootDir, repoRoot] },
    proxy: {
      '/api': 'http://127.0.0.1:8640',
      '/files': 'http://127.0.0.1:8640',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
