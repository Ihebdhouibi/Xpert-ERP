import { Component, type ReactNode } from 'react'
import { Box, Button, Typography } from '@mui/material'
import ErrorOutlineRoundedIcon from '@mui/icons-material/ErrorOutlineRounded'
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '60vh',
            p: 4,
            textAlign: 'center',
          }}
        >
          <Box
            sx={{
              width: 72,
              height: 72,
              borderRadius: '50%',
              bgcolor: '#FEE2E2',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mb: 3,
            }}
          >
            <ErrorOutlineRoundedIcon sx={{ color: '#EF4444', fontSize: 36 }} />
          </Box>
          <Typography variant="h5" fontWeight={700} gutterBottom>
            Une erreur inattendue est survenue
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={4} maxWidth={480}>
            L'application a rencontré un problème. Essayez de recharger la page ou contactez le support si le problème persiste.
          </Typography>
          <Button
            variant="contained"
            startIcon={<RefreshRoundedIcon />}
            onClick={() => window.location.reload()}
          >
            Recharger la page
          </Button>
        </Box>
      )
    }

    return this.props.children
  }
}
