/**
 * CommandPalette — Cmd+K / Ctrl+K global navigation palette.
 *
 * Powered by cmdk (headless). Styled entirely with MUI sx props so it inherits
 * the design system. Renders in a portal so it works from any context.
 */
import { useCallback, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { Command } from 'cmdk'
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
import { navSections } from './layout/navConfig'
import { useAuth } from '../contexts/AuthContext'

// Quick-create actions shown at the top (always visible, highest frequency)
const QUICK_ACTIONS = [
  { label: 'Nouvel ordre de réparation', path: '/repair-orders/new', shortcut: 'N O' },
  { label: 'Nouveau client',             path: '/customers/new',      shortcut: 'N C' },
  { label: 'Nouveau véhicule',           path: '/vehicles/new',       shortcut: 'N V' },
]

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
          border: '1px solid #E2E8F0',
          boxShadow: '0 25px 50px -12px rgba(0,0,0,0.22), 0 0 0 1px rgba(0,0,0,0.04)',
          overflow: 'hidden',
          // cmdk root styles
          '& [cmdk-root]': { outline: 'none' },
          '& [cmdk-list]': {
            maxHeight: 400,
            overflowY: 'auto',
            overscrollBehavior: 'contain',
            '&::-webkit-scrollbar': { width: 5 },
            '&::-webkit-scrollbar-thumb': { bgcolor: '#E2E8F0', borderRadius: 999 },
          },
          '& [cmdk-group-heading]': {
            px: 2,
            py: 0.75,
            fontSize: '0.6875rem',
            fontWeight: 600,
            color: '#94A3B8',
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
              bgcolor: '#EFF6FF',
            },
            '&:active': { bgcolor: '#DBEAFE' },
          },
          '& [cmdk-empty]': {
            px: 2,
            py: 4,
            textAlign: 'center',
            color: '#94A3B8',
            fontSize: '0.875rem',
          },
          '& [cmdk-separator]': {
            height: 1,
            bgcolor: '#F1F5F9',
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
              borderBottom: '1px solid #F1F5F9',
            }}
          >
            <SearchRoundedIcon sx={{ color: 'text.disabled', fontSize: 20, flexShrink: 0 }} />
            <Command.Input asChild>
              <InputBase
                inputRef={inputRef}
                placeholder="Rechercher une page, une action…"
                sx={{
                  flex: 1,
                  fontSize: '0.9375rem',
                  '& input': { p: 0 },
                  '& input::placeholder': { color: '#94A3B8' },
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
                bgcolor: '#F8FAFC',
                border: '1px solid #E2E8F0',
                borderRadius: '5px',
                flexShrink: 0,
              }}
            >
              <KeyboardRoundedIcon sx={{ fontSize: 13, color: '#94A3B8' }} />
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
                      bgcolor: '#EFF6FF',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <AddRoundedIcon sx={{ color: '#2563EB', fontSize: 16 }} />
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
                            bgcolor: '#F8FAFC',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            flexShrink: 0,
                          }}
                        >
                          <Icon sx={{ color: '#64748B', fontSize: 16 }} />
                        </Box>
                        <Typography variant="body2" fontWeight={500} flex={1}>
                          {item.label}
                        </Typography>
                        <ArrowForwardRoundedIcon
                          sx={{ color: '#CBD5E1', fontSize: 15, flexShrink: 0 }}
                        />
                      </Command.Item>
                    )
                  })}
                </Command.Group>
              )
            })}
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
                      bgcolor: '#F8FAFC',
                      border: '1px solid #E2E8F0',
                      borderRadius: '4px',
                      fontSize: '0.6875rem',
                      fontFamily: 'inherit',
                      color: '#64748B',
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
