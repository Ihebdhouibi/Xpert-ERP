import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Grid,
  InputAdornment,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import DirectionsCarRoundedIcon from '@mui/icons-material/DirectionsCarRounded'
import CalendarMonthRoundedIcon from '@mui/icons-material/CalendarMonthRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import {
  vehiclesApi,
  FUEL_TYPE_LABELS,
  type FuelType,
  type VehicleCreateInput,
} from '../../lib/vehiclesApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { useToast } from '../../contexts/ToastContext'

const FUEL_TYPES = Object.entries(FUEL_TYPE_LABELS).map(([value, label]) => ({
  value: value as FuelType,
  label,
}))

function SectionCard({
  title,
  icon,
  children,
}: {
  title: string
  icon?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardContent sx={{ p: 3 }}>
        <Stack direction="row" alignItems="center" spacing={1.5} mb={2.5}>
          {icon && <Box sx={{ color: 'primary.main' }}>{icon}</Box>}
          <Typography variant="subtitle1" fontWeight={700}>
            {title}
          </Typography>
        </Stack>
        <Divider sx={{ mb: 2.5 }} />
        {children}
      </CardContent>
    </Card>
  )
}

export function VehicleCreatePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()

  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  const [make, setMake] = useState('')
  const [model, setModel] = useState('')
  const [year, setYear] = useState('')
  const [fuelType, setFuelType] = useState<FuelType | ''>('')
  const [color, setColor] = useState('')
  const [registration, setRegistration] = useState('')
  const [vin, setVin] = useState('')
  const [mileage, setMileage] = useState('')
  const [ctDate, setCtDate] = useState('')
  const [maintenanceDate, setMaintenanceDate] = useState('')
  const [customerId, setCustomerId] = useState('')

  const canSubmit = make.trim().length > 0 && model.trim().length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setServerError(null)
    try {
      const input: VehicleCreateInput = {
        make: make.trim(),
        model: model.trim(),
        year: year ? Number(year) : undefined,
        fuel_type: fuelType || undefined,
        color: color.trim() || undefined,
        registration: registration.trim().toUpperCase() || undefined,
        vin: vin.trim().toUpperCase() || undefined,
        mileage_current: mileage ? Number(mileage) : undefined,
        technical_inspection_due_at: ctDate || undefined,
        maintenance_due_at: maintenanceDate || undefined,
        customer_id: customerId ? Number(customerId) : undefined,
      }
      const created = await vehiclesApi.create(input)
      await queryClient.invalidateQueries({ queryKey: ['vehicles'] })
      success('Véhicule créé avec succès')
      navigate(`/vehicles/${created.id}`, { replace: true })
    } catch {
      setServerError('Erreur lors de la création. Vérifiez les données saisies.')
      toastError('Impossible de créer le véhicule.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <PageHeader
        title="Nouveau véhicule"
        subtitle="Enregistrez un véhicule dans le parc atelier"
        breadcrumbs={[
          { label: 'Véhicules', href: '/vehicles' },
          { label: 'Nouveau véhicule' },
        ]}
        actions={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={<ArrowBackRoundedIcon />}
              onClick={() => navigate('/vehicles')}
              disabled={submitting}
            >
              Annuler
            </Button>
            <Button
              type="submit"
              variant="contained"
              startIcon={<SaveRoundedIcon />}
              disabled={!canSubmit || submitting}
            >
              Enregistrer
            </Button>
          </Stack>
        }
      />

      {serverError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {serverError}
        </Alert>
      )}

      <Grid container spacing={3} sx={{ maxWidth: 920 }}>
        {/* Left column — identity + registration */}
        <Grid item xs={12} md={7}>
          <Stack spacing={3}>
            <SectionCard
              title="Identification du véhicule"
              icon={<DirectionsCarRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    label="Marque *"
                    value={make}
                    onChange={e => setMake(e.target.value)}
                    fullWidth
                    placeholder="ex. Peugeot"
                    autoFocus
                    error={submitting && !make.trim()}
                    helperText={submitting && !make.trim() ? 'Champ obligatoire' : undefined}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    label="Modèle *"
                    value={model}
                    onChange={e => setModel(e.target.value)}
                    fullWidth
                    placeholder="ex. 308"
                    error={submitting && !model.trim()}
                    helperText={submitting && !model.trim() ? 'Champ obligatoire' : undefined}
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    label="Année"
                    type="number"
                    value={year}
                    onChange={e => setYear(e.target.value)}
                    fullWidth
                    placeholder={String(new Date().getFullYear())}
                    inputProps={{ min: 1900, max: new Date().getFullYear() + 1 }}
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    label="Carburant"
                    select
                    value={fuelType}
                    onChange={e => setFuelType(e.target.value as FuelType | '')}
                    fullWidth
                  >
                    <MenuItem value=""><em>Non renseigné</em></MenuItem>
                    {FUEL_TYPES.map(ft => (
                      <MenuItem key={ft.value} value={ft.value}>{ft.label}</MenuItem>
                    ))}
                  </TextField>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    label="Couleur"
                    value={color}
                    onChange={e => setColor(e.target.value)}
                    fullWidth
                    placeholder="ex. Gris anthracite"
                  />
                </Grid>
              </Grid>
            </SectionCard>

            <SectionCard title="Immatriculation & VIN">
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    label="Immatriculation"
                    value={registration}
                    onChange={e => setRegistration(e.target.value.toUpperCase())}
                    fullWidth
                    placeholder="AB-123-CD"
                    inputProps={{
                      style: {
                        fontFamily: 'monospace',
                        letterSpacing: '0.1em',
                        fontWeight: 700,
                        fontSize: '1rem',
                      },
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    label="Numéro VIN"
                    value={vin}
                    onChange={e => setVin(e.target.value.toUpperCase())}
                    fullWidth
                    placeholder="VF3XXXXXXXXXX"
                    inputProps={{
                      maxLength: 17,
                      style: { fontFamily: 'monospace', fontSize: '0.875rem' },
                    }}
                    helperText={vin ? `${vin.length} / 17 caractères` : 'Numéro de châssis à 17 caractères'}
                  />
                </Grid>
              </Grid>
            </SectionCard>
          </Stack>
        </Grid>

        {/* Right column — maintenance + owner */}
        <Grid item xs={12} md={5}>
          <Stack spacing={3}>
            <SectionCard
              title="Entretien & Contrôles"
              icon={<CalendarMonthRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Stack spacing={2}>
                <TextField
                  label="Kilométrage actuel"
                  type="number"
                  value={mileage}
                  onChange={e => setMileage(e.target.value)}
                  fullWidth
                  placeholder="ex. 75 000"
                  inputProps={{ min: 0 }}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <Typography variant="caption" color="text.secondary">km</Typography>
                      </InputAdornment>
                    ),
                  }}
                />
                <TextField
                  label="Échéance contrôle technique"
                  type="date"
                  value={ctDate}
                  onChange={e => setCtDate(e.target.value)}
                  fullWidth
                  InputLabelProps={{ shrink: true }}
                />
                <TextField
                  label="Date prochain entretien"
                  type="date"
                  value={maintenanceDate}
                  onChange={e => setMaintenanceDate(e.target.value)}
                  fullWidth
                  InputLabelProps={{ shrink: true }}
                />
              </Stack>
            </SectionCard>

            <SectionCard
              title="Propriétaire"
              icon={<PersonRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <TextField
                label="ID Client"
                type="number"
                value={customerId}
                onChange={e => setCustomerId(e.target.value)}
                fullWidth
                placeholder="Numéro du client"
                inputProps={{ min: 1 }}
                helperText="Optionnel — peut être associé après création"
              />
            </SectionCard>
          </Stack>
        </Grid>
      </Grid>
    </Box>
  )
}
