import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    allowedHosts: ['mscli.dev'],
    proxy: { '/api': 'http://127.0.0.1:8000', '/health': 'http://127.0.0.1:8000' },
  },
})
