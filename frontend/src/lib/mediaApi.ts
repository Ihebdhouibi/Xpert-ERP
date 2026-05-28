/**
 * API client for the /media endpoints.
 *
 * Includes a high-level uploadFile() function that handles:
 *   - Session creation (or resumption from a saved session_id)
 *   - Chunked upload with per-chunk progress callbacks
 *   - Skipping already-uploaded chunks on resume
 *   - Session completion and media record creation
 */
import { apiClient } from './apiClient'

export interface UploadSessionInfo {
  session_id: string
  chunk_size_bytes: number
  total_chunks: number
  /** Part numbers (1-based) that have already been received by the server. */
  received_part_numbers: number[]
  status: string
  expires_at: string
}

export interface MediaOut {
  media_id: string
  mime_type: string
  size_bytes: number
  caption: string | null
  uploaded_at: string
  signed_url: string
}

export interface SignedUrlResponse {
  media_id: string
  url: string
  expires_in_seconds: number
}

export interface UploadOptions {
  inspectionPublicId: string
  filename: string
  mimeType: string
  caption?: string
  /** Existing session_id to resume; if absent a new session is created. */
  sessionId?: string
  onProgress?: (loaded: number, total: number) => void
}

export const mediaApi = {
  createSession(body: {
    inspection_public_id: string
    filename: string
    mime_type: string
    total_size_bytes: number
    caption?: string
  }): Promise<UploadSessionInfo> {
    return apiClient.post('/media/upload-sessions', body).then((r) => r.data)
  },

  getSession(sessionId: string): Promise<UploadSessionInfo> {
    return apiClient.get(`/media/upload-sessions/${sessionId}`).then((r) => r.data)
  },

  uploadPart(
    sessionId: string,
    partNumber: number,
    chunk: Blob,
  ): Promise<{ part_number: number; received_part_numbers: number[] }> {
    return apiClient
      .put(`/media/upload-sessions/${sessionId}/parts/${partNumber}`, chunk, {
        headers: { 'Content-Type': 'application/octet-stream' },
      })
      .then((r) => r.data)
  },

  completeUpload(sessionId: string, caption?: string): Promise<MediaOut> {
    const params = caption ? { caption } : undefined
    return apiClient
      .post(`/media/upload-sessions/${sessionId}/complete`, null, { params })
      .then((r) => r.data)
  },

  getSignedUrl(mediaId: string): Promise<SignedUrlResponse> {
    return apiClient.get(`/media/${mediaId}/signed-url`).then((r) => r.data)
  },

  deleteMedia(mediaId: string): Promise<void> {
    return apiClient.delete(`/media/${mediaId}`).then(() => undefined)
  },

  /**
   * Upload a Blob in chunks, resuming from an existing session if provided.
   *
   * Resume flow:
   *   1. If sessionId is given, GET the session to learn which parts already landed.
   *   2. Upload only the missing parts (skipping received ones).
   *   3. Complete the session and return the resulting media_id.
   *
   * The caller is responsible for persisting the returned session_id between
   * page loads so that interrupted uploads can be resumed.
   */
  async uploadFile(
    blob: Blob,
    opts: UploadOptions,
  ): Promise<{ mediaId: string; sessionId: string }> {
    const { inspectionPublicId, filename, mimeType, caption, onProgress } = opts

    let session: UploadSessionInfo

    if (opts.sessionId) {
      // Resume: fetch existing session state
      session = await mediaApi.getSession(opts.sessionId)
      if (session.status !== 'pending') {
        throw new Error(`Session ${opts.sessionId} is already ${session.status}`)
      }
    } else {
      // New upload
      session = await mediaApi.createSession({
        inspection_public_id: inspectionPublicId,
        filename,
        mime_type: mimeType,
        total_size_bytes: blob.size,
        caption,
      })
    }

    const { session_id, chunk_size_bytes, total_chunks } = session
    const alreadyReceived = new Set(session.received_part_numbers)

    let uploadedBytes = alreadyReceived.size * chunk_size_bytes

    for (let part = 1; part <= total_chunks; part++) {
      if (alreadyReceived.has(part)) {
        onProgress?.(Math.min(uploadedBytes, blob.size), blob.size)
        continue
      }

      const start = (part - 1) * chunk_size_bytes
      const end = Math.min(start + chunk_size_bytes, blob.size)
      const chunk = blob.slice(start, end)

      await mediaApi.uploadPart(session_id, part, chunk)
      uploadedBytes = Math.min(uploadedBytes + chunk.size, blob.size)
      onProgress?.(uploadedBytes, blob.size)
    }

    const media = await mediaApi.completeUpload(session_id, caption)
    return { mediaId: media.media_id, sessionId: session_id }
  },
}
