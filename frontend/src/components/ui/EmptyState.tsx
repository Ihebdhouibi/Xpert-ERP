import { type ReactNode } from 'react'
import { Box, Typography } from '@mui/material'
import InboxRoundedIcon from '@mui/icons-material/InboxRounded'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        py: 8,
        px: 3,
        textAlign: 'center',
      }}
    >
      <Box
        sx={{
          width: 64,
          height: 64,
          borderRadius: '50%',
          bgcolor: 'action.hover',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          mb: 2.5,
        }}
      >
        {icon ?? <InboxRoundedIcon sx={{ color: 'text.disabled', fontSize: 30 }} />}
      </Box>
      <Typography variant="h6" fontWeight={600} color="text.primary" gutterBottom>
        {title}
      </Typography>
      {description && (
        <Typography variant="body2" color="text.secondary" maxWidth={380} lineHeight={1.7}>
          {description}
        </Typography>
      )}
      {action && <Box mt={3}>{action}</Box>}
    </Box>
  )
}
