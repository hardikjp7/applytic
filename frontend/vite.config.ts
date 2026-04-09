import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // Base path for GitHub Pages — /applytic/ matches the repo name
  base: process.env.VITE_BASE_PATH ?? '/',
  plugins: [react()],
  resolve: {
    alias: { '@': '/src' },
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          aws: ['aws-amplify', '@aws-amplify/ui-react'],
          charts: ['recharts'],
        },
      },
    },
  },
})
