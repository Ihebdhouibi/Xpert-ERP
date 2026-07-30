import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  TouchSensor,
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
  Stack,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { useToast } from '../../contexts/ToastContext'
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
  'finished',
  'delivered',
]

const STATUS_ACCENT: Record<ROStatus, string> = {
  created: '#94A3B8',
  diagnosis: '#334155',
  in_repair: '#F59E0B',
  finished: '#10B981',
  delivered: '#6366F1',
  paused_parts: '#EF4444',
}

const PRIORITY_LABELS: Record<string, string> = {
  low: 'Basse', normal: 'Normale', high: 'Haute', urgent: 'Urgente',
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
      elevation={isDragging ? 8 : 0}
      onClick={() => navigate(`/repair-orders/${ro.id}`)}
      sx={{
        p: 1.5,
        cursor: canDrag ? 'grab' : 'pointer',
        opacity: isDragging ? 0.5 : 1,
        userSelect: 'none',
        border: '1px solid #E2E8F0',
        borderLeft: '4px solid',
        borderLeftColor: ro.priority === 'urgent'
          ? 'error.main'
          : ro.priority === 'high'
          ? 'warning.main'
          : 'transparent',
        transition: 'box-shadow 0.15s',
        '&:hover': { boxShadow: '0 2px 8px rgba(0,0,0,0.10)' },
      }}
    >
      <Stack spacing={0.5}>
        <Typography variant="caption" color="text.disabled" fontFamily="monospace">
          #{ro.id.slice(-8).toUpperCase()}
        </Typography>
        <Typography variant="body2" fontWeight={600} noWrap title={ro.description || undefined}>
          {ro.description || 'Sans description'}
        </Typography>
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
          {ro.priority && ro.priority !== 'normal' && (
            <Chip
              size="small"
              label={PRIORITY_LABELS[ro.priority]}
              color={ro.priority === 'urgent' ? 'error' : 'warning'}
              sx={{ height: 18, fontSize: '0.65rem', fontWeight: 600 }}
            />
          )}
          {ro.vehicle_id && (
            <Chip
              size="small"
              label={`Véh. #${ro.vehicle_id}`}
              variant="outlined"
              sx={{ height: 18, fontSize: '0.65rem' }}
            />
          )}
        </Stack>
        <Typography variant="caption" color="text.secondary">
          {ro.customer_name ?? `Client #${ro.customer_id}`}
          {ro.assigned_user_id ? ` · Méc. #${ro.assigned_user_id}` : ''}
        </Typography>
      </Stack>
    </Paper>
  )
}

function DraggableCard({ ro, canDrag }: { ro: RepairOrderSummary; canDrag: boolean }) {
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
        // Scroll-snap alignment — each column snaps into view on tablet
        scrollSnapAlign: 'start',
        minWidth: 230,
        width: 250,
        flex: '0 0 250px',
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
      }}
    >
      {/* Sticky column header */}
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          px: 1.5,
          py: 1.25,
          borderRadius: '8px 8px 0 0',
          bgcolor: 'background.paper',
          borderTop: '3px solid',
          borderColor: STATUS_ACCENT[status],
          borderBottom: '1px solid #E2E8F0',
        }}
      >
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="subtitle2" fontWeight={700} fontSize="0.8125rem">
            {STATUS_LABELS[status]}
          </Typography>
          <Box
            sx={{
              minWidth: 22, height: 22, borderRadius: '6px',
              bgcolor: cards.length > 0 ? STATUS_ACCENT[status] : '#E2E8F0',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <Typography
              variant="caption"
              fontWeight={700}
              fontSize="0.6875rem"
              color={cards.length > 0 ? 'white' : 'text.disabled'}
            >
              {cards.length}
            </Typography>
          </Box>
        </Stack>
      </Box>

      {/* Drop zone */}
      <Box
        ref={setNodeRef}
        sx={{
          flex: 1,
          minHeight: 120,
          p: 0.75,
          borderRadius: '0 0 8px 8px',
          bgcolor: isOver ? 'rgba(245,158,11,0.1)' : '#F8FAFC',
          border: '1px solid',
          borderTop: 0,
          borderColor: isOver ? '#F59E0B' : '#E2E8F0',
          display: 'flex',
          flexDirection: 'column',
          gap: 0.75,
          transition: 'background-color 0.15s, border-color 0.15s',
        }}
      >
        {cards.map(ro => (
          <DraggableCard key={ro.id} ro={ro} canDrag={canDrop} />
        ))}
      </Box>
    </Box>
  )
}

// Mobile fallback: grouped vertical list when screen is too narrow for columns
function MobileGroupedList({ grouped }: { grouped: Record<ROStatus, RepairOrderSummary[]> }) {
  const navigate = useNavigate()
  return (
    <Stack spacing={2}>
      {STATUS_ORDER.filter(s => grouped[s].length > 0).map(s => (
        <Box key={s}>
          <Stack direction="row" alignItems="center" spacing={1.5} mb={1}>
            <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: STATUS_ACCENT[s], flexShrink: 0 }} />
            <Typography variant="subtitle2" fontWeight={700}>{STATUS_LABELS[s]}</Typography>
            <Box
              sx={{
                minWidth: 20, height: 20, borderRadius: '5px',
                bgcolor: STATUS_ACCENT[s], display: 'flex',
                alignItems: 'center', justifyContent: 'center',
              }}
            >
              <Typography variant="caption" fontWeight={700} fontSize="0.625rem" color="white">
                {grouped[s].length}
              </Typography>
            </Box>
          </Stack>
          <Stack spacing={1}>
            {grouped[s].map(ro => (
              <Paper
                key={ro.id}
                elevation={0}
                onClick={() => navigate(`/repair-orders/${ro.id}`)}
                sx={{
                  p: 1.5, cursor: 'pointer',
                  border: '1px solid #E2E8F0',
                  borderLeft: `4px solid ${STATUS_ACCENT[s]}`,
                  '&:hover': { bgcolor: '#F9FAFB' },
                }}
              >
                <Stack direction="row" alignItems="center" justifyContent="space-between">
                  <Box flex={1} minWidth={0} mr={1}>
                    <Typography variant="body2" fontWeight={600} noWrap>{ro.description || 'Sans description'}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {ro.customer_name ?? `Client #${ro.customer_id}`} · #{ro.id.slice(-6).toUpperCase()}
                    </Typography>
                  </Box>
                  <StatusChip status={ro.status} label={STATUS_LABELS[s]} />
                </Stack>
              </Paper>
            ))}
          </Stack>
        </Box>
      ))}
    </Stack>
  )
}

export function WorkshopKanbanPage() {
  const queryClient = useQueryClient()
  const { success: toastSuccess, error: toastError } = useToast()
  const [activeRo, setActiveRo] = useState<RepairOrderSummary | null>(null)
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'))

  // PointerSensor for mouse + stylus, TouchSensor for finger (delay prevents
  // accidental drags when scrolling the horizontal column list on tablet)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } })
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
      toastSuccess('Statut mis à jour.')
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ['kanban-repair-orders'] })
      toastError('Transition invalide ou accès refusé.')
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
        toastError(`Transition ${STATUS_LABELS[ro.status]} → ${STATUS_LABELS[newStatus]} non permise.`)
        return
      }
      transitionMutation.mutate({ publicId: ro.id, newStatus })
    },
    [transitionMutation, toastError]
  )

  const groupedByStatus: Record<ROStatus, RepairOrderSummary[]> = STATUS_ORDER.reduce(
    (acc, s) => ({ ...acc, [s]: [] }),
    {} as Record<ROStatus, RepairOrderSummary[]>
  )
  data?.items.forEach(ro => {
    if (groupedByStatus[ro.status]) groupedByStatus[ro.status].push(ro)
  })

  const totalActive = data
    ? data.items.filter(r => r.status !== 'delivered').length
    : 0

  const kanbanColumns = (canDrop: boolean) => (
    <Box
      sx={{
        display: 'flex',
        gap: 2,
        overflowX: 'auto',
        pb: 2,
        flex: 1,
        // Scroll-snap: each column snaps cleanly into view on tablet
        scrollSnapType: 'x proximity',
        // Allow vertical page scroll while enabling horizontal swipe
        touchAction: 'pan-y',
        // Custom scrollbar styling
        '&::-webkit-scrollbar': { height: 6 },
        '&::-webkit-scrollbar-track': { bgcolor: '#F1F5F9', borderRadius: 999 },
        '&::-webkit-scrollbar-thumb': { bgcolor: '#CBD5E1', borderRadius: 999 },
      }}
    >
      {STATUS_ORDER.map(s => (
        <KanbanColumn key={s} status={s} cards={groupedByStatus[s]} canDrop={canDrop} />
      ))}
    </Box>
  )

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)' }}>
      <PageHeader
        title="Suivi Atelier"
        subtitle={
          data
            ? `${totalActive} ordre${totalActive !== 1 ? 's' : ''} actif${totalActive !== 1 ? 's' : ''} · actualisation auto 30 s`
            : 'Glissez les cartes pour changer le statut'
        }
        actions={
          <Button
            startIcon={<RefreshRoundedIcon />}
            onClick={() => refetch()}
            size="small"
            variant="outlined"
          >
            Actualiser
          </Button>
        }
      />

      {isLoading && (
        <Box display="flex" justifyContent="center" pt={8}>
          <CircularProgress />
        </Box>
      )}
      {isError && (
        <Alert severity="error">Impossible de charger les ordres de réparation.</Alert>
      )}

      {data && (
        <>
          {/* Mobile (xs/sm): vertical grouped list — Kanban columns are unreadable at <600px */}
          {isMobile ? (
            <Box sx={{ flex: 1, overflowY: 'auto', pb: 2 }}>
              <MobileGroupedList grouped={groupedByStatus} />
            </Box>
          ) : (
            <PermissionGate
              permission="repair_order.transition"
              fallback={kanbanColumns(false)}
            >
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
              >
                {kanbanColumns(true)}
                <DragOverlay>
                  {activeRo && <KanbanCard ro={activeRo} canDrag />}
                </DragOverlay>
              </DndContext>
            </PermissionGate>
          )}
        </>
      )}
    </Box>
  )
}
