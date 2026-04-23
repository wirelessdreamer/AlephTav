import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: process.env.NODE_ENV === 'production' ? '/AlephTav/' : '/',
  root: 'app/ui',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/project': 'http://127.0.0.1:8765',
      '/assistant': 'http://127.0.0.1:8765',
      '/psalms': 'http://127.0.0.1:8765',
      '/speech': 'http://127.0.0.1:8765',
      '/units': 'http://127.0.0.1:8765',
      '/tokens': 'http://127.0.0.1:8765',
      '/lexicon': 'http://127.0.0.1:8765',
      '/search': 'http://127.0.0.1:8765',
      '/alignments': 'http://127.0.0.1:8765',
      '/renderings': 'http://127.0.0.1:8765',
      '/review': 'http://127.0.0.1:8765',
      '/audit': 'http://127.0.0.1:8765',
      '/state': 'http://127.0.0.1:8765',
      '/reports': 'http://127.0.0.1:8765',
      '/export': 'http://127.0.0.1:8765',
      '/jobs': 'http://127.0.0.1:8765'
    }
  },
  build: {
    outDir: '../../dist/ui',
    emptyOutDir: true
  }
});
