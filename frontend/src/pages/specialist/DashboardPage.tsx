import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Alert,
  Box,
  Button,
  Chip,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material'
import { useAuth } from '../../hooks/useAuth'
import { getSpecialistDashboard } from '../../api/users'
import LevelProgressIndicator from '../../components/shared/LevelProgressIndicator'
import type { CategoryScore } from '../../types/domain'

function daysSince(lastAssessedAt: string | null): number | null {
  if (!lastAssessedAt) return null
  return Math.floor((Date.now() - new Date(lastAssessedAt).getTime()) / (1000 * 60 * 60 * 24))
}

function formatDate(isoString: string | null): string {
  if (!isoString) return ''
  return new Date(isoString).toLocaleDateString()
}

function CategoryRow({ row }: { row: CategoryScore }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const days = daysSince(row.lastAssessedAt)
  const showInactivityNudge = days !== null && days > 45

  return (
    <TableRow>
      <TableCell>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="body2" sx={{ fontWeight: 500 }}>
            {row.categoryName}
          </Typography>
          {showInactivityNudge && days !== null && (
            <Tooltip title={t('dashboard.inactivityNudge', { category: row.categoryName })}>
              <Chip
                label={t('dashboard.inactivityNudgeChip', { days })}
                size="small"
                color="warning"
                variant="outlined"
              />
            </Tooltip>
          )}
        </Box>
      </TableCell>
        <TableCell>
          {row.score === null ? (
            <Typography variant="body2" color="text.secondary">
              {t('dashboard.notYetAssessed')}
            </Typography>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2">{row.score}%</Typography>
              {row.previousScore !== null && row.score !== row.previousScore && (
                <Chip
                  label={
                    row.score > row.previousScore
                      ? t('dashboard.deltaUp', { previous: row.previousScore })
                      : t('dashboard.deltaDown', { previous: row.previousScore })
                  }
                  size="small"
                  color={row.score > row.previousScore ? 'success' : 'error'}
                  variant="outlined"
                />
              )}
            </Box>
          )}
        </TableCell>
        <TableCell>
          {row.lastAssessedAt ? (
            <Typography variant="body2" color="text.secondary">
              {t('dashboard.lastAssessed', { date: formatDate(row.lastAssessedAt) })}
            </Typography>
          ) : (
            <Button
              variant="outlined"
              size="small"
              onClick={() => navigate('/specialist/matrix')}
            >
              {t('dashboard.startAssessment')}
            </Button>
          )}
        </TableCell>
    </TableRow>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const { t } = useTranslation()

  const {
    data: dashboard,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['specialist', 'dashboard', user?.id],
    queryFn: getSpecialistDashboard,
    enabled: !!user,
    staleTime: 30_000,
  })

  if (isLoading) {
    return (
      <Box sx={{ p: 3 }}>
        <Skeleton variant="rounded" height={120} sx={{ mb: 3 }} />
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

  if (!dashboard) return null

  if (dashboard.categoryScores.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">{t('dashboard.noMatrix')}</Alert>
      </Box>
    )
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" sx={{ fontWeight: 600 }} gutterBottom>
        {t('dashboard.title')}
      </Typography>

      <Box sx={{ mb: 4 }}>
        <LevelProgressIndicator
          level={dashboard.specialistLevel}
          percentage={dashboard.overallPercentage}
          variant="large"
        />
      </Box>

      <Typography variant="h6" gutterBottom>
        {t('dashboard.categories')}
      </Typography>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{t('dashboard.category')}</TableCell>
              <TableCell>{t('dashboard.overallProgress')}</TableCell>
              <TableCell>{t('dashboard.lastAssessedHeader')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {dashboard.categoryScores.map((row) => (
              <CategoryRow key={row.categoryId} row={row} />
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  )
}
