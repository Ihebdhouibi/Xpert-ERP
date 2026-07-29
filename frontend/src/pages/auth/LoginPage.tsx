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
  Collapse,
  IconButton,
  InputAdornment,
  TextField,
  Typography,
} from '@mui/material'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import LoginIcon from '@mui/icons-material/Login'
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
  const [formVisible, setFormVisible] = useState(true)
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
          width: formVisible ? '45%' : '100%',
          flexShrink: 0,
          bgcolor: '#1a2744',
          px: 6,
          position: 'relative',
          overflow: 'hidden',
          transition: 'width 0.4s cubic-bezier(0.4,0,0.2,1)',
        }}
      >
        {/* Decorative circles */}
        <Box sx={{ position: 'absolute', top: -80, right: -80, width: 320, height: 320, borderRadius: '50%', border: '1px solid rgba(255,255,255,0.06)' }} />
        <Box sx={{ position: 'absolute', bottom: -120, left: -60, width: 400, height: 400, borderRadius: '50%', border: '1px solid rgba(255,255,255,0.04)' }} />
        <Box sx={{ position: 'absolute', top: '30%', left: -40, width: 200, height: 200, borderRadius: '50%', border: '1px solid rgba(255,255,255,0.05)' }} />

        {/* Toggle button — top-right edge */}
        <IconButton
          onClick={() => setFormVisible((v) => !v)}
          size="small"
          sx={{
            position: 'absolute', top: 20, right: 20, zIndex: 2,
            color: 'rgba(255,255,255,0.5)',
            border: '1px solid rgba(255,255,255,0.15)',
            borderRadius: 1,
            '&:hover': { bgcolor: 'rgba(255,255,255,0.08)', color: '#fff' },
          }}
          title={formVisible ? 'Masquer le formulaire' : 'Afficher le formulaire'}
        >
          {formVisible ? <ChevronLeftIcon fontSize="small" /> : <ChevronRightIcon fontSize="small" />}
        </IconButton>

        {/* Logo */}
        <Box sx={{ mb: 4, zIndex: 1 }}>
          <img
            src="/assets/logo-blanc.png"
            alt="Motors Utilitaires"
            style={{ width: formVisible ? 260 : 300, maxWidth: '100%', objectFit: 'contain', transition: 'width 0.4s' }}
          />
        </Box>

        {/* Tagline */}
        <Typography variant="h5" sx={{ color: '#fff', fontWeight: 700, textAlign: 'center', zIndex: 1, mb: 1.5 }}>
          Votre espace de gestion
        </Typography>
        <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.55)', textAlign: 'center', zIndex: 1, maxWidth: 320, lineHeight: 1.7, mb: 4 }}>
          Gestion des réparations, facturation, stock et bien plus — tout en un seul endroit.
        </Typography>

        {/* Feature list — visible only when form is hidden */}
        <Collapse in={!formVisible} timeout={300}>
          <Box sx={{ zIndex: 1, width: '100%', maxWidth: 360, mb: 5 }}>
            {[
              'Ordres de réparation & suivi atelier',
              'Facturation, devis et avoirs',
              'Gestion du stock & pièces',
              'Bons de livraison fournisseurs',
              'OCR automatique des documents',
            ].map((feature) => (
              <Box key={feature} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.75 }}>
                <Box sx={{
                  width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                  bgcolor: 'rgba(245,158,11,0.15)',
                  border: '1px solid rgba(245,158,11,0.4)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Box component="span" sx={{ color: '#F59E0B', fontSize: 13, fontWeight: 700, lineHeight: 1 }}>✓</Box>
                </Box>
                <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.85)', lineHeight: 1.4 }}>
                  {feature}
                </Typography>
              </Box>
            ))}
          </Box>

          {/* CTA button when form is hidden */}
          <Box sx={{ display: 'flex', justifyContent: 'center', zIndex: 1 }}>
            <Button
              variant="contained"
              size="large"
              startIcon={<LoginIcon />}
              onClick={() => setFormVisible(true)}
              sx={{
                bgcolor: '#F59E0B', color: '#1a2744', fontWeight: 700,
                px: 4, py: 1.5, fontSize: '1rem',
                '&:hover': { bgcolor: '#D97706' },
              }}
            >
              Se connecter
            </Button>
          </Box>
        </Collapse>

        {/* Bottom version */}
        <Typography variant="caption" sx={{ position: 'absolute', bottom: 24, color: 'rgba(255,255,255,0.25)', zIndex: 1 }}>
          Motors Utilitaires © {new Date().getFullYear()}
        </Typography>
      </Box>

      {/* ── Right form panel — single form, always mounted, responsive ── */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          flex: 1,
          px: { xs: 3, md: 8 },
          bgcolor: '#F8FAFC',
          overflow: 'hidden',
          maxWidth: formVisible ? { xs: '100%', md: '55vw' } : { xs: '100%', md: 0 },
          opacity: { xs: 1, md: formVisible ? 1 : 0 },
          transition: 'max-width 0.4s cubic-bezier(0.4,0,0.2,1), opacity 0.3s ease',
          pointerEvents: formVisible ? 'auto' : { xs: 'auto', md: 'none' },
        }}
      >
        <Box sx={{ width: '100%', maxWidth: 400, minWidth: { md: 320 } }}>
          {/* Mobile-only logo */}
          <Box sx={{ display: { xs: 'flex', md: 'none' }, justifyContent: 'center', mb: 3 }}>
            <img src="/assets/logo.png" alt="Motors Utilitaires" style={{ height: 60, objectFit: 'contain' }} />
          </Box>
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

          <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate display="flex" flexDirection="column" gap={2.5}>
            <TextField
              label="Adresse email"
              type="email"
              fullWidth
              autoComplete="email"
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
                    <IconButton onClick={() => setShowPassword((v) => !v)} edge="end" size="small" tabIndex={-1}>
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
              sx={{ mt: 1, py: 1.5, fontWeight: 700, fontSize: '1rem', bgcolor: '#1a2744', '&:hover': { bgcolor: '#243b5e' } }}
            >
              {isSubmitting ? 'Connexion en cours…' : 'Se connecter'}
            </Button>
          </Box>
        </Box>
      </Box>
    </Box>
  )
}
