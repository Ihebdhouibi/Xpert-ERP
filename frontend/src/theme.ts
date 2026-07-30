import { createTheme } from '@mui/material/styles'

export const sidebarTokens = {
  width: 260,
  collapsedWidth: 64,
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
}

export const theme = createTheme({
  palette: {
    primary: {
      main: '#1E293B',
      dark: '#0F172A',
      light: '#475569',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#F59E0B',
      dark: '#D97706',
      light: '#FCD34D',
      contrastText: '#1C1917',
    },
    error:   { main: '#EF4444', dark: '#DC2626', light: '#FCA5A5' },
    warning: { main: '#F59E0B', dark: '#D97706', light: '#FDE68A' },
    success: { main: '#10B981', dark: '#059669', light: '#6EE7B7' },
    info:    { main: '#475569', dark: '#1E293B', light: '#94A3B8' },
    background: {
      default: '#F1F5F9',
      paper:   '#FFFFFF',
    },
    text: {
      primary:   '#0F172A',
      secondary: '#64748B',
      disabled:  '#94A3B8',
    },
    divider: '#E2E8F0',
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
        '*::-webkit-scrollbar-thumb': { background: '#CBD5E1', borderRadius: 3 },
        '*::-webkit-scrollbar-thumb:hover': { background: '#94A3B8' },
        // JetBrains Mono utility class — apply via sx={{ fontFamily: 'mono' }}
        '.font-mono': {
          fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',
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
          background: 'linear-gradient(135deg, #1E293B 0%, #0F172A 100%)',
          '&:hover': {
            background: 'linear-gradient(135deg, #0F172A 0%, #020617 100%)',
            boxShadow: '0 4px 12px rgba(245,158,11,0.25)',
          },
        },
        outlinedPrimary: {
          borderColor: '#CBD5E1',
          '&:hover': { borderColor: '#1E293B', backgroundColor: '#F1F5F9' },
        },
      },
    },

    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          // Border-based elevation — no shadow on resting cards
          border: '1px solid #E2E8F0',
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
        outlined: { borderColor: '#E2E8F0' },
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
            backgroundColor: '#F8FAFC',
            color: '#64748B',          // lighter — not shouting
            fontWeight: 500,           // medium weight
            fontSize: '0.75rem',       // slightly smaller
            textTransform: 'none',     // sentence case — not uppercase
            letterSpacing: '0',        // no extra spacing
            borderBottom: '1px solid #E2E8F0',
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
            backgroundColor: '#F9FAFB',
            cursor: 'pointer',
          },
        },
      },
    },

    MuiTableCell: {
      styleOverrides: {
        root: {
          borderColor: '#F1F5F9',
          fontSize: '0.875rem',
          padding: '12px 16px',
          color: '#0F172A',
        },
      },
    },

    MuiTablePagination: {
      styleOverrides: {
        root: { fontSize: '0.8125rem', color: '#64748B' },
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
          backgroundColor: '#DCFCE7',
          color: '#15803D',
          '& .MuiChip-icon': { color: '#15803D' },
        },
        colorError: {
          backgroundColor: '#FEE2E2',
          color: '#B91C1C',
          '& .MuiChip-icon': { color: '#B91C1C' },
        },
        colorWarning: {
          backgroundColor: '#FEF3C7',
          color: '#92400E',
          '& .MuiChip-icon': { color: '#92400E' },
        },
        colorInfo: {
          backgroundColor: '#E2E8F0',
          color: '#1E293B',
          '& .MuiChip-icon': { color: '#1E293B' },
        },
        colorPrimary: {
          backgroundColor: '#E2E8F0',
          color: '#1E293B',
        },
      },
    },

    MuiTextField: {
      defaultProps: { size: 'small' },
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 8,
            backgroundColor: '#FFFFFF',
            fontSize: '0.875rem',
            '& fieldset': { borderColor: '#E2E8F0', transition: 'border-color 0.15s' },
            '&:hover fieldset': { borderColor: '#CBD5E1' },
            '&.Mui-focused fieldset': { borderColor: '#F59E0B', borderWidth: 2 },
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
        standardSuccess: { backgroundColor: '#F0FDF4', color: '#166534' },
        standardError:   { backgroundColor: '#FEF2F2', color: '#991B1B' },
        standardWarning: { backgroundColor: '#FFFBEB', color: '#92400E' },
        standardInfo:    { backgroundColor: '#F1F5F9', color: '#1E293B' },
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
          backgroundColor: '#1E293B',
          padding: '5px 10px',
        },
        arrow: { color: '#1E293B' },
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
        root: { borderColor: '#E2E8F0' },
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
        indicator: { height: 3, borderRadius: '3px 3px 0 0', backgroundColor: '#F59E0B' },
        root: { borderBottom: '1px solid #E2E8F0' },
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
          color: '#64748B',
          '&.Mui-selected': { color: '#1E293B' },
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
        root: { backgroundColor: '#F1F5F9', borderRadius: 6 },
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
        separator: { color: '#CBD5E1' },
      },
    },

    MuiLink: {
      styleOverrides: {
        root: { textDecoration: 'none', '&:hover': { textDecoration: 'underline' } },
      },
    },
  },
})
