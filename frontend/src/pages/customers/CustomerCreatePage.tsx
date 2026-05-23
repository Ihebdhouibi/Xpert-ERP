import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { Alert, Box, Paper, Typography } from '@mui/material'
import { CustomerForm } from '../../components/customer/CustomerForm'
import { DuplicatePromptDialog } from '../../components/customer/DuplicatePromptDialog'
import { customerApi } from '../../lib/customerApi'
import type {
  CustomerCreateInput,
  CustomerSummary,
  MergeMatchReason,
  MergePromptResponse,
} from '../../lib/customerApi'

export function CustomerCreatePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const [duplicate, setDuplicate] = useState<{
    existing: CustomerSummary
    reason: MergeMatchReason
  } | null>(null)

  const handleSubmit = async (payload: CustomerCreateInput) => {
    setSubmitting(true)
    setServerError(null)
    try {
      const created = await customerApi.create(payload)
      await queryClient.invalidateQueries({ queryKey: ['customers'] })
      navigate(`/customers/${created.id}`, { replace: true })
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        const body = err.response.data as MergePromptResponse
        if (body.code === 'duplicate_customer') {
          setDuplicate({ existing: body.existing, reason: body.match_reason })
        } else {
          setServerError('Conflit détecté. Vérifiez les données saisies.')
        }
      } else if (axios.isAxiosError(err) && err.response?.status === 422) {
        setServerError('Les données saisies ne sont pas valides.')
      } else {
        setServerError('Erreur lors de la création du client.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box p={4} maxWidth={900} mx="auto">
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Nouveau client
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        Saisissez au minimum un nom. Les autres champs facilitent les recherches
        futures et la facturation.
      </Typography>

      {serverError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {serverError}
        </Alert>
      )}

      <Paper sx={{ p: 3 }}>
        <CustomerForm
          mode="create"
          submitting={submitting}
          onSubmit={handleSubmit}
          onCancel={() => navigate('/customers')}
        />
      </Paper>

      <DuplicatePromptDialog
        open={duplicate !== null}
        existing={duplicate?.existing ?? null}
        reason={duplicate?.reason ?? null}
        onUseExisting={(publicId) => {
          setDuplicate(null)
          navigate(`/customers/${publicId}`)
        }}
        onClose={() => setDuplicate(null)}
      />
    </Box>
  )
}
