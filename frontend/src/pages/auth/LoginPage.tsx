import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import axios from 'axios'
import {
  Alert,
  Box,
  Button,
  IconButton,
  InputAdornment,
  TextField,
  Typography,
} from '@mui/material'
import VisibilityIcon from '@mui/icons-material/Visibility'
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff'
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
  const [showPassword, setShowPassword] = useState(false)

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
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* ── Left brand panel ── */}
      <Box
        sx={{
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          width: '45%',
          flexShrink: 0,
          bgcolor: '#1a2744',
          px: 6,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Decorative circles */}
        <Box sx={{
          position: 'absolute', top: -80, right: -80,
          width: 320, height: 320, borderRadius: '50%',
          border: '1px solid rgba(255,255,255,0.06)',
        }} />
        <Box sx={{
          position: 'absolute', bottom: -120, left: -60,
          width: 400, height: 400, borderRadius: '50%',
          border: '1px solid rgba(255,255,255,0.04)',
        }} />
        <Box sx={{
          position: 'absolute', top: '30%', left: -40,
          width: 200, height: 200, borderRadius: '50%',
          border: '1px solid rgba(255,255,255,0.05)',
        }} />

        {/* Logo */}
        <Box sx={{ mb: 5, zIndex: 1 }}>
          <img
            src="/assets/logo-blanc.png"
            alt="Motors Utilitaires"
            style={{ width: 220, maxWidth: '100%', objectFit: 'contain' }}
          />
        </Box>

        {/* Tagline */}
        <Typography
          variant="h5"
          sx={{ color: '#fff', fontWeight: 700, textAlign: 'center', zIndex: 1, mb: 1.5 }}
        >
          Votre espace de gestion
        </Typography>
        <Typography
          variant="body2"
          sx={{ color: 'rgba(255,255,255,0.55)', textAlign: 'center', zIndex: 1, maxWidth: 280, lineHeight: 1.7 }}
        >
          Gestion des réparations, facturation, stock et bien plus — tout en un seul endroit.
        </Typography>

        {/* Bottom version */}
        <Typography
          variant="caption"
          sx={{ position: 'absolute', bottom: 24, color: 'rgba(255,255,255,0.25)', zIndex: 1 }}
        >
          Motors Utilitaires © {new Date().getFullYear()}
        </Typography>
      </Box>

      {/* ── Right form panel ── */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          px: { xs: 3, sm: 6, md: 8 },
          bgcolor: '#F8FAFC',
        }}
      >
        {/* Mobile logo (hidden on desktop) */}
        <Box sx={{ display: { xs: 'block', md: 'none' }, mb: 4 }}>
          <img src="/assets/logo.png" alt="Motors Utilitaires" style={{ height: 60, objectFit: 'contain' }} />
        </Box>

        <Box sx={{ width: '100%', maxWidth: 400 }}>
          <Typography variant="h4" fontWeight={700} color="text.primary" gutterBottom>
            Connexion
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={4}>
            Connectez-vous à votre espace professionnel
          </Typography>

          {serverError && (
            <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>
              {serverError}
            </Alert>
          )}

          <Box
            component="form"
            onSubmit={handleSubmit(onSubmit)}
            noValidate
            display="flex"
            flexDirection="column"
            gap={2.5}
          >
            <TextField
              label="Adresse email"
              type="email"
              fullWidth
              autoComplete="email"
              autoFocus
              {...register('email')}
              error={!!errors.email}
              helperText={errors.email?.message}
              sx={{ bgcolor: '#fff', borderRadius: 1 }}
            />
            <TextField
              label="Mot de passe"
              type={showPassword ? 'text' : 'password'}
              fullWidth
              autoComplete="current-password"
              {...register('password')}
              error={!!errors.password}
              helperText={errors.password?.message}
              sx={{ bgcolor: '#fff', borderRadius: 1 }}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword((v) => !v)}
                      edge="end"
                      size="small"
                      tabIndex={-1}
                    >
                      {showPassword ? <VisibilityOffIcon fontSize="small" /> : <VisibilityIcon fontSize="small" />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={isSubmitting}
              size="large"
              sx={{
                mt: 1,
                py: 1.5,
                fontWeight: 700,
                fontSize: '1rem',
                bgcolor: '#1a2744',
                '&:hover': { bgcolor: '#243b5e' },
              }}
            >
              {isSubmitting ? 'Connexion en cours…' : 'Se connecter'}
            </Button>
          </Box>
        </Box>
      </Box>
    </Box>
  )
}
