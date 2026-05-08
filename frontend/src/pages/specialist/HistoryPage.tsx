import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  Alert,
  Box,
  Button,
  Chip,
  Paper,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
} from '@mui/material'
import { useAuth } from '../../hooks/useAuth'
import { getSessions } from '../../api/sessions'
import type { SessionListItem } from '../../types/domain'

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString()
}

function DeltaChip({ finalScore, previousScore }: { finalScore: number | null; previousScore: number | null }) {
  const { t } = useTranslation()
  if (finalScore === null || previousScore === null || finalScore === previousScore) return null
  const delta = finalScore - previousScore
  const label = delta > 0
    ? t('history.deltaUp', { delta: `+${delta}` })
    : t('history.deltaDown', { delta })
  return <Chip label={label} size="small" color={delta > 0 ? 'success' : 'error'} variant="outlined" />
}

function DisputeBadge({ dispute }: { dispute: SessionListItem['dispute'] }) {
  const { t } = useTranslation()
  if (!dispute) return null
  return (
    <Chip
      label={dispute.status === 'resolved' ? t('history.disputeResolved') : t('history.disputeOpen')}
      size="small"
      color={dispute.status === 'resolved' ? 'warning' : 'info'}
      variant="outlined"
    />
  )
}

const PER_PAGE = 20

export default function HistoryPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [page, setPage] = useState(1)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['specialist', 'history', user?.id, page],
    queryFn: () => getSessions(page, PER_PAGE),
    enabled: !!user,
    staleTime: 10 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <Box sx={{ p: 3 }}>
        <Skeleton variant="rounded" height={40} sx={{ mb: 1 }} />
        <Skeleton variant="rounded" height={40} sx={{ mb: 1 }} />
        <Skeleton variant="rounded" height={40} sx={{ mb: 1 }} />
        <Skeleton variant="rounded" height={40} />
      </Box>
    )
  }

  if (isError) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => refetch()}>
              {t('matrix.retry')}
            </Button>
          }
        >
          {t('common.genericError')}
        </Alert>
      </Box>
    )
  }

  if (!data) return null

  if (data.total === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center', py: 8 }}>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          {t('history.empty')}
        </Typography>
        <Button variant="contained" onClick={() => navigate('/specialist/matrix')}>
          {t('history.startAssessment')}
        </Button>
      </Box>
    )
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>{t('history.title')}</Typography>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{t('history.category')}</TableCell>
              <TableCell>{t('history.date')}</TableCell>
              <TableCell>{t('history.score')}</TableCell>
              <TableCell>{t('history.change')}</TableCell>
              <TableCell>{t('history.dispute')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.items.map((session) => (
              <TableRow
                key={session.id}
                hover
                sx={{ cursor: 'pointer' }}
                onClick={() => navigate(`/specialist/session/${session.id}/result`, { state: { from: 'history' } })}
              >
                <TableCell>{session.categoryName ?? '—'}</TableCell>
                <TableCell>{formatDate(session.createdAt)}</TableCell>
                <TableCell>{session.finalScore != null ? `${session.finalScore}%` : '—'}</TableCell>
                <TableCell>
                  <DeltaChip finalScore={session.finalScore} previousScore={session.previousScore} />
                </TableCell>
                <TableCell>
                  <DisputeBadge dispute={session.dispute} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={data.total}
        page={page - 1}
        rowsPerPage={PER_PAGE}
        rowsPerPageOptions={[]}
        onPageChange={(_, newPage) => setPage(newPage + 1)}
      />
    </Box>
  )
}
