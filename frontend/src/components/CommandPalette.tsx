/**
 * CommandPalette — Cmd+K / Ctrl+K global navigation palette.
 *
 * Powered by cmdk (headless). Styled entirely with MUI sx props so it inherits
 * the design system. Renders in a portal so it works from any context.
 */
import { useCallback, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Command, useCommandState } from 'cmdk'
import {
  Box,
  Typography,
  InputBase,
  Divider,
} from '@mui/material'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import KeyboardRoundedIcon from '@mui/icons-material/KeyboardRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded'
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded'
import DirectionsCarRoundedIcon from '@mui/icons-material/DirectionsCarRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded'
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import { navSections } from './layout/navConfig'
import { useAuth } from '../contexts/AuthContext'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { customerApi } from '../lib/customerApi'
import { vehiclesApi } from '../lib/vehiclesApi'
import { invoiceApi } from '../lib/invoiceApi'
import { quotationApi } from '../lib/quotationApi'
import { repairOrderApi } from '../lib/repairOrderApi'

// Quick-create actions shown at the top (always visible, highest frequency)
const QUICK_ACTIONS = [
  { label: 'Nouvel ordre de réparation', path: '/repair-orders/new', shortcut: 'N O' },
  { label: 'Nouveau client',             path: '/customers/new',      shortcut: 'N C' },
  { label: 'Nouveau véhicule',           path: '/vehicles/new',       shortcut: 'N V' },
]

// Below this length a query is too broad to fire 5 parallel list requests for —
// wait for a more specific term.
const MIN_SEARCH_LENGTH = 2

interface SearchResultItem {
  key: string
  /** Fed to cmdk's own fuzzy filter — must contain the matched text so the
   * item survives filtering against the current search string. */
  value: string
  path: string
  icon: typeof PeopleRoundedIcon
  primary: string
  secondary?: string
}

/**
 * Renders inside <Command.List> — reads the live search text via cmdk's
 * useCommandState (no need to lift the input into controlled state) and
 * fires one small, permission-gated list query per searchable entity.
 */
function SearchResultsGroup({
  hasPermission,
  go,
}: {
  hasPermission: (p?: string) => boolean
  go: (path: string) => void
}) {
  const rawSearch = useCommandState(state => state.search)
  const search = useDebouncedValue(rawSearch, 250)
  const query = search.trim()
  const enabled = query.length >= MIN_SEARCH_LENGTH

  const customerQuery = useQuery({
    queryKey: ['palette-search', 'customers', query],
    queryFn: () => customerApi.list({ q: query, page_size: 5 }),
    enabled: enabled && hasPermission('customer.read'),
  })
  const vehicleQuery = useQuery({
    queryKey: ['palette-search', 'vehicles', query],
    queryFn: () => vehiclesApi.list({ q: query, page_size: 5 }),
    enabled: enabled && hasPermission('vehicle.read'),
  })
  const invoiceQuery = useQuery({
    queryKey: ['palette-search', 'invoices', query],
    queryFn: () => invoiceApi.list({ search: query, page_size: 5 }),
    enabled: enabled && hasPermission('invoice.read'),
  })
  const quotationQuery = useQuery({
    queryKey: ['palette-search', 'quotations', query],
    queryFn: () => quotationApi.list({ search: query, page_size: 5 }),
    enabled: enabled && hasPermission('quotation.read'),
  })
  const repairOrderQuery = useQuery({
    queryKey: ['palette-search', 'repair-orders', query],
    queryFn: () => repairOrderApi.list({ search: query, page_size: 5 }),
    enabled: enabled && hasPermission('repair_order.read'),
  })

  if (!enabled) return null

  const results: SearchResultItem[] = [
    ...(customerQuery.data?.items ?? []).map(c => ({
      key: `customer-${c.id}`,
      value: `${c.full_name} ${c.company_name ?? ''}`,
      path: `/customers/${c.id}`,
      icon: PeopleRoundedIcon,
      primary: c.full_name,
      secondary: c.company_name ?? c.phone_e164 ?? undefined,
    })),
    ...(vehicleQuery.data?.items ?? []).map(v => ({
      key: `vehicle-${v.id}`,
      value: `${v.registration ?? ''} ${v.vin ?? ''} ${v.make} ${v.model}`,
      path: `/vehicles/${v.id}`,
      icon: DirectionsCarRoundedIcon,
      primary: v.registration ?? v.vin ?? `${v.make} ${v.model}`,
      secondary: [v.make, v.model, v.customer_name].filter(Boolean).join(' · ') || undefined,
    })),
    ...(invoiceQuery.data?.items ?? []).map(i => ({
      key: `invoice-${i.id}`,
      value: `${i.doc_number ?? ''} ${i.customer_name ?? ''}`,
      path: `/invoices/${i.public_id}`,
      icon: ReceiptRoundedIcon,
      primary: i.doc_number ?? `Facture #${i.id}`,
      secondary: i.customer_name ?? undefined,
    })),
    ...(quotationQuery.data?.items ?? []).map(q => ({
      key: `quotation-${q.id}`,
      value: `${q.doc_number ?? ''} ${q.customer_name ?? ''}`,
      path: `/quotations/${q.public_id}`,
      icon: DescriptionRoundedIcon,
      primary: q.doc_number ?? `Devis #${q.id}`,
      secondary: q.customer_name ?? undefined,
    })),
    ...(repairOrderQuery.data?.items ?? []).map(ro => ({
      key: `ro-${ro.id}`,
      value: `${ro.customer_name ?? ''} ${ro.description ?? ''}`,
      path: `/repair-orders/${ro.id}`,
      icon: BuildRoundedIcon,
      primary: ro.customer_name ?? `Ordre de réparation #${ro.int_id}`,
      secondary: ro.description ?? undefined,
    })),
  ]

  if (results.length === 0) return null

  return (
    <>
      <Command.Separator />
      <Command.Group heading="Résultats">
        {results.map(r => {
          const Icon = r.icon
          return (
            <Command.Item key={r.key} value={r.value} onSelect={() => go(r.path)}>
              <Box
                sx={{
                  width: 28, height: 28,
                  borderRadius: '7px',
                  bgcolor: 'action.hover',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Icon sx={{ color: 'text.secondary', fontSize: 16 }} />
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2" fontWeight={500} noWrap>
                  {r.primary}
                </Typography>
                {r.secondary && (
                  <Typography variant="caption" color="text.disabled" noWrap sx={{ display: 'block' }}>
                    {r.secondary}
                  </Typography>
                )}
              </Box>
              <ArrowForwardRoundedIcon sx={{ color: 'text.disabled', fontSize: 15, flexShrink: 0 }} />
            </Command.Item>
          )
        })}
      </Command.Group>
    </>
  )
}

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate()
  const { user } = useAuth()
  const inputRef = useRef<HTMLInputElement>(null)

  // Focus input when opened
  useEffect(() => {
    if (open) {
      // Small delay to let the portal mount
      const id = setTimeout(() => inputRef.current?.focus(), 30)
      return () => clearTimeout(id)
    }
  }, [open])

  const go = useCallback((path: string) => {
    navigate(path)
    onClose()
  }, [navigate, onClose])

  if (!open) return null

  const hasPermission = (p?: string) => !p || (user?.permissions.includes(p) ?? false)

  return createPortal(
    <Box
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: 1400,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        pt: { xs: '10vh', sm: '14vh' },
        px: 2,
        bgcolor: 'rgba(15, 23, 42, 0.5)',
        backdropFilter: 'blur(4px)',
        WebkitBackdropFilter: 'blur(4px)',
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <Box
        sx={{
          width: '100%',
          maxWidth: 620,
          bgcolor: 'background.paper',
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider',
          boxShadow: '0 25px 50px -12px rgba(0,0,0,0.22), 0 0 0 1px rgba(0,0,0,0.04)',
          overflow: 'hidden',
          // cmdk root styles
          '& [cmdk-root]': { outline: 'none' },
          '& [cmdk-list]': {
            maxHeight: 400,
            overflowY: 'auto',
            overscrollBehavior: 'contain',
            '&::-webkit-scrollbar': { width: 5 },
            '&::-webkit-scrollbar-thumb': { bgcolor: 'divider', borderRadius: 999 },
          },
          '& [cmdk-group-heading]': {
            px: 2,
            py: 0.75,
            fontSize: '0.6875rem',
            fontWeight: 600,
            color: 'text.disabled',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            userSelect: 'none',
          },
          '& [cmdk-item]': {
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            px: 2,
            py: 1.125,
            cursor: 'pointer',
            borderRadius: 0,
            outline: 'none',
            transition: 'background-color 0.1s',
            '&[data-selected="true"]': {
              bgcolor: 'rgba(245,158,11,0.12)',
            },
            '&:active': { bgcolor: 'rgba(245,158,11,0.2)' },
          },
          '& [cmdk-empty]': {
            px: 2,
            py: 4,
            textAlign: 'center',
            color: 'text.disabled',
            fontSize: '0.875rem',
          },
          '& [cmdk-separator]': {
            height: 1,
            bgcolor: 'divider',
            mx: 0,
            my: 0.5,
          },
        }}
      >
        <Command label="Palette de navigation" shouldFilter>
          {/* ── Search input ── */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              px: 2,
              py: 1.25,
              gap: 1.5,
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            <SearchRoundedIcon sx={{ color: 'text.disabled', fontSize: 20, flexShrink: 0 }} />
            <Command.Input asChild>
              <InputBase
                inputRef={inputRef}
                placeholder="Rechercher un client, un véhicule, une facture…"
                sx={{
                  flex: 1,
                  fontSize: '0.9375rem',
                  '& input': { p: 0 },
                  '& input::placeholder': { color: 'text.disabled' },
                }}
                onKeyDown={e => { if (e.key === 'Escape') onClose() }}
              />
            </Command.Input>
            <Box
              sx={{
                display: { xs: 'none', sm: 'flex' },
                alignItems: 'center',
                gap: 0.5,
                px: 0.75,
                py: 0.375,
                bgcolor: 'action.hover',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: '5px',
                flexShrink: 0,
              }}
            >
              <KeyboardRoundedIcon sx={{ fontSize: 13, color: 'text.disabled' }} />
              <Typography variant="caption" color="text.disabled" fontSize="0.6875rem">
                Esc
              </Typography>
            </Box>
          </Box>

          <Command.List>
            <Command.Empty>Aucun résultat pour cette recherche.</Command.Empty>

            {/* ── Quick actions ── */}
            <Command.Group heading="Actions rapides">
              {QUICK_ACTIONS.map(action => (
                <Command.Item
                  key={action.path}
                  value={action.label}
                  onSelect={() => go(action.path)}
                >
                  <Box
                    sx={{
                      width: 28, height: 28,
                      borderRadius: '7px',
                      bgcolor: 'action.hover',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <AddRoundedIcon sx={{ color: 'text.primary', fontSize: 16 }} />
                  </Box>
                  <Typography variant="body2" fontWeight={500} flex={1}>
                    {action.label}
                  </Typography>
                  <Typography variant="caption" color="text.disabled" fontSize="0.6875rem"
                    sx={{ display: { xs: 'none', sm: 'block' } }}>
                    {action.shortcut}
                  </Typography>
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Separator />

            {/* ── Nav sections ── */}
            {navSections.map(section => {
              const visibleItems = section.items.filter(item => hasPermission(item.permission))
              if (visibleItems.length === 0) return null
              return (
                <Command.Group key={section.label} heading={section.label}>
                  {visibleItems.map(item => {
                    const Icon = item.icon
                    return (
                      <Command.Item
                        key={item.path}
                        value={`${section.label} ${item.label}`}
                        onSelect={() => go(item.path)}
                      >
                        <Box
                          sx={{
                            width: 28, height: 28,
                            borderRadius: '7px',
                            bgcolor: 'action.hover',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            flexShrink: 0,
                          }}
                        >
                          <Icon sx={{ color: 'text.secondary', fontSize: 16 }} />
                        </Box>
                        <Typography variant="body2" fontWeight={500} flex={1}>
                          {item.label}
                        </Typography>
                        <ArrowForwardRoundedIcon
                          sx={{ color: 'text.disabled', fontSize: 15, flexShrink: 0 }}
                        />
                      </Command.Item>
                    )
                  })}
                </Command.Group>
              )
            })}

            <SearchResultsGroup hasPermission={hasPermission} go={go} />
          </Command.List>

          {/* ── Footer hint ── */}
          <Divider />
          <Box
            sx={{
              px: 2,
              py: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 2,
            }}
          >
            {[
              { keys: ['↑', '↓'], label: 'naviguer' },
              { keys: ['↵'], label: 'ouvrir' },
              { keys: ['Esc'], label: 'fermer' },
            ].map(hint => (
              <Box key={hint.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {hint.keys.map(k => (
                  <Box
                    key={k}
                    component="kbd"
                    sx={{
                      px: 0.625, py: 0.25,
                      bgcolor: 'action.hover',
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: '4px',
                      fontSize: '0.6875rem',
                      fontFamily: 'inherit',
                      color: 'text.secondary',
                      lineHeight: 1.4,
                    }}
                  >
                    {k}
                  </Box>
                ))}
                <Typography variant="caption" color="text.disabled" fontSize="0.6875rem">
                  {hint.label}
                </Typography>
              </Box>
            ))}
          </Box>
        </Command>
      </Box>
    </Box>,
    document.body
  )
}

export default CommandPalette
