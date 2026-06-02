import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
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
