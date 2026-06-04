import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
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
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded'
import { apiClient } from '../../lib/apiClient'

const schema = z.object({
  email: z.string().email('Email invalide'),
})
type FormValues = z.infer<typeof schema>

export function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: FormValues) => {
    setServerError(null)
    try {
      await apiClient.post('/auth/password-reset/request', { email: values.email })
      setSubmitted(true)
    } catch {
      setServerError('Une erreur est survenue. Veuillez réessayer.')
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
            Mot de passe oublié
          </Typography>

          {submitted ? (
            <Box textAlign="center" py={2}>
              <CheckCircleOutlineRoundedIcon
                sx={{ fontSize: 56, color: 'success.main', mb: 1 }}
              />
              <Typography variant="body1" fontWeight={600} gutterBottom>
                Email envoyé !
              </Typography>
              <Typography variant="body2" color="text.secondary" mb={3}>
                Si cette adresse est associée à un compte, vous recevrez un lien
                de réinitialisation dans quelques minutes.
              </Typography>
              <Link component={RouterLink} to="/login" underline="hover">
                Retour à la connexion
              </Link>
            </Box>
          ) : (
            <>
              <Typography variant="body2" color="text.secondary" mb={3}>
                Saisissez votre adresse email. Si elle est liée à un compte, vous
                recevrez un lien de réinitialisation.
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
                  autoFocus
                  {...register('email')}
                  error={!!errors.email}
                  helperText={errors.email?.message}
                />
                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  size="large"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Envoi en cours…' : 'Envoyer le lien'}
                </Button>
              </Box>

              <Box mt={2} textAlign="center">
                <Link component={RouterLink} to="/login" underline="hover" variant="body2">
                  Retour à la connexion
                </Link>
              </Box>
            </>
          )}
        </Paper>
      </Container>
    </Box>
  )
}
