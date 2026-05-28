/**
 * MediaUploadButton — captures a photo (camera or gallery), compresses it,
 * strips EXIF, uploads in chunks, and calls onUploaded with the media_id.
 *
 * Supports resumable uploads: the session_id is kept in component state and
 * reused if the browser tab is not closed between retries.
 */
import { useEffect, useRef, useState } from 'react'
import {
  Box,
  CircularProgress,
  IconButton,
  LinearProgress,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material'
import AddAPhotoIcon from '@mui/icons-material/AddAPhoto'
import DeleteIcon from '@mui/icons-material/Delete'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'

import { compressAndStripExif } from '../../lib/imageCompressor'
import { mediaApi } from '../../lib/mediaApi'

interface Props {
  inspectionPublicId: string
  /** Called with the new media_id after a successful upload. */
  onUploaded: (mediaId: string) => void
  /** Called to request removal of a previously uploaded media. */
  onDelete?: (mediaId: string) => void
  /** Already-attached media IDs for this item. */
  mediaIds: string[]
  disabled?: boolean
}

interface PendingUpload {
  sessionId?: string
  progress: number  // 0–100
  error?: string
}

export function MediaUploadButton({
  inspectionPublicId,
  onUploaded,
  onDelete,
  mediaIds,
  disabled = false,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [pending, setPending] = useState<PendingUpload | null>(null)

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!inputRef.current) return
    inputRef.current.value = ''  // allow re-selecting the same file
    if (!file) return

    setPending({ progress: 0 })

    try {
      // 1. Client-side compression + EXIF strip (canvas redraw)
      const compressed = await compressAndStripExif(file, {
        maxDimension: 1920,
        quality: 0.85,
        outputMime: 'image/jpeg',
      })

      const outputMime = compressed.type || 'image/jpeg'
      const filename = file.name.replace(/\.[^.]+$/, '.jpg')

      // 2. Chunked upload with resume support
      const { mediaId, sessionId } = await mediaApi.uploadFile(compressed, {
        inspectionPublicId,
        filename,
        mimeType: outputMime,
        sessionId: pending?.sessionId,  // resume if we have a session
        onProgress: (loaded, total) => {
          const pct = total > 0 ? Math.round((loaded / total) * 100) : 0
          setPending((prev) => (prev ? { ...prev, progress: pct, sessionId } : null))
        },
      })

      setPending(null)
      onUploaded(mediaId)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setPending((prev) => (prev ? { ...prev, error: msg } : null))
    }
  }

  const triggerPicker = () => {
    if (!disabled && !pending) inputRef.current?.click()
  }

  return (
    <Box>
      {/* Thumbnail strip for already-uploaded media */}
      {mediaIds.length > 0 && (
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap mb={0.5}>
          {mediaIds.map((id) => (
            <Box
              key={id}
              sx={{
                position: 'relative',
                width: 56,
                height: 56,
                borderRadius: 1,
                overflow: 'hidden',
                border: '1px solid',
                borderColor: 'divider',
                bgcolor: 'grey.100',
              }}
            >
              <MediaThumb mediaId={id} />
              {onDelete && !disabled && (
                <IconButton
                  size="small"
                  sx={{
                    position: 'absolute',
                    top: 0,
                    right: 0,
                    p: 0,
                    bgcolor: 'rgba(0,0,0,0.45)',
                    color: 'white',
                    '&:hover': { bgcolor: 'rgba(0,0,0,0.7)' },
                  }}
                  onClick={() => onDelete(id)}
                >
                  <DeleteIcon sx={{ fontSize: 14 }} />
                </IconButton>
              )}
            </Box>
          ))}
        </Stack>
      )}

      {/* Upload progress */}
      {pending && (
        <Box mb={0.5}>
          {pending.error ? (
            <Stack direction="row" alignItems="center" spacing={0.5}>
              <ErrorOutlineIcon color="error" fontSize="small" />
              <Typography variant="caption" color="error">
                {pending.error}
              </Typography>
              <Tooltip title="Retry upload">
                <IconButton size="small" onClick={triggerPicker}>
                  <AddAPhotoIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Stack>
          ) : (
            <Stack direction="row" alignItems="center" spacing={1}>
              <CircularProgress size={14} />
              <Box flex={1}>
                <LinearProgress variant="determinate" value={pending.progress} />
              </Box>
              <Typography variant="caption">{pending.progress}%</Typography>
            </Stack>
          )}
        </Box>
      )}

      {/* Camera trigger button */}
      {!pending && (
        <Tooltip title="Ajouter une photo">
          <span>
            <IconButton
              size="small"
              onClick={triggerPicker}
              disabled={disabled}
              color="default"
            >
              <AddAPhotoIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      )}

      {/* Hidden file input — accept="image/*" capture="environment" opens the rear camera on mobile */}
      <input
        ref={inputRef}
        type="file"
        accept="image/*,video/mp4,video/quicktime"
        capture="environment"
        style={{ display: 'none' }}
        onChange={handleFileSelect}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Lazy-loading thumbnail: fetches signed URL on mount
// ---------------------------------------------------------------------------

function MediaThumb({ mediaId }: { mediaId: string }) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    mediaApi.getSignedUrl(mediaId).then((r) => {
      if (!cancelled) setUrl(r.url)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [mediaId])

  if (!url) {
    return (
      <Box
        sx={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <CircularProgress size={16} />
      </Box>
    )
  }

  return (
    <Box
      component="img"
      src={url}
      alt=""
      sx={{ width: '100%', height: '100%', objectFit: 'cover' }}
    />
  )
}
