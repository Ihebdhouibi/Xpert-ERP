import { createTheme, type Theme } from '@mui/material/styles'

export type ThemeMode = 'light' | 'dark'
export type ThemePreference = ThemeMode | 'system'

// Module augmentation so `theme.custom.sidebar` (mode-aware sidebar colors)
// is available and typed via the normal useTheme() hook, instead of a
// separate hardcoded import that can't react to the current mode.
declare module '@mui/material/styles' {
  interface Theme {
    custom: { sidebar: SidebarTokens }
  }
  interface ThemeOptions {
    custom?: { sidebar?: SidebarTokens }
  }
}

// Sidebar drawer widths are mode-independent — kept as a plain export so
// layout code (AppShell, Sidebar) doesn't need the full theme for sizing.
export const SIDEBAR_METRICS = {
  width: 260,
  collapsedWidth: 64,
}

export interface SidebarTokens {
  bg: string
  hover: string
  activeBg: string
  activeBorder: string
  text: string
  activeText: string
  sectionLabel: string
  iconColor: string
  activeIconColor: string
  divider: string
}

// Everything mode-dependent that used to be a literal hex string scattered
// across styleOverrides lives here, one row per mode, so the two palettes
// stay visually parallel and nothing gets missed when either one changes.
interface ThemeTokens {
  primary: { main: string; dark: string; light: string; contrastText: string }
  secondary: { main: string; dark: string; light: string; contrastText: string }
  error: { main: string; dark: string; light: string }
  warning: { main: string; dark: string; light: string }
  success: { main: string; dark: string; light: string }
  info: { main: string; dark: string; light: string }
  background: { default: string; paper: string }
  text: { primary: string; secondary: string; disabled: string }
  divider: string
  scrollbarThumb: string
  scrollbarThumbHover: string
  buttonGradient: [string, string]
  buttonGradientHover: [string, string]
  outlinedBorder: string
  outlinedHoverBorder: string
  outlinedHoverBg: string
  cardBorder: string
  tableHeadBg: string
  tableHeadColor: string
  tableRowHoverBg: string
  tableCellBorder: string
  chip: {
    success: { bg: string; text: string }
    error: { bg: string; text: string }
    warning: { bg: string; text: string }
    info: { bg: string; text: string }
  }
  textFieldBorder: string
  textFieldHoverBorder: string
  textFieldBg: string
  alert: {
    success: { bg: string; color: string }
    error: { bg: string; color: string }
    warning: { bg: string; color: string }
    info: { bg: string; color: string }
  }
  tooltipBg: string
  tabColor: string
  tabSelectedColor: string
  skeletonBg: string
  breadcrumbSeparator: string
  sidebar: SidebarTokens
}

const light: ThemeTokens = {
  primary: { main: '#1E293B', dark: '#0F172A', light: '#475569', contrastText: '#ffffff' },
  secondary: { main: '#F59E0B', dark: '#D97706', light: '#FCD34D', contrastText: '#1C1917' },
  error: { main: '#EF4444', dark: '#DC2626', light: '#FCA5A5' },
  warning: { main: '#F59E0B', dark: '#D97706', light: '#FDE68A' },
  success: { main: '#10B981', dark: '#059669', light: '#6EE7B7' },
  info: { main: '#475569', dark: '#1E293B', light: '#94A3B8' },
  background: { default: '#F1F5F9', paper: '#FFFFFF' },
  text: { primary: '#0F172A', secondary: '#64748B', disabled: '#94A3B8' },
  divider: '#E2E8F0',
  scrollbarThumb: '#CBD5E1',
  scrollbarThumbHover: '#94A3B8',
  buttonGradient: ['#1E293B', '#0F172A'],
  buttonGradientHover: ['#0F172A', '#020617'],
  outlinedBorder: '#CBD5E1',
  outlinedHoverBorder: '#1E293B',
  outlinedHoverBg: '#F1F5F9',
  cardBorder: '#E2E8F0',
  tableHeadBg: '#F8FAFC',
  tableHeadColor: '#64748B',
  tableRowHoverBg: '#F9FAFB',
  tableCellBorder: '#F1F5F9',
  chip: {
    success: { bg: '#DCFCE7', text: '#15803D' },
    error: { bg: '#FEE2E2', text: '#B91C1C' },
    warning: { bg: '#FEF3C7', text: '#92400E' },
    info: { bg: '#E2E8F0', text: '#1E293B' },
  },
  textFieldBorder: '#E2E8F0',
  textFieldHoverBorder: '#CBD5E1',
  textFieldBg: '#FFFFFF',
  alert: {
    success: { bg: '#F0FDF4', color: '#166534' },
    error: { bg: '#FEF2F2', color: '#991B1B' },
    warning: { bg: '#FFFBEB', color: '#92400E' },
    info: { bg: '#F1F5F9', color: '#1E293B' },
  },
  tooltipBg: '#1E293B',
  tabColor: '#64748B',
  tabSelectedColor: '#1E293B',
  skeletonBg: '#F1F5F9',
  breadcrumbSeparator: '#CBD5E1',
  sidebar: {
    bg: '#FFFFFF',
    hover: 'rgba(15,23,42,0.05)',
    activeBg: 'rgba(245,158,11,0.14)',
    activeBorder: '#F59E0B',
    text: '#334155',
    activeText: '#0F172A',
    sectionLabel: '#64748B',
    iconColor: '#64748B',
    activeIconColor: '#B45309',
    divider: '#E2E8F0',
  },
}

// Dark mode phase 1 (see UX plan WS3): the shell + shared components below
// use these tokens and render correctly. Page-level one-off hex colors
// outside this file are a tracked follow-up, not silently broken — most
// pages read text/background through theme.palette already and only their
// bespoke accent colors (status dashboards, etc.) won't adapt yet.
const dark: ThemeTokens = {
  primary: { main: '#475569', dark: '#334155', light: '#64748B', contrastText: '#F8FAFC' },
  secondary: { main: '#F59E0B', dark: '#D97706', light: '#FCD34D', contrastText: '#1C1917' },
  error: { main: '#F87171', dark: '#EF4444', light: '#FCA5A5' },
  warning: { main: '#FBBF24', dark: '#F59E0B', light: '#FDE68A' },
  success: { main: '#34D399', dark: '#10B981', light: '#6EE7B7' },
  info: { main: '#94A3B8', dark: '#64748B', light: '#CBD5E1' },
  background: { default: '#0B1120', paper: '#0F172A' },
  text: { primary: '#F1F5F9', secondary: '#94A3B8', disabled: '#64748B' },
  divider: '#1E293B',
  scrollbarThumb: '#334155',
  scrollbarThumbHover: '#475569',
  buttonGradient: ['#334155', '#1E293B'],
  buttonGradientHover: ['#475569', '#1E293B'],
  outlinedBorder: '#334155',
  outlinedHoverBorder: '#64748B',
  outlinedHoverBg: 'rgba(148,163,184,0.08)',
  cardBorder: '#1E293B',
  tableHeadBg: '#131B2C',
  tableHeadColor: '#94A3B8',
  tableRowHoverBg: 'rgba(148,163,184,0.06)',
  tableCellBorder: '#1E293B',
  chip: {
    success: { bg: 'rgba(16,185,129,0.16)', text: '#34D399' },
    error: { bg: 'rgba(239,68,68,0.16)', text: '#F87171' },
    warning: { bg: 'rgba(245,158,11,0.16)', text: '#FBBF24' },
    info: { bg: 'rgba(148,163,184,0.16)', text: '#CBD5E1' },
  },
  textFieldBorder: '#334155',
  textFieldHoverBorder: '#475569',
  textFieldBg: '#0F172A',
  alert: {
    success: { bg: 'rgba(16,185,129,0.12)', color: '#34D399' },
    error: { bg: 'rgba(239,68,68,0.12)', color: '#F87171' },
    warning: { bg: 'rgba(245,158,11,0.12)', color: '#FBBF24' },
    info: { bg: 'rgba(148,163,184,0.12)', color: '#E2E8F0' },
  },
  tooltipBg: '#334155',
  tabColor: '#94A3B8',
  tabSelectedColor: '#F1F5F9',
  skeletonBg: '#1E293B',
  breadcrumbSeparator: '#475569',
  sidebar: {
    bg: '#0F172A',
    hover: 'rgba(148,163,184,0.08)',
    activeBg: 'rgba(245,158,11,0.16)',
    activeBorder: '#F59E0B',
    text: '#CBD5E1',
    activeText: '#F1F5F9',
    sectionLabel: '#94A3B8',
    iconColor: '#94A3B8',
    activeIconColor: '#FBBF24',
    divider: '#1E293B',
  },
}

const TOKENS: Record<ThemeMode, ThemeTokens> = { light, dark }

export function getTheme(mode: ThemeMode): Theme {
  const t = TOKENS[mode]

  return createTheme({
    palette: {
      mode,
      primary: t.primary,
      secondary: t.secondary,
      error: t.error,
      warning: t.warning,
      success: t.success,
      info: t.info,
      background: t.background,
      text: t.text,
      divider: t.divider,
    },

    custom: {
      sidebar: t.sidebar,
    },

    typography: {
      // Inter for UI, JetBrains Mono for technical data (plates, codes, amounts)
      fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
      h1: { fontWeight: 800, letterSpacing: '-0.03em' },
      h2: { fontWeight: 700, letterSpacing: '-0.025em' },
      h3: { fontWeight: 700, letterSpacing: '-0.02em' },
      h4: { fontWeight: 700, letterSpacing: '-0.015em' },
      h5: { fontWeight: 600, letterSpacing: '-0.01em' },
      h6: { fontWeight: 600, letterSpacing: '-0.005em' },
      subtitle1: { fontWeight: 500, letterSpacing: '-0.005em' },
      subtitle2: { fontWeight: 500 },
      body1: { fontSize: '0.9375rem', lineHeight: 1.6 },
      body2: { fontSize: '0.875rem',  lineHeight: 1.55 },
      caption: { fontSize: '0.75rem', lineHeight: 1.5 },
      button: {
        fontWeight: 600,
        textTransform: 'none',
        letterSpacing: '0',
        fontSize: '0.875rem',
      },
    },

    // 8px base radius — enterprise feel, not mobile softness
    shape: { borderRadius: 8 },

    // Shadows reserved for elevated surfaces only (modals, dropdowns, overlays)
    // Everything else uses 1px borders — Stripe/Linear approach
    shadows: [
      'none',
      '0 1px 2px 0 rgb(0 0 0 / 0.04)',
      '0 1px 3px 0 rgb(0 0 0 / 0.08), 0 1px 2px -1px rgb(0 0 0 / 0.06)',
      '0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05)',
      '0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.04)',
      '0 20px 25px -5px rgb(0 0 0 / 0.08), 0 8px 10px -6px rgb(0 0 0 / 0.04)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
      '0 25px 50px -12px rgb(0 0 0 / 0.18)',
    ],

    components: {
      MuiCssBaseline: {
        styleOverrides: {
          html: { scrollBehavior: 'smooth' },
          body: {
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
          },
          '*': { boxSizing: 'border-box' },
          '*::-webkit-scrollbar': { width: 6, height: 6 },
          '*::-webkit-scrollbar-track': { background: 'transparent' },
          '*::-webkit-scrollbar-thumb': { background: t.scrollbarThumb, borderRadius: 3 },
          '*::-webkit-scrollbar-thumb:hover': { background: t.scrollbarThumbHover },
          // JetBrains Mono utility class — apply via sx={{ fontFamily: 'mono' }}
          '.font-mono': {
            fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',
          },
          // A single global focus ring so every native-focusable element is
          // keyboard-visible without per-component work. Only shows for
          // keyboard focus (:focus-visible), not on a mouse click.
          '*:focus-visible': {
            outline: `2px solid ${t.secondary.main}`,
            outlineOffset: 2,
          },
        },
      },

      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: {
            borderRadius: 8,
            padding: '8px 16px',
            fontWeight: 600,
            transition: 'all 0.15s ease',
          },
          sizeSmall: { padding: '5px 12px', fontSize: '0.8125rem' },
          sizeLarge: { padding: '11px 24px', fontSize: '0.9375rem' },
          containedPrimary: {
            background: `linear-gradient(135deg, ${t.buttonGradient[0]} 0%, ${t.buttonGradient[1]} 100%)`,
            '&:hover': {
              background: `linear-gradient(135deg, ${t.buttonGradientHover[0]} 0%, ${t.buttonGradientHover[1]} 100%)`,
              boxShadow: '0 4px 12px rgba(245,158,11,0.25)',
            },
            // Without this, the gradient background above still applies even when
            // disabled (it isn't scoped to :not(.Mui-disabled)), which overrides
            // MUI's own disabled-background dimming — leaving MUI's near-invisible
            // translucent-black disabled text on top of our dark background.
            '&.Mui-disabled': {
              background: `linear-gradient(135deg, ${t.buttonGradient[0]} 0%, ${t.buttonGradient[1]} 100%)`,
              color: t.primary.contrastText,
              opacity: 0.5,
            },
          },
          outlinedPrimary: {
            borderColor: t.outlinedBorder,
            '&:hover': { borderColor: t.outlinedHoverBorder, backgroundColor: t.outlinedHoverBg },
          },
        },
      },

      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            // Border-based elevation — no shadow on resting cards
            border: `1px solid ${t.cardBorder}`,
            borderRadius: 8, // 12 → 8: enterprise feel, not mobile softness
            backgroundImage: 'none',
            boxShadow: 'none',
          },
        },
      },

      MuiPaper: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: { backgroundImage: 'none' },
          outlined: { borderColor: t.cardBorder },
          // Keep very subtle shadows for elevated contexts (drawers, overlays)
          elevation1: { boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)' },
          elevation2: { boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.06), 0 2px 4px -2px rgb(0 0 0 / 0.04)' },
          elevation3: { boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.07), 0 4px 6px -4px rgb(0 0 0 / 0.04)' },
        },
      },

      MuiTableHead: {
        styleOverrides: {
          root: {
            '& .MuiTableCell-head': {
              backgroundColor: t.tableHeadBg,
              color: t.tableHeadColor,          // lighter — not shouting
              fontWeight: 500,           // medium weight
              fontSize: '0.75rem',       // slightly smaller
              textTransform: 'none',     // sentence case — not uppercase
              letterSpacing: '0',        // no extra spacing
              borderBottom: `1px solid ${t.divider}`,
              padding: '10px 16px',
            },
          },
        },
      },

      MuiTableRow: {
        styleOverrides: {
          root: {
            '&:last-child td, &:last-child th': { borderBottom: 0 },
            '&.MuiTableRow-hover:hover': {
              // Barely-there hover — signals interactivity without screaming
              backgroundColor: t.tableRowHoverBg,
              cursor: 'pointer',
            },
          },
        },
      },

      MuiTableCell: {
        styleOverrides: {
          root: {
            borderColor: t.tableCellBorder,
            fontSize: '0.875rem',
            padding: '12px 16px',
            color: t.text.primary,
          },
        },
      },

      MuiTablePagination: {
        styleOverrides: {
          root: { fontSize: '0.8125rem', color: t.text.secondary },
          selectLabel: { fontSize: '0.8125rem' },
          displayedRows: { fontSize: '0.8125rem' },
        },
      },

      MuiChip: {
        styleOverrides: {
          root: {
            fontWeight: 500,
            fontSize: '0.75rem',
            borderRadius: 6,
          },
          sizeSmall: {
            height: 22,
            fontSize: '0.6875rem',
            '& .MuiChip-label': { paddingLeft: 8, paddingRight: 8 },
          },
          colorSuccess: {
            backgroundColor: t.chip.success.bg,
            color: t.chip.success.text,
            '& .MuiChip-icon': { color: t.chip.success.text },
          },
          colorError: {
            backgroundColor: t.chip.error.bg,
            color: t.chip.error.text,
            '& .MuiChip-icon': { color: t.chip.error.text },
          },
          colorWarning: {
            backgroundColor: t.chip.warning.bg,
            color: t.chip.warning.text,
            '& .MuiChip-icon': { color: t.chip.warning.text },
          },
          colorInfo: {
            backgroundColor: t.chip.info.bg,
            color: t.chip.info.text,
            '& .MuiChip-icon': { color: t.chip.info.text },
          },
          colorPrimary: {
            backgroundColor: t.chip.info.bg,
            color: t.chip.info.text,
          },
        },
      },

      MuiTextField: {
        defaultProps: { size: 'small' },
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              borderRadius: 8,
              backgroundColor: t.textFieldBg,
              fontSize: '0.875rem',
              '& fieldset': { borderColor: t.textFieldBorder, transition: 'border-color 0.15s' },
              '&:hover fieldset': { borderColor: t.textFieldHoverBorder },
              '&.Mui-focused fieldset': { borderColor: t.secondary.main, borderWidth: 2 },
            },
            '& .MuiInputLabel-root': { fontSize: '0.875rem' },
          },
        },
      },

      MuiSelect: {
        styleOverrides: {
          outlined: { fontSize: '0.875rem' },
        },
      },

      MuiInputBase: {
        styleOverrides: {
          root: { fontSize: '0.875rem' },
          sizeSmall: { fontSize: '0.875rem' },
        },
      },

      MuiDialog: {
        styleOverrides: {
          paper: {
            // Dialogs keep 12px radius — they're elevated surfaces, can be softer
            borderRadius: 12,
            boxShadow: '0 25px 50px -12px rgb(0 0 0 / 0.22)',
          },
        },
      },

      MuiDialogTitle: {
        styleOverrides: {
          root: {
            fontSize: '1.0625rem',
            fontWeight: 700,
            padding: '20px 24px 12px',
            letterSpacing: '-0.01em',
          },
        },
      },

      MuiDialogContent: {
        styleOverrides: {
          root: { padding: '8px 24px 16px' },
        },
      },

      MuiDialogActions: {
        styleOverrides: {
          root: { padding: '12px 24px 20px', gap: 8 },
        },
      },

      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: 8, fontWeight: 500, fontSize: '0.875rem' },
          standardSuccess: { backgroundColor: t.alert.success.bg, color: t.alert.success.color },
          standardError:   { backgroundColor: t.alert.error.bg, color: t.alert.error.color },
          standardWarning: { backgroundColor: t.alert.warning.bg, color: t.alert.warning.color },
          standardInfo:    { backgroundColor: t.alert.info.bg, color: t.alert.info.color },
        },
      },

      MuiSnackbar: {
        defaultProps: {
          anchorOrigin: { vertical: 'bottom', horizontal: 'right' },
          autoHideDuration: 4000,
        },
      },

      MuiTooltip: {
        defaultProps: { arrow: true },
        styleOverrides: {
          tooltip: {
            borderRadius: 6,
            fontSize: '0.75rem',
            fontWeight: 500,
            backgroundColor: t.tooltipBg,
            padding: '5px 10px',
          },
          arrow: { color: t.tooltipBg },
        },
      },

      MuiAppBar: {
        styleOverrides: {
          root: { backgroundImage: 'none' },
        },
      },

      MuiToolbar: {
        styleOverrides: {
          regular: { minHeight: 64 },
        },
      },

      MuiDivider: {
        styleOverrides: {
          root: { borderColor: t.divider },
        },
      },

      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            transition: 'all 0.15s ease',
          },
        },
      },

      MuiAvatar: {
        styleOverrides: {
          root: { fontWeight: 700, fontSize: '0.875rem' },
        },
      },

      MuiTabs: {
        styleOverrides: {
          indicator: { height: 3, borderRadius: '3px 3px 0 0', backgroundColor: t.secondary.main },
          root: { borderBottom: `1px solid ${t.divider}` },
        },
      },

      MuiTab: {
        styleOverrides: {
          root: {
            fontWeight: 600,
            fontSize: '0.875rem',
            textTransform: 'none',
            minWidth: 0,
            padding: '10px 16px',
            color: t.tabColor,
            '&.Mui-selected': { color: t.tabSelectedColor },
          },
        },
      },

      MuiLinearProgress: {
        styleOverrides: {
          root: { borderRadius: 999, height: 6 },
        },
      },

      MuiBadge: {
        styleOverrides: {
          badge: { fontWeight: 700, fontSize: '0.6875rem', minWidth: 18, height: 18 },
        },
      },

      MuiSkeleton: {
        defaultProps: { animation: 'wave' },
        styleOverrides: {
          root: { backgroundColor: t.skeletonBg, borderRadius: 6 },
        },
      },

      MuiIconButton: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            transition: 'all 0.15s ease',
          },
          sizeSmall: { padding: 6 },
        },
      },

      MuiBreadcrumbs: {
        styleOverrides: {
          li: { fontSize: '0.8125rem' },
          separator: { color: t.breadcrumbSeparator },
        },
      },

      MuiLink: {
        styleOverrides: {
          root: { textDecoration: 'none', '&:hover': { textDecoration: 'underline' } },
        },
      },
    },
  })
}

// Kept for any leftover direct `import { theme }` usage — resolves to the
// light theme. Prefer `useTheme()` (mode-aware, via ThemeModeProvider) in
// new code.
export const theme = getTheme('light')
