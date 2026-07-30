import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  MenuItem,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material'
import StorefrontRoundedIcon from '@mui/icons-material/StorefrontRounded'
import SecurityRoundedIcon from '@mui/icons-material/SecurityRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded'
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded'
import BarChartRoundedIcon from '@mui/icons-material/BarChartRounded'
import PhotoCameraRoundedIcon from '@mui/icons-material/PhotoCameraRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import { settingsApi } from '../../lib/settingsApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { useToast } from '../../contexts/ToastContext'

// ─── Settings catalog ─────────────────────────────────────────────────────────

type SettingType = 'string' | 'int' | 'float' | 'bool' | 'select' | 'textarea'

interface SettingDef {
  key: string
  label: string
  type: SettingType
  description: string
  options?: { value: string; label: string }[]
  placeholder?: string
}

interface SettingSection {
  id: string
  label: string
  icon: React.ReactNode
  settings: SettingDef[]
}

const CATALOG: SettingSection[] = [
  {
    id: 'garage',
    label: 'Garage & Identité',
    icon: <StorefrontRoundedIcon />,
    settings: [
      { key: 'pdf_garage_name', label: 'Nom du garage', type: 'string', description: 'Apparaît en en-tête sur tous les documents PDF', placeholder: 'Ex: Garage Dupont' },
      { key: 'pdf_garage_address', label: 'Adresse', type: 'textarea', description: 'Adresse complète du garage (peut contenir des retours à la ligne)' },
      { key: 'pdf_garage_phone', label: 'Téléphone', type: 'string', description: 'Numéro affiché sur les documents', placeholder: 'Ex: +33 1 23 45 67 89' },
      { key: 'pdf_garage_email', label: 'Email de contact', type: 'string', description: 'Email affiché sur les PDF', placeholder: 'contact@garage.fr' },
      { key: 'pdf_vat_number', label: 'N° TVA', type: 'string', description: 'Numéro de TVA intracommunautaire', placeholder: 'FR12345678901' },
      { key: 'pdf_currency_symbol', label: 'Symbole monétaire', type: 'string', description: 'Symbole utilisé sur les documents (€, DT, MAD…)', placeholder: '€' },
      { key: 'pdf_payment_terms', label: 'Conditions de paiement', type: 'string', description: 'Texte en pied de facture', placeholder: 'Paiement à 30 jours' },
      { key: 'pdf_legal_mention', label: 'Mention légale', type: 'textarea', description: 'Mention légale en pied de page PDF' },
      { key: 'pdf_bank_details', label: 'Coordonnées bancaires', type: 'textarea', description: 'IBAN / RIB affiché sur les factures' },
      { key: 'pdf_footer_text', label: 'Pied de page PDF', type: 'string', description: 'Texte libre en bas de chaque document' },
    ],
  },
  {
    id: 'security',
    label: 'Sécurité & Authentification',
    icon: <SecurityRoundedIcon />,
    settings: [
      { key: 'auth_max_failed_attempts', label: 'Tentatives avant verrouillage', type: 'int', description: 'Nombre d\'échecs de connexion avant blocage automatique du compte', placeholder: '5' },
      { key: 'auth_lockout_minutes', label: 'Durée de verrouillage (minutes)', type: 'int', description: 'Combien de minutes un compte reste bloqué après trop de tentatives', placeholder: '15' },
      { key: 'password_reset_expiry_minutes', label: 'Expiration lien reset (minutes)', type: 'int', description: 'Durée de validité du lien envoyé par email pour réinitialiser le mot de passe', placeholder: '30' },
      { key: 'access_token_expire_minutes', label: 'Durée de session (minutes)', type: 'int', description: 'Durée de validité du token JWT — l\'utilisateur est déconnecté après ce délai d\'inactivité', placeholder: '30' },
    ],
  },
  {
    id: 'billing',
    label: 'Facturation & Finance',
    icon: <ReceiptRoundedIcon />,
    settings: [
      { key: 'credit_currency', label: 'Devise principale', type: 'string', description: 'Code ISO-4217 utilisé pour les encours clients et la balance (EUR, MAD, TND…)', placeholder: 'EUR' },
      {
        key: 'credit_limit_mode',
        label: 'Mode limite de crédit',
        type: 'select',
        description: 'Comportement quand un client dépasse sa limite de crédit',
        options: [
          { value: 'block', label: 'Bloquer — rejeter la transaction' },
          { value: 'warn', label: 'Avertir — journaliser seulement' },
        ],
      },
      { key: 'cfg_po_match_tolerance_percent', label: 'Tolérance rapprochement 3 voies (%)', type: 'float', description: 'Écart acceptable entre BC, réception et facture fournisseur avant alerte', placeholder: '5.0' },
      {
        key: 'cfg_accounting_format',
        label: 'Format export comptable par défaut',
        type: 'select',
        description: 'Format utilisé lors des exports vers votre logiciel de comptabilité',
        options: [
          { value: 'generic_csv', label: 'CSV générique' },
          { value: 'sage', label: 'Sage' },
          { value: 'cegid', label: 'Cegid' },
          { value: 'ebp', label: 'EBP' },
        ],
      },
    ],
  },
  {
    id: 'stock',
    label: 'Stock & Pièces',
    icon: <InventoryRoundedIcon />,
    settings: [
      { key: 'cfg_allow_negative_stock', label: 'Autoriser le stock négatif', type: 'bool', description: 'Si activé, les sorties de stock peuvent rendre la quantité disponible négative (un motif obligatoire sera requis)' },
    ],
  },
  {
    id: 'notifications',
    label: 'Notifications',
    icon: <NotificationsRoundedIcon />,
    settings: [
      { key: 'cfg_quiet_hours_start', label: 'Début des heures silencieuses', type: 'string', description: 'Format HH:MM — pas d\'envoi de SMS ou d\'email avant cette heure', placeholder: '22:00' },
      { key: 'cfg_quiet_hours_end', label: 'Fin des heures silencieuses', type: 'string', description: 'Format HH:MM — reprise des envois après cette heure', placeholder: '08:00' },
      { key: 'cfg_notification_max_retries', label: 'Tentatives max par notification', type: 'int', description: 'Nombre de tentatives avant abandon en cas d\'échec d\'envoi', placeholder: '3' },
      { key: 'cfg_reminder_delay_1_days', label: 'Délai 1ère relance (jours)', type: 'int', description: 'Jours après échéance pour la première relance automatique', placeholder: '7' },
      { key: 'cfg_reminder_delay_2_days', label: 'Délai 2ème relance (jours)', type: 'int', description: 'Jours après échéance pour la deuxième relance', placeholder: '14' },
      { key: 'cfg_reminder_delay_3_days', label: 'Délai 3ème relance (jours)', type: 'int', description: 'Jours après échéance pour la troisième et dernière relance', placeholder: '30' },
    ],
  },
  {
    id: 'kpi',
    label: 'KPI & Analytique',
    icon: <BarChartRoundedIcon />,
    settings: [
      { key: 'cfg_kpi_refresh_interval_seconds', label: 'Intervalle d\'actualisation KPI (secondes)', type: 'int', description: 'Fréquence de mise à jour du tableau de bord — valeur plus basse = plus de charge serveur', placeholder: '300' },
      { key: 'cfg_kpi_workshop_capacity', label: 'Capacité atelier (postes)', type: 'int', description: 'Nombre de postes de travail simultanés — utilisé pour calculer le taux d\'occupation', placeholder: '10' },
    ],
  },
  {
    id: 'media',
    label: 'Médias & Inspections',
    icon: <PhotoCameraRoundedIcon />,
    settings: [
      { key: 'cfg_image_max_dimension', label: 'Résolution max photo (pixels)', type: 'int', description: 'Compression côté client — longueur du côté le plus grand en pixels avant upload', placeholder: '1920' },
      { key: 'cfg_image_quality', label: 'Qualité image JPEG/WebP (0–100)', type: 'int', description: 'Taux de compression des photos d\'inspection. 85 = bon compromis qualité/taille', placeholder: '85' },
      { key: 'cfg_inspection_approval_expiry_days', label: 'Expiration lien d\'approbation (jours)', type: 'int', description: 'Combien de jours le lien envoyé au client pour approuver un devis reste valide', placeholder: '7' },
      { key: 'cfg_photo_archive_after_days', label: 'Archivage photos après (jours)', type: 'int', description: 'Délai avant déplacement automatique des photos vers le stockage froid', placeholder: '90' },
    ],
  },
]

// ─── Single setting row ───────────────────────────────────────────────────────

function SettingRow({
  def,
  currentValue,
  onSave,
}: {
  def: SettingDef
  currentValue: string | undefined
  onSave: (key: string, value: string) => Promise<void>
}) {
  const [value, setValue] = useState(currentValue ?? '')
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    setValue(currentValue ?? '')
    setDirty(false)
  }, [currentValue])

  const handleChange = (v: string) => {
    setValue(v)
    setDirty(v !== (currentValue ?? ''))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(def.key, value)
      setDirty(false)
    } finally {
      setSaving(false)
    }
  }

  const inputEl = () => {
    if (def.type === 'bool') {
      const checked = value === 'true' || value === '1' || value === 'yes'
      return (
        <Stack direction="row" alignItems="center" spacing={1.5}>
          <Switch
            checked={checked}
            onChange={e => handleChange(e.target.checked ? 'true' : 'false')}
            size="small"
          />
          <Typography variant="body2" color={checked ? 'success.main' : 'text.secondary'} fontWeight={600}>
            {checked ? 'Activé' : 'Désactivé'}
          </Typography>
        </Stack>
      )
    }

    if (def.type === 'select' && def.options) {
      return (
        <TextField
          select
          size="small"
          value={value}
          onChange={e => handleChange(e.target.value)}
          sx={{ minWidth: 220 }}
        >
          {def.options.map(o => (
            <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
          ))}
        </TextField>
      )
    }

    if (def.type === 'textarea') {
      return (
        <TextField
          size="small"
          multiline
          rows={3}
          value={value}
          onChange={e => handleChange(e.target.value)}
          placeholder={def.placeholder}
          sx={{ minWidth: 320, maxWidth: 480 }}
        />
      )
    }

    return (
      <TextField
        size="small"
        type={def.type === 'int' || def.type === 'float' ? 'number' : 'text'}
        value={value}
        onChange={e => handleChange(e.target.value)}
        placeholder={def.placeholder}
        inputProps={def.type === 'float' ? { step: '0.1' } : def.type === 'int' ? { step: '1' } : {}}
        sx={{ minWidth: 220, maxWidth: 360 }}
      />
    )
  }

  return (
    <Stack
      direction={{ xs: 'column', md: 'row' }}
      alignItems={{ md: 'flex-start' }}
      justifyContent="space-between"
      spacing={2}
      sx={{ py: 2 }}
    >
      <Box flex={1} minWidth={0}>
        <Typography variant="body2" fontWeight={600}>{def.label}</Typography>
        <Typography variant="caption" color="text.secondary" display="block" mt={0.25}>
          {def.description}
        </Typography>
        <Typography variant="caption" color="text.disabled" fontFamily="monospace" display="block" mt={0.25}>
          {def.key}
          {currentValue === undefined && (
            <Typography component="span" variant="caption" color="warning.main" ml={1}>
              · non défini (valeur env par défaut)
            </Typography>
          )}
        </Typography>
      </Box>
      <Stack direction="row" alignItems="flex-start" spacing={1} flexShrink={0}>
        {inputEl()}
        {def.type !== 'bool' && dirty && (
          <Button
            variant="contained"
            size="small"
            startIcon={<SaveRoundedIcon />}
            onClick={handleSave}
            disabled={saving}
            sx={{ height: 40, flexShrink: 0, textTransform: 'none', fontWeight: 700 }}
          >
            {saving ? 'Sauvegarde…' : 'Sauvegarder'}
          </Button>
        )}
        {def.type === 'bool' && (
          <Button
            variant={dirty ? 'contained' : 'outlined'}
            size="small"
            onClick={handleSave}
            disabled={saving || !dirty}
            sx={{ height: 36, flexShrink: 0, textTransform: 'none', fontWeight: 600, opacity: dirty ? 1 : 0 }}
          >
            {saving ? '…' : 'OK'}
          </Button>
        )}
      </Stack>
    </Stack>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function SettingsPage() {
  const qc = useQueryClient()
  const { success, error: toastError } = useToast()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.list(0),
    staleTime: 30_000,
  })

  const settingsMap: Record<string, string> = {}
  for (const item of data?.items ?? []) {
    settingsMap[item.key] = item.value
  }

  const handleSave = async (key: string, value: string) => {
    try {
      await settingsApi.upsert(key, value)
      success(`Paramètre "${key}" enregistré.`)
      qc.invalidateQueries({ queryKey: ['settings'] })
    } catch {
      toastError(`Erreur lors de la sauvegarde de "${key}".`)
      throw new Error('save failed')
    }
  }

  return (
    <Box>
      <PageHeader
        title="Paramètres"
        subtitle="Configuration du garage et des comportements système"
      />

      {isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Impossible de charger les paramètres. Vérifiez votre connexion et vos droits d'accès.
        </Alert>
      )}

      {isLoading && (
        <Box sx={{ py: 4, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">Chargement des paramètres…</Typography>
        </Box>
      )}

      {!isLoading && (
        <Stack spacing={3}>
          {CATALOG.map(section => (
            <Card key={section.id}>
              <CardContent sx={{ p: 0 }}>
                {/* Section header */}
                <Stack
                  direction="row"
                  alignItems="center"
                  spacing={1.5}
                  sx={{ px: 3, py: 2, borderBottom: '1px solid #F1F5F9' }}
                >
                  <Box
                    sx={{
                      width: 36, height: 36, borderRadius: '10px',
                      bgcolor: '#F1F5F9',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0,
                      '& svg': { color: '#334155', fontSize: 18 },
                    }}
                  >
                    {section.icon}
                  </Box>
                  <Box>
                    <Typography variant="subtitle2" fontWeight={700}>{section.label}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {section.settings.length} paramètre{section.settings.length !== 1 ? 's' : ''}
                    </Typography>
                  </Box>
                </Stack>

                {/* Settings rows */}
                <Box sx={{ px: 3 }}>
                  {section.settings.map((def, i) => (
                    <Box key={def.key}>
                      <SettingRow
                        def={def}
                        currentValue={settingsMap[def.key]}
                        onSave={handleSave}
                      />
                      {i < section.settings.length - 1 && (
                        <Divider sx={{ borderColor: '#F8FAFC' }} />
                      )}
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}

      <Box sx={{ mt: 4, p: 2.5, bgcolor: '#F8FAFC', borderRadius: 2, border: '1px solid #E2E8F0' }}>
        <Typography variant="caption" color="text.secondary">
          <strong>Note :</strong> Les paramètres non définis utilisent les valeurs par défaut configurées via les variables d'environnement du serveur.
          Les modifications sont appliquées immédiatement et mises en cache Redis (TTL configurable).
        </Typography>
      </Box>
    </Box>
  )
}
