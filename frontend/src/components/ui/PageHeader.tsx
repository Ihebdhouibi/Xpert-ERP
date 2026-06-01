import { type ReactNode } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import {
  Box,
  Breadcrumbs,
  Link,
  Stack,
  Typography,
} from '@mui/material'
import NavigateNextRoundedIcon from '@mui/icons-material/NavigateNextRounded'

interface Breadcrumb {
  label: string
  href?: string
}

interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: ReactNode
  breadcrumbs?: Breadcrumb[]
}

export function PageHeader({ title, subtitle, actions, breadcrumbs }: PageHeaderProps) {
  return (
    <Box sx={{ mb: 3 }}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumbs
          separator={<NavigateNextRoundedIcon sx={{ fontSize: 14 }} />}
          sx={{ mb: 1.5 }}
        >
          {breadcrumbs.map((crumb, i) =>
            crumb.href ? (
              <Link
                key={i}
                component={RouterLink}
                to={crumb.href}
                underline="hover"
                color="text.secondary"
                fontSize="0.8125rem"
                fontWeight={500}
              >
                {crumb.label}
              </Link>
            ) : (
              <Typography
                key={i}
                color="text.primary"
                fontSize="0.8125rem"
                fontWeight={500}
              >
                {crumb.label}
              </Typography>
            ),
          )}
        </Breadcrumbs>
      )}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        flexWrap="wrap"
        gap={2}
      >
        <Box>
          <Typography variant="h4" fontWeight={700} lineHeight={1.2}>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary" mt={0.5}>
              {subtitle}
            </Typography>
          )}
        </Box>
        {actions && <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>{actions}</Box>}
      </Stack>
    </Box>
  )
}
