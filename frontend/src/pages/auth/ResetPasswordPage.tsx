import { useState } from 'react'
import { Link as RouterLink, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import axios from 'axios'
import {
  Alert,
  Box,
  Button,
  Container,
  IconButton,
  InputAdornment,
  Link,
  Paper,
  TextField,
  Typography,
} from '@mui/material'
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded'
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded'
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded'
import { apiClient } from '../../lib/apiClient'

const schema = z
  .object({
    new_password: z
      .string()
      .min(12, 'Minimum 12 caractères')
      .refine(v => /[A-Z]/.test(v), 'Doit contenir une majuscule')
      .refine(v => /[a-z]/.test(v), 'Doit contenir une minuscule')
      .refine(v => /[0-9]/.test(v), 'Doit contenir un chiffre'),
    confirm_password: z.string(),
  })
  .refine(d => d.new_password === d.confirm_password, {
    message: 'Les mots de passe ne correspondent pas',
    path: ['confirm_password'],
  })

type FormValues = z.infer<typeof schema>

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') ?? ''
  const email = searchParams.get('email') ?? ''

  const [done, setDone] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const [showPwd, setShowPwd] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  // Invalid link — token or email missing
  if (!token || !email) {
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
          <Paper elevation={3} sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="h6" fontWeight={700} gutterBottom>
              Lien invalide
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={3}>
              Ce lien de réinitialisation est invalide ou a expiré.
            </Typography>
            <Link component={RouterLink} to="/forgot-password" underline="hover">
              Demander un nouveau lien
            </Link>
          </Paper>
        </Container>
      </Box>
    )
  }

  const onSubmit = async (values: FormValues) => {
    setServerError(null)
    try {
      await apiClient.post(
        '/auth/password-reset/confirm',
        { token, new_password: values.new_password },
        { headers: { 'X-Reset-Email': email } },
      )
      setDone(true)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 400) {
        setServerError('Le lien est invalide ou a expiré. Veuillez en demander un nouveau.')
      } else {
        setServerError('Une erreur est survenue. Veuillez réessayer.')
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
          <Typography variant="h5" fontWeight={700} gutterBottom>
            Nouveau mot de passe
          </Typography>

          {done ? (
            <Box textAlign="center" py={2}>
              <CheckCircleOutlineRoundedIcon
                sx={{ fontSize: 56, color: 'success.main', mb: 1 }}
              />
              <Typography variant="body1" fontWeight={600} gutterBottom>
                Mot de passe mis à jour !
              </Typography>
              <Typography variant="body2" color="text.secondary" mb={3}>
                Vous pouvez maintenant vous connecter avec votre nouveau mot de passe.
              </Typography>
              <Button variant="contained" onClick={() => navigate('/login')}>
                Se connecter
              </Button>
            </Box>
          ) : (
            <>
              <Typography variant="body2" color="text.secondary" mb={3}>
                Choisissez un nouveau mot de passe (12 caractères minimum, avec
                majuscule, minuscule et chiffre).
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
                  label="Nouveau mot de passe"
                  type={showPwd ? 'text' : 'password'}
                  fullWidth
                  autoFocus
                  autoComplete="new-password"
                  {...register('new_password')}
                  error={!!errors.new_password}
                  helperText={errors.new_password?.message}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() => setShowPwd(p => !p)}
                          edge="end"
                          size="small"
                          aria-label="Afficher / masquer"
                        >
                          {showPwd ? <VisibilityOffRoundedIcon /> : <VisibilityRoundedIcon />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
                <TextField
                  label="Confirmer le mot de passe"
                  type={showConfirm ? 'text' : 'password'}
                  fullWidth
                  autoComplete="new-password"
                  {...register('confirm_password')}
                  error={!!errors.confirm_password}
                  helperText={errors.confirm_password?.message}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() => setShowConfirm(p => !p)}
                          edge="end"
                          size="small"
                          aria-label="Afficher / masquer"
                        >
                          {showConfirm ? <VisibilityOffRoundedIcon /> : <VisibilityRoundedIcon />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  size="large"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Enregistrement…' : 'Enregistrer le mot de passe'}
                </Button>
              </Box>

              <Box mt={2} textAlign="center">
                <Link
                  component={RouterLink}
                  to="/forgot-password"
                  underline="hover"
                  variant="body2"
                >
                  Demander un nouveau lien
                </Link>
              </Box>
            </>
          )}
        </Paper>
      </Container>
    </Box>
  )
}
