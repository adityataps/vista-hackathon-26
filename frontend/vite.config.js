import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev proxy: forwards /api/* to the local FastAPI backend (port 8080, as per
// implementation plan). In production the ALB routes /api/* to the backend
// target group, so the built frontend never needs to know the backend host.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
});
