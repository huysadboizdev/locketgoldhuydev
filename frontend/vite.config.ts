import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
        configure: (proxy) => {
          let isBackendOffline = false;

          proxy.on('error', (_err, _req, res) => {
            if (!isBackendOffline) {
              isBackendOffline = true;
              console.warn(
                '[vite:proxy] Backend development server is unavailable at 127.0.0.1:5001. Subsequent connection errors suppressed until restored.'
              );
            }
            if ('writeHead' in res && !res.headersSent) {
              res.writeHead(503, { 'Content-Type': 'application/json' });
              res.end(
                JSON.stringify({
                  success: false,
                  offline: true,
                  msg: 'Backend development server is unavailable',
                })
              );
            }
          });

          proxy.on('proxyRes', () => {
            if (isBackendOffline) {
              isBackendOffline = false;
              console.info('[vite:proxy] Backend connection restored at 127.0.0.1:5001');
            }
          });
        },
      },
    },
  },
});
