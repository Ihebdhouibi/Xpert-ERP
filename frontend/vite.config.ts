import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import fs from 'fs'
import path from 'path'
import type { Plugin } from 'vite'

// ── Dev-only plugin: mirrors Vite output to logs/vite.log ─────────────────
function viteFileLogger(): Plugin {
  const logDir = path.resolve(__dirname, '../logs')
  const logFile = path.join(logDir, 'vite.log')

  function write(level: string, msg: string) {
    const ts = new Date().toISOString().replace('T', ' ').replace('Z', '')
    const line = `${ts} - vite         - ${level.padEnd(8)} - ${msg}\n`
    try {
      fs.mkdirSync(logDir, { recursive: true })
      fs.appendFileSync(logFile, line, 'utf-8')
    } catch {
      // never crash the dev server due to logging
    }
  }

  return {
    name: 'vite-file-logger',
    apply: 'serve',
    configureServer(server) {
      const orig = server.config.logger
      // patch each level to also write to file
      ;(['info', 'warn', 'error', 'warnOnce'] as const).forEach(level => {
        const fileLevel = level === 'warnOnce' ? 'WARN' : level.toUpperCase()
        const original = orig[level].bind(orig)
        ;(orig as Record<string, unknown>)[level] = (msg: string, opts?: unknown) => {
          write(fileLevel, typeof msg === 'string' ? msg.replace(/\x1B\[[0-9;]*m/g, '') : String(msg))
          return (original as (...args: unknown[]) => void)(msg, opts)
        }
      })
    },
    buildEnd(err) {
      if (err) write('ERROR', err.message)
    },
  }
}

export default defineConfig({
  plugins: [
    react(),
    viteFileLogger(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon-192.svg', 'icon-512.svg', 'apple-touch-icon.svg'],

      manifest: {
        name: 'Xpert ERP — Atelier automobile',
        short_name: 'Xpert ERP',
        description: 'Gestion complète de l\'atelier automobile',
        theme_color: '#0F172A',
        background_color: '#F1F5F9',
        display: 'standalone',
        orientation: 'any',
        // Mechanics who install the app land directly on their work queue
        start_url: '/tablet',
        scope: '/',
        icons: [
          {
            src: 'icon-192.svg',
            sizes: '192x192',
            type: 'image/svg+xml',
            purpose: 'any',
          },
          {
            src: 'icon-512.svg',
            sizes: '512x512',
            type: 'image/svg+xml',
            purpose: 'any maskable',
          },
        ],
        categories: ['business', 'productivity'],
      },

      workbox: {
        // Pre-cache the app shell (JS, CSS, HTML)
        globPatterns: ['**/*.{js,css,html,svg,woff2}'],

        runtimeCaching: [
          // API calls: NetworkFirst with 5s timeout — fresh data when online,
          // last-known data when offline (mechanics keep working)
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              networkTimeoutSeconds: 5,
              expiration: {
                maxEntries: 300,
                maxAgeSeconds: 60 * 60 * 24, // 24 hours
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          // Google Fonts: StaleWhileRevalidate — loads instantly after first visit
          {
            urlPattern: ({ url }) =>
              url.hostname === 'fonts.googleapis.com' ||
              url.hostname === 'fonts.gstatic.com',
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'google-fonts',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
            },
          },
        ],
      },

      // Show the "update available" prompt instead of silently refreshing
      // in case a mechanic is mid-inspection when a deploy happens
      devOptions: {
        enabled: false, // only activate SW in production builds
      },
    }),
  ],

  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
