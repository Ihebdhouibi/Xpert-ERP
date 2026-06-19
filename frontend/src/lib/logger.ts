/**
 * Frontend logger — captures browser-side events and ships them to the backend
 * (POST /api/v1/logs/client → logs/frontend.log).
 *
 * Captures: explicit logs, user actions, window errors, unhandled promise
 * rejections, console.error/warn, and (via apiClient) API failures.
 *
 * Pre-deployment posture: logs everything, batched and flushed on a timer /
 * size threshold / page hide. It never throws and uses fetch+sendBeacon (not
 * the axios client) so logging can't recurse through the API error interceptor.
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
const ENDPOINT = `${BASE_URL}/api/v1/logs/client`
const FLUSH_INTERVAL_MS = 4000
const MAX_BATCH = 25

type Level = 'debug' | 'info' | 'warn' | 'error'

interface Entry {
  level: Level
  message: string
  context?: Record<string, unknown>
  timestamp: string
  url: string
  user_agent: string
  stack?: string
}

const queue: Entry[] = []
let timer: ReturnType<typeof setTimeout> | null = null

// Keep originals so our console mirror never recurses.
const origError = console.error.bind(console)
const origWarn = console.warn.bind(console)

function safeStr(v: unknown): string {
  if (typeof v === 'string') return v
  try {
    return JSON.stringify(v)
  } catch {
    return String(v)
  }
}

function flush(useBeacon = false): void {
  if (timer != null) {
    clearTimeout(timer)
    timer = null
  }
  if (queue.length === 0) return
  const entries = queue.splice(0, queue.length)
  const body = JSON.stringify({ entries })
  try {
    if (useBeacon && typeof navigator !== 'undefined' && navigator.sendBeacon) {
      navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }))
    } else {
      void fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
      }).catch(() => {
        /* never surface logging transport errors */
      })
    }
  } catch {
    /* swallow — logging must never break the app */
  }
}

function scheduleFlush(): void {
  if (timer == null) timer = setTimeout(() => flush(false), FLUSH_INTERVAL_MS)
}

function enqueue(
  level: Level,
  message: string,
  context?: Record<string, unknown>,
  stack?: string,
): void {
  queue.push({
    level,
    message,
    context,
    timestamp: new Date().toISOString(),
    url: typeof location !== 'undefined' ? location.href : '',
    user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
    stack,
  })
  if (queue.length >= MAX_BATCH) flush(false)
  else scheduleFlush()
}

export const logger = {
  debug: (message: string, context?: Record<string, unknown>) => enqueue('debug', message, context),
  info: (message: string, context?: Record<string, unknown>) => enqueue('info', message, context),
  warn: (message: string, context?: Record<string, unknown>) => enqueue('warn', message, context),
  error: (message: string, context?: Record<string, unknown>, stack?: string) =>
    enqueue('error', message, context, stack),
  /** Record a user action (clicks, navigations, submits, …). */
  action: (name: string, context?: Record<string, unknown>) =>
    enqueue('info', `user_action:${name}`, context),
  /** Force-send everything immediately (e.g. before logout). */
  flush: () => flush(false),
}

let installed = false

export function initLogging(): void {
  if (installed || typeof window === 'undefined') return
  installed = true

  window.addEventListener('error', (e: ErrorEvent) => {
    enqueue(
      'error',
      e.message || 'window_error',
      { filename: e.filename, lineno: e.lineno, colno: e.colno },
      e.error?.stack,
    )
  })

  window.addEventListener('unhandledrejection', (e: PromiseRejectionEvent) => {
    const reason = e.reason as { message?: string; stack?: string } | undefined
    enqueue(
      'error',
      'unhandled_rejection',
      { reason: safeStr(reason?.message ?? e.reason) },
      reason?.stack,
    )
  })

  // Flush on tab hide / navigation away (best-effort via sendBeacon).
  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush(true)
  })
  window.addEventListener('pagehide', () => flush(true))

  // Mirror console.error / console.warn into the stream (keep original output).
  console.error = (...args: unknown[]) => {
    origError(...args)
    try {
      enqueue('error', args.map(safeStr).join(' '))
    } catch {
      /* ignore */
    }
  }
  console.warn = (...args: unknown[]) => {
    origWarn(...args)
    try {
      enqueue('warn', args.map(safeStr).join(' '))
    } catch {
      /* ignore */
    }
  }

  enqueue('info', 'frontend_logging_initialized', {
    ua: typeof navigator !== 'undefined' ? navigator.userAgent : '',
  })
}
