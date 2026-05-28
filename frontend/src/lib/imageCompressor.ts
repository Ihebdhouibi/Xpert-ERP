/**
 * Client-side image compression and EXIF stripping.
 *
 * Drawing an image onto a <canvas> and exporting via toBlob() discards all
 * EXIF/XMP metadata — the resulting blob contains only raw pixel data.
 * This satisfies the privacy requirement before any bytes leave the device.
 */

export interface CompressOptions {
  /** Maximum length of the longest edge in pixels (default 1920). */
  maxDimension: number
  /** JPEG/WebP quality, 0–1 (default 0.85). */
  quality: number
  /** Output MIME type (default image/jpeg). */
  outputMime: 'image/jpeg' | 'image/webp'
}

const DEFAULT_OPTS: CompressOptions = {
  maxDimension: 1920,
  quality: 0.85,
  outputMime: 'image/jpeg',
}

/**
 * Load an HTMLImageElement from a Blob/File, resolving when decoded.
 * Creates and revokes an object URL internally.
 */
function loadImage(blob: Blob): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve(img)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Failed to load image for compression'))
    }
    img.src = url
  })
}

/**
 * Compress an image file and strip all EXIF/metadata.
 *
 * - Downsizes to maxDimension if the image is larger.
 * - Re-encodes as JPEG or WebP at the given quality.
 * - Returns a Blob with no EXIF, GPS, device, or orientation data.
 *
 * Non-image files are returned unchanged.
 */
export async function compressAndStripExif(
  file: File | Blob,
  opts: Partial<CompressOptions> = {},
): Promise<Blob> {
  const { maxDimension, quality, outputMime } = { ...DEFAULT_OPTS, ...opts }

  const mime = file instanceof File ? file.type : (file as Blob).type
  if (!mime.startsWith('image/')) {
    return file  // pass videos and other types through unchanged
  }

  const img = await loadImage(file)

  let { naturalWidth: w, naturalHeight: h } = img
  if (w > maxDimension || h > maxDimension) {
    if (w >= h) {
      h = Math.round((h / w) * maxDimension)
      w = maxDimension
    } else {
      w = Math.round((w / h) * maxDimension)
      h = maxDimension
    }
  }

  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(img, 0, 0, w, h)

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob)
        else reject(new Error('canvas.toBlob returned null'))
      },
      outputMime,
      quality,
    )
  })
}
