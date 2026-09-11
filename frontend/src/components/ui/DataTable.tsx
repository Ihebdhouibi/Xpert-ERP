import { type ReactNode } from 'react'
import {
  Box,
  Checkbox,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  Toolbar,
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
  // Row selection (checkboxes) — additive, existing consumers are unaffected
  // unless they opt in. `selected` holds the keys from getRowKey().
  selectable?: boolean
  selected?: Set<string>
  onSelectionChange?: (selected: Set<string>) => void
  /** Rendered as a toolbar replacing the default header row while
   * `selected` is non-empty — the table doesn't know what the actions do,
   * the page supplies them. */
  bulkActionsSlot?: (selectedIds: Set<string>, clearSelection: () => void) => ReactNode
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
  selectable = false,
  selected,
  onSelectionChange,
  bulkActionsSlot,
}: DataTableProps<T>) {
  const showPagination = total != null && page != null && onPageChange != null
  const hasActionCol = columns.some(c => c.actions)
  const selectedIds = selected ?? new Set<string>()
  const pageRowKeys = rows.map(getRowKey)
  const selectedOnPageCount = pageRowKeys.filter(k => selectedIds.has(k)).length
  const allOnPageSelected = rows.length > 0 && selectedOnPageCount === rows.length
  const someOnPageSelected = selectedOnPageCount > 0 && !allOnPageSelected

  const toggleRow = (key: string) => {
    if (!onSelectionChange) return
    const next = new Set(selectedIds)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    onSelectionChange(next)
  }

  const toggleAllOnPage = () => {
    if (!onSelectionChange) return
    const next = new Set(selectedIds)
    if (allOnPageSelected) {
      pageRowKeys.forEach(k => next.delete(k))
    } else {
      pageRowKeys.forEach(k => next.add(k))
    }
    onSelectionChange(next)
  }

  return (
    <Paper
      variant="outlined"
      sx={{ borderRadius: 2, overflow: 'hidden', border: '1px solid', borderColor: 'divider' }}
    >
      {selectable && selectedIds.size > 0 && bulkActionsSlot && (
        <Toolbar
          variant="dense"
          sx={{
            bgcolor: 'action.selected',
            borderBottom: '1px solid',
            borderColor: 'divider',
            gap: 1.5,
            minHeight: 48,
          }}
        >
          <Checkbox
            size="small"
            checked={allOnPageSelected}
            indeterminate={someOnPageSelected}
            onChange={toggleAllOnPage}
          />
          <Typography variant="body2" fontWeight={600} sx={{ flex: 1 }}>
            {selectedIds.size} sélectionné{selectedIds.size > 1 ? 's' : ''}
          </Typography>
          {bulkActionsSlot(selectedIds, () => onSelectionChange?.(new Set()))}
        </Toolbar>
      )}
      <TableContainer>
        <Table stickyHeader={stickyHeader} size="medium">
          <TableHead>
            <TableRow>
              {selectable && (
                <TableCell padding="checkbox">
                  <Checkbox
                    size="small"
                    checked={allOnPageSelected}
                    indeterminate={someOnPageSelected}
                    onChange={toggleAllOnPage}
                  />
                </TableCell>
              )}
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
              <TableLoadingSkeleton
                cols={columns.length + (selectable ? 1 : 0)}
                rows={pageSize > 10 ? 8 : 4}
              />
            )}

            {!loading && error && (
              <TableRow>
                <TableCell colSpan={columns.length + (selectable ? 1 : 0)} align="center" sx={{ py: 4 }}>
                  <Typography color="error.main" variant="body2" fontWeight={500}>
                    {errorMessage}
                  </Typography>
                </TableCell>
              </TableRow>
            )}

            {!loading && !error && rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={columns.length + (selectable ? 1 : 0)} sx={{ border: 0 }}>
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
              rows.map(row => {
                const rowKey = getRowKey(row)
                const isSelected = selectedIds.has(rowKey)
                return (
                <TableRow
                  key={rowKey}
                  hover={!!onRowClick}
                  selected={isSelected}
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
                  {selectable && (
                    <TableCell
                      padding="checkbox"
                      onClick={e => e.stopPropagation()}
                    >
                      <Checkbox
                        size="small"
                        checked={isSelected}
                        onChange={() => toggleRow(rowKey)}
                      />
                    </TableCell>
                  )}
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
                )
              })}
          </TableBody>
        </Table>
      </TableContainer>

      {showPagination && !loading && (
        <Box sx={{ borderTop: '1px solid', borderColor: 'divider' }}>
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
