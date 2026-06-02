import { type ReactNode } from 'react'
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  Typography,
} from '@mui/material'
import { EmptyState } from './EmptyState'
import { TableLoadingSkeleton } from './LoadingScreen'

export interface Column<T> {
  id: string
  label: string
  render: (row: T) => ReactNode
  align?: 'left' | 'center' | 'right'
  width?: string | number
  minWidth?: string | number
  sortable?: boolean
  // Mark a column as "actions" — hidden until the row is hovered.
  // Stripe/Linear pattern: reduces visual clutter from N rows × N icons.
  actions?: boolean
}

interface DataTableProps<T> {
  columns: Column<T>[]
  rows: T[]
  getRowKey: (row: T) => string
  onRowClick?: (row: T) => void
  loading?: boolean
  error?: boolean
  errorMessage?: string
  total?: number
  page?: number
  pageSize?: number
  onPageChange?: (page: number) => void
  onPageSizeChange?: (size: number) => void
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: ReactNode
  stickyHeader?: boolean
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  onSort?: (columnId: string) => void
}

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  onRowClick,
  loading = false,
  error = false,
  errorMessage = 'Impossible de charger les données.',
  total,
  page,
  pageSize = 20,
  onPageChange,
  onPageSizeChange,
  emptyTitle = 'Aucun résultat',
  emptyDescription,
  emptyAction,
  stickyHeader = false,
  sortBy,
  sortOrder = 'asc',
  onSort,
}: DataTableProps<T>) {
  const showPagination = total != null && page != null && onPageChange != null
  const hasActionCol = columns.some(c => c.actions)

  return (
    <Paper
      variant="outlined"
      sx={{ borderRadius: 2, overflow: 'hidden', border: '1px solid #E2E8F0' }}
    >
      <TableContainer>
        <Table stickyHeader={stickyHeader} size="medium">
          <TableHead>
            <TableRow>
              {columns.map(col => (
                <TableCell
                  key={col.id}
                  align={col.align ?? 'left'}
                  sx={{
                    width: col.width,
                    minWidth: col.minWidth,
                    // Action columns: right-align header, no label needed
                    ...(col.actions && { width: 48, padding: '10px 12px' }),
                  }}
                  sortDirection={sortBy === col.id ? sortOrder : false}
                >
                  {col.actions ? null : col.sortable && onSort ? (
                    <TableSortLabel
                      active={sortBy === col.id}
                      direction={sortBy === col.id ? sortOrder : 'asc'}
                      onClick={() => onSort(col.id)}
                    >
                      {col.label}
                    </TableSortLabel>
                  ) : (
                    col.label
                  )}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>

          <TableBody>
            {loading && (
              <TableLoadingSkeleton cols={columns.length} rows={pageSize > 10 ? 8 : 4} />
            )}

            {!loading && error && (
              <TableRow>
                <TableCell colSpan={columns.length} align="center" sx={{ py: 4 }}>
                  <Typography color="error.main" variant="body2" fontWeight={500}>
                    {errorMessage}
                  </Typography>
                </TableCell>
              </TableRow>
            )}

            {!loading && !error && rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={columns.length} sx={{ border: 0 }}>
                  <EmptyState
                    title={emptyTitle}
                    description={emptyDescription}
                    action={emptyAction}
                  />
                </TableCell>
              </TableRow>
            )}

            {!loading &&
              !error &&
              rows.map(row => (
                <TableRow
                  key={getRowKey(row)}
                  hover={!!onRowClick}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  sx={{
                    cursor: onRowClick ? 'pointer' : 'default',
                    // Hover reveals action columns with a smooth fade
                    ...(hasActionCol && {
                      '& .DataTable-actions': {
                        opacity: 0,
                        transition: 'opacity 0.15s ease',
                      },
                      '&:hover .DataTable-actions': {
                        opacity: 1,
                      },
                    }),
                  }}
                >
                  {columns.map(col => (
                    <TableCell
                      key={col.id}
                      align={col.align ?? 'left'}
                      sx={col.actions ? { padding: '8px 12px', width: 48 } : undefined}
                      // Stop row click from firing when clicking action buttons
                      onClick={col.actions ? e => e.stopPropagation() : undefined}
                    >
                      {col.actions ? (
                        <Box className="DataTable-actions">
                          {col.render(row)}
                        </Box>
                      ) : (
                        col.render(row)
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </TableContainer>

      {showPagination && !loading && (
        <Box sx={{ borderTop: '1px solid #F1F5F9' }}>
          <TablePagination
            component="div"
            count={total!}
            page={page!}
            onPageChange={(_, newPage) => onPageChange!(newPage)}
            rowsPerPage={pageSize}
            rowsPerPageOptions={[10, 20, 50, 100]}
            onRowsPerPageChange={
              onPageSizeChange
                ? e => onPageSizeChange(parseInt(e.target.value, 10))
                : undefined
            }
            labelRowsPerPage="Lignes :"
            labelDisplayedRows={({ from, to, count }) =>
              `${from}–${to} sur ${count !== -1 ? count : `plus de ${to}`}`
            }
          />
        </Box>
      )}
    </Paper>
  )
}
