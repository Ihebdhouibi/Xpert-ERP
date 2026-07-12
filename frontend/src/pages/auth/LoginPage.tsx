import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import axios from 'axios'
import {
  Alert,
  Box,
  Button,
  Container,
  Link,
  Paper,
  TextField,
  Typography,
} from '@mui/material'
import { useAuth } from '../../contexts/AuthContext'

const loginSchema = z.object({
  email: z.string().email('Email invalide'),
  password: z.string().min(1, 'Mot de passe requis'),
})

type LoginFormValues = z.infer<typeof loginSchema>

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (values: LoginFormValues) => {
    setServerError(null)
    try {
      await login(values.email, values.password)
      navigate('/', { replace: true })
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        setServerError('Email ou mot de passe incorrect.')
      } else if (axios.isAxiosError(err) && !err.response) {
        setServerError('Impossible de joindre le serveur. Vérifiez votre connexion.')
      } else {
        setServerError('Une erreur inattendue est survenue. Veuillez réessayer.')
      }
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        bgcolor: 'background.default',
      }}
    >
      <Container maxWidth="xs">
        <Paper elevation={3} sx={{ p: 4 }}>
          <Box sx={{ mb: 2, textAlign: 'center' }}>
            <img
              src="/assets/logo.png"
              alt="Motors Utilitaires"
              style={{ maxHeight: 80, maxWidth: '100%', objectFit: 'contain' }}
            />
          </Box>
          <Typography variant="body2" color="text.secondary" mb={3}>
            Connectez-vous a votre espace
          </Typography>

          {serverError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {serverError}
            </Alert>
          )}

          <Box
            component="form"
            onSubmit={handleSubmit(onSubmit)}
            noValidate
            display="flex"
            flexDirection="column"
            gap={2}
          >
            <TextField
              label="Email"
              type="email"
              fullWidth
              autoComplete="email"
              {...register('email')}
              error={!!errors.email}
              helperText={errors.email?.message}
            />
            <TextField
              label="Mot de passe"
              type="password"
              fullWidth
              autoComplete="current-password"
              {...register('password')}
              error={!!errors.password}
              helperText={errors.password?.message}
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={isSubmitting}
              size="large"
            >
              {isSubmitting ? 'Connexion...' : 'Se connecter'}
            </Button>
          </Box>

          <Box mt={2} textAlign="center">
            <Link
              component={RouterLink}
              to="/forgot-password"
              underline="hover"
              variant="body2"
            >
              Mot de passe oublié ?
            </Link>
          </Box>
        </Paper>
      </Container>
    </Box>
  )
}
