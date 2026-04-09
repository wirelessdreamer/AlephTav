import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: 'app/ui',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/project': 'http://127.0.0.1:8000',
      '/psalms': 'http://127.0.0.1:8000',
      '/units': 'http://127.0.0.1:8000',
      '/tokens': 'http://127.0.0.1:8000',
      '/lexicon': 'http://127.0.0.1:8000',
      '/search': 'http://127.0.0.1:8000',
      '/alignments': 'http://127.0.0.1:8000',
      '/renderings': 'http://127.0.0.1:8000',
      '/review': 'http://127.0.0.1:8000',
      '/audit': 'http://127.0.0.1:8000',
      '/reports': 'http://127.0.0.1:8000',
      '/export': 'http://127.0.0.1:8000',
      '/jobs': 'http://127.0.0.1:8000'
    }
  },
  build: {
    outDir: '../../dist/ui',
    emptyOutDir: true
  }
});
