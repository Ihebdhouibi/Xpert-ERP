import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
} from '@dnd-kit/core'
import { useDroppable } from '@dnd-kit/core'
import { useDraggable } from '@dnd-kit/core'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Snackbar,
  Stack,
  Typography,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import { PermissionGate } from '../../components/auth/PermissionGate'
import {
  repairOrderApi,
  STATUS_LABELS,
  ALLOWED_TRANSITIONS,
  type ROStatus,
  type RepairOrderSummary,
} from '../../lib/repairOrderApi'

const STATUS_ORDER: ROStatus[] = [
  'created',
  'diagnosis',
  'in_repair',
  'paused_parts',
  'paused_approval',
  'finished',
  'delivered',
]

const STATUS_COLORS: Record<ROStatus, string> = {
  created: '#e3f2fd',
  diagnosis: '#e8f5e9',
  in_repair: '#fff3e0',
  finished: '#f3e5f5',
  delivered: '#e0f2f1',
  paused_parts: '#fce4ec',
  paused_approval: '#fce4ec',
}

const PRIORITY_COLORS: Record<string, 'default' | 'warning' | 'error'> = {
  low: 'default',
  normal: 'default',
  high: 'warning',
  urgent: 'error',
}

function KanbanCard({
  ro,
  isDragging = false,
  canDrag = false,
}: {
  ro: RepairOrderSummary
  isDragging?: boolean
  canDrag?: boolean
}) {
  const navigate = useNavigate()

  return (
    <Paper
      elevation={isDragging ? 8 : 1}
      onClick={() => navigate(`/repair-orders/${ro.id}`)}
      sx={{
        p: 1.5,
        cursor: canDrag ? 'grab' : 'pointer',
        opacity: isDragging ? 0.5 : 1,
        userSelect: 'none',
        '&:hover': { boxShadow: 4 },
        borderLeft: '4px solid',
        borderColor: ro.priority === 'urgent' ? 'error.main' : ro.priority === 'high' ? 'warning.main' : 'transparent',
      }}
    >
      <Stack spacing={0.5}>
        <Typography variant="caption" color="text.secondary" noWrap>
          #{ro.id.slice(-8).toUpperCase()}
        </Typography>
        <Typography variant="body2" fontWeight={600} noWrap title={ro.description}>
          {ro.description}
        </Typography>
        <Stack direction="row" spacing={0.5} flexWrap="wrap">
          {ro.priority && ro.priority !== 'normal' && (
            <Chip
              size="small"
              label={ro.priority}
              color={PRIORITY_COLORS[ro.priority] ?? 'default'}
              sx={{ height: 18, fontSize: 10 }}
            />
          )}
          {ro.vehicle_id && (
            <Chip
              size="small"
              label={`Véh #${ro.vehicle_id}`}
              variant="outlined"
              sx={{ height: 18, fontSize: 10 }}
            />
          )}
        </Stack>
        <Typography variant="caption" color="text.secondary">
          Client #{ro.customer_id}
          {ro.assigned_user_id ? ` · Méc. #${ro.assigned_user_id}` : ''}
        </Typography>
      </Stack>
    </Paper>
  )
}

function DraggableCard({
  ro,
  canDrag,
}: {
  ro: RepairOrderSummary
  canDrag: boolean
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: ro.id,
    disabled: !canDrag,
    data: { ro },
  })

  return (
    <Box ref={setNodeRef} {...(canDrag ? { ...listeners, ...attributes } : {})}>
      <KanbanCard ro={ro} isDragging={isDragging} canDrag={canDrag} />
    </Box>
  )
}

function KanbanColumn({
  status,
  cards,
  canDrop,
}: {
  status: ROStatus
  cards: RepairOrderSummary[]
  canDrop: boolean
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status, disabled: !canDrop })

  return (
    <Box
      sx={{
        minWidth: 230,
        maxWidth: 260,
        flex: '0 0 230px',
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
      }}
    >
      <Box
        sx={{
          px: 1.5,
          py: 1,
          borderRadius: 1,
          bgcolor: STATUS_COLORS[status],
          borderBottom: '2px solid',
          borderColor: 'divider',
        }}
      >
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="subtitle2" fontWeight={700}>
            {STATUS_LABELS[status]}
          </Typography>
          <Chip label={cards.length} size="small" sx={{ height: 20, fontSize: 11 }} />
        </Stack>
      </Box>

      <Box
        ref={setNodeRef}
        sx={{
          flex: 1,
          minHeight: 120,
          p: 0.5,
          borderRadius: 1,
          bgcolor: isOver ? 'action.hover' : 'transparent',
          border: isOver ? '2px dashed' : '2px solid transparent',
          borderColor: isOver ? 'primary.main' : 'transparent',
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
          transition: 'background-color 0.15s, border-color 0.15s',
        }}
      >
        {cards.map((ro) => (
          <DraggableCard key={ro.id} ro={ro} canDrag={canDrop} />
        ))}
      </Box>
    </Box>
  )
}

export function WorkshopKanbanPage() {
  const queryClient = useQueryClient()
  const [activeRo, setActiveRo] = useState<RepairOrderSummary | null>(null)
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  })

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['kanban-repair-orders'],
    queryFn: () => repairOrderApi.list({ page_size: 100 }),
    refetchInterval: 30000,
  })

  const transitionMutation = useMutation({
    mutationFn: ({ publicId, newStatus }: { publicId: string; newStatus: ROStatus }) =>
      repairOrderApi.transition(publicId, { new_status: newStatus }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['kanban-repair-orders'] })
      setSnackbar({ open: true, message: 'Statut mis à jour', severity: 'success' })
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ['kanban-repair-orders'] })
      setSnackbar({ open: true, message: 'Transition invalide ou accès refusé', severity: 'error' })
    },
  })

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const ro = event.active.data.current?.ro as RepairOrderSummary | undefined
    setActiveRo(ro ?? null)
  }, [])

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setActiveRo(null)
      const { active, over } = event
      if (!over) return
      const ro = active.data.current?.ro as RepairOrderSummary | undefined
      if (!ro) return
      const newStatus = over.id as ROStatus
      if (newStatus === ro.status) return
      const allowed = ALLOWED_TRANSITIONS[ro.status]
      if (!allowed.includes(newStatus)) {
        setSnackbar({ open: true, message: `Transition ${STATUS_LABELS[ro.status]} → ${STATUS_LABELS[newStatus]} non permise`, severity: 'error' })
        return
      }
      transitionMutation.mutate({ publicId: ro.id, newStatus })
    },
    [transitionMutation]
  )

  const groupedByStatus: Record<ROStatus, RepairOrderSummary[]> = STATUS_ORDER.reduce(
    (acc, s) => ({ ...acc, [s]: [] }),
    {} as Record<ROStatus, RepairOrderSummary[]>
  )
  data?.items.forEach((ro) => {
    if (groupedByStatus[ro.status]) groupedByStatus[ro.status].push(ro)
  })

  return (
    <Box p={3} sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            Tableau kanban atelier
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Glissez les cartes pour changer le statut &mdash; actualisation auto toutes les 30 s
          </Typography>
        </Box>
        <Button startIcon={<RefreshIcon />} onClick={() => refetch()} size="small">
          Actualiser
        </Button>
      </Stack>

      {isLoading && (
        <Box display="flex" justifyContent="center" pt={8}>
          <CircularProgress />
        </Box>
      )}
      {isError && (
        <Alert severity="error">Impossible de charger les ordres de réparation.</Alert>
      )}

      {data && (
        <PermissionGate
          permission="repair_order.transition"
          fallback={
            <Box
              sx={{
                display: 'flex',
                gap: 2,
                overflowX: 'auto',
                pb: 2,
                flex: 1,
              }}
            >
              {STATUS_ORDER.map((s) => (
                <KanbanColumn key={s} status={s} cards={groupedByStatus[s]} canDrop={false} />
              ))}
            </Box>
          }
        >
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <Box sx={{ display: 'flex', gap: 2, overflowX: 'auto', pb: 2, flex: 1 }}>
              {STATUS_ORDER.map((s) => (
                <KanbanColumn key={s} status={s} cards={groupedByStatus[s]} canDrop />
              ))}
            </Box>

            <DragOverlay>
              {activeRo && <KanbanCard ro={activeRo} canDrag />}
            </DragOverlay>
          </DndContext>
        </PermissionGate>
      )}

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  )
}
