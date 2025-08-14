import { defineConfig } from 'vite';
import legacy from '@vitejs/plugin-legacy';

export default defineConfig({
  root: 'static',
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: 'static/index.html'
      }
    },
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true
      }
    }
  },
  plugins: [
    legacy({
      targets: ['defaults', 'not IE 11']
    })
  ],
  server: {
    port: 8080,
    host: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/ws': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true
      }
    }
  },
  define: {
    __API_URL__: JSON.stringify(process.env.VITE_API_URL || 'http://localhost:8000')
  }
});
