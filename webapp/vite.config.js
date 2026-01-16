import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    open: false, // 禁用自动打开浏览器
    watch: {
      // 忽略运行时生成的文件，避免触发热重载
      ignored: [
        '**/*.db',
        '**/*.db-*',
        '**/config.json',
        '**/src-tauri/config/**',
        '**/src-tauri/target/**',
        '**/.cargo/**',
        '**/data-pipeline/**',
        '**/output/**',
        '**/logs/**',
        '**/.DS_Store',
        '**/node_modules/**'
      ]
    }
  },
  build: {
    outDir: 'dist'
  },
  // 彻底禁用文件监视优化
  optimizeDeps: {
    exclude: []
  }
})

