import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const __uiRoot = path.dirname(new URL(import.meta.url).pathname).replace(/^\/([A-Z]:)/, '$1')

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Restrict dependency scanning to this UI directory only
  optimizeDeps: {
    entries: ['index.html', 'src/**/*.{js,jsx}'],
  },
  server: {
    port: 3000,
    open: true,
    fs: {
      // Only allow serving files from the UI directory
      strict: true,
      allow: [__uiRoot],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8001',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          mui: ['@mui/material', '@mui/icons-material'],
          reactflow: ['reactflow'],
        },
      },
    },
  },
})
