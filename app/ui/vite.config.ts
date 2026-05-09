import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiTarget = process.env.VITE_API_BASE_URL || 'http://127.0.0.1:43174';

export default defineConfig({
  base: process.env.NODE_ENV === 'production' ? '/AlephTav/' : '/',
  root: 'app/ui',
  plugins: [react()],
  server: {
    port: 43173,
    strictPort: true,
    proxy: {
      '/project': apiTarget,
      '/assistant': apiTarget,
      '/psalms': apiTarget,
      '/speech': apiTarget,
      '/units': apiTarget,
      '/tokens': apiTarget,
      '/lexicon': apiTarget,
      '/search': apiTarget,
      '/alignments': apiTarget,
      '/renderings': apiTarget,
      '/review': apiTarget,
      '/audit': apiTarget,
      '/state': apiTarget,
      '/reports': apiTarget,
      '/export': apiTarget,
      '/jobs': apiTarget
    }
  },
  build: {
    outDir: '../../dist/ui',
    emptyOutDir: true
  }
});
