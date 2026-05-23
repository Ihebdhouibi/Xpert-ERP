import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { Alert, Box, CircularProgress, Paper, Typography } from '@mui/material'
import { CustomerForm } from '../../components/customer/CustomerForm'
import { customerApi } from '../../lib/customerApi'
import type { CustomerCreateInput, CustomerStatus } from '../../lib/customerApi'

export function CustomerEditPage() {
  const { publicId = '' } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    data: customer,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['customer', publicId],
    queryFn: () => customerApi.get(publicId),
    enabled: !!publicId,
  })

  const handleSubmit = async (
    payload: CustomerCreateInput & { status?: CustomerStatus },
  ) => {
    if (!customer) return
    setSubmitting(true)
    setServerError(null)
    try {
      await customerApi.update(publicId, {
        version: customer.version,
        full_name: payload.full_name,
        company_name: payload.company_name,
        fiscal_id: payload.fiscal_id,
        email: payload.email,
        phone_e164: payload.phone_e164,
        address: payload.address,
        segment: payload.segment,
        status: payload.status,
        notes: payload.notes,
      })
      await queryClient.invalidateQueries({ queryKey: ['customers'] })
      await queryClient.invalidateQueries({ queryKey: ['customer', publicId] })
      navigate(`/customers/${publicId}`, { replace: true })
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        const detail = err.response.data?.detail
        if (detail?.code === 'stale_version') {
          setServerError(
            'Ce client a été modifié par un autre utilisateur. Rechargez la page et réessayez.',
          )
        } else if (detail?.code === 'fiscal_id_taken') {
          setServerError(
            'Cet identifiant fiscal est déjà utilisé par un autre client.',
          )
        } else {
          setServerError('Conflit lors de la mise à jour.')
        }
      } else if (axios.isAxiosError(err) && err.response?.status === 404) {
        setServerError('Client introuvable.')
      } else {
        setServerError('Erreur lors de la mise à jour.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (isLoading) {
    return (
      <Box p={4} display="flex" justifyContent="center">
        <CircularProgress />
      </Box>
    )
  }
  if (isError || !customer) {
    return (
      <Box p={4}>
        <Alert severity="error">Impossible de charger ce client.</Alert>
      </Box>
    )
  }

  return (
    <Box p={4} maxWidth={900} mx="auto">
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Modifier le client
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        {customer.full_name}
        {customer.company_name ? ` — ${customer.company_name}` : ''}
      </Typography>

      {serverError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {serverError}
        </Alert>
      )}

      <Paper sx={{ p: 3 }}>
        <CustomerForm
          mode="edit"
          initial={customer}
          submitting={submitting}
          onSubmit={handleSubmit}
          onCancel={() => navigate(`/customers/${publicId}`)}
        />
      </Paper>
    </Box>
  )
}
