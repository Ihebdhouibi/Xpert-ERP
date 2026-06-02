import { Box, CircularProgress, Typography } from '@mui/material'

interface LoadingScreenProps {
  message?: string
  fullPage?: boolean
}

export function LoadingScreen({ message, fullPage = true }: LoadingScreenProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: fullPage ? '60vh' : 200,
        gap: 2,
      }}
    >
      <CircularProgress size={36} thickness={4} />
      {message && (
        <Typography variant="body2" color="text.secondary" fontWeight={500}>
          {message}
        </Typography>
      )}
    </Box>
  )
}

export function TableLoadingSkeleton({ cols, rows = 5 }: { cols: number; rows?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, ri) => (
        <tr key={ri}>
          {Array.from({ length: cols }).map((_, ci) => (
            <td key={ci} style={{ padding: '12px 16px' }}>
              <Box
                sx={{
                  height: 14,
                  borderRadius: 2,
                  bgcolor: '#F1F5F9',
                  width: ci === 0 ? '60%' : ci % 3 === 0 ? '40%' : '80%',
                  animation: 'pulse 1.5s ease-in-out infinite',
                  '@keyframes pulse': {
                    '0%, 100%': { opacity: 1 },
                    '50%': { opacity: 0.4 },
                  },
                }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}
