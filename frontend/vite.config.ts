import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

const apiProxyTarget = process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000'

// The Vite dev server is the only thing the tunnel points at; it forwards /api (incl. the sync
// WebSocket) to the loopback-bound backend. The backend decides who is "local" from the original
// Host, so we stamp it on every proxied request (overwriting anything a remote client sent).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function stampOriginalHost(proxy: any) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const stamp = (proxyReq: any, req: any) => {
    proxyReq.setHeader('x-forwarded-host', req.headers.host ?? '')
  }
  proxy.on('proxyReq', stamp)
  proxy.on('proxyReqWs', stamp)
}

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    // Listen on loopback only: cloudflared connects locally, nothing else on your network can.
    // (Docker sets VITE_HOST=0.0.0.0 and publishes the port on the host's loopback only.)
    host: process.env.VITE_HOST ?? '127.0.0.1',
    port: Number(process.env.FRONTEND_PORT ?? 5173),
    strictPort: true,
    allowedHosts: ['.trycloudflare.com', 'localhost', '.localhost', '127.0.0.1'],
    headers: {
      'Cache-Control': 'no-store',
    },
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
        ws: true,
        configure: stampOriginalHost,
      },
    },
  },
})
