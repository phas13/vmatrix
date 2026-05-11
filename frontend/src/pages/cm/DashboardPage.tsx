import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import { Alert, Box, Button, Chip, Link, Skeleton, Typography, useTheme } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { getCmPending, getCmTeam } from '../../api/cm'
import PendingActionsPanel from '../../components/cm/PendingActionsPanel'
import { useAuth } from '../../hooks/useAuth'
import type { SpecialistLevel } from '../../types/domain'

const INACTIVE_DAYS_THRESHOLD = 14

function isInactive(lastActivityAt: string | null): boolean {
  if (!lastActivityAt) return true
  const diffMs = Date.now() - new Date(lastActivityAt).getTime()
  return diffMs / (1000 * 60 * 60 * 24) > INACTIVE_DAYS_THRESHOLD
}

const LEVEL_CHIP_COLOR: Record<string, 'default' | 'primary' | 'success'> = {
  junior: 'default',
  middle: 'primary',
  senior: 'success',
}

export default function CMDashboardPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const navigate = useNavigate()
  const theme = useTheme()
  const cmId = user?.id

  const {
    data: pendingData,
    isLoading: pendingLoading,
    isError: pendingError,
    refetch: refetchPending,
  } = useQuery({
    queryKey: ['cm', 'pending', cmId],
    queryFn: getCmPending,
    enabled: !!cmId,
    staleTime: 30 * 1000,
  })

  const { data: team, isLoading: teamLoading } = useQuery({
    queryKey: ['cm', 'team', cmId],
    queryFn: getCmTeam,
    enabled: !!cmId,
    staleTime: 30 * 1000,
  })

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3 }}>{t('cm.dashboard.title')}</Typography>

      {/* Pending Actions Section — FIRST per UX spec */}
      <Typography variant="h6" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
        {t('cm.dashboard.pendingActions')}
        {(pendingData?.total ?? 0) > 0 && (
          <Chip label={pendingData!.total} color="error" size="small" />
        )}
      </Typography>
      {pendingError ? (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => refetchPending()}>
              {t('common.retry')}
            </Button>
          }
        >
          {t('cm.pending.loadError')}
        </Alert>
      ) : (
        <PendingActionsPanel data={pendingData} isLoading={pendingLoading} />
      )}

      {/* Team Overview Section */}
      <Typography variant="h6" sx={{ mt: 3, mb: 1 }}>{t('cm.dashboard.teamOverview')}</Typography>

      {teamLoading && (
        <>
          <Skeleton variant="rectangular" height={64} sx={{ mb: 1, borderRadius: 1 }} />
          <Skeleton variant="rectangular" height={64} sx={{ mb: 1, borderRadius: 1 }} />
          <Skeleton variant="rectangular" height={64} sx={{ mb: 1, borderRadius: 1 }} />
        </>
      )}

      {!teamLoading && (!team || team.length === 0) && (
        <Typography color="text.secondary">{t('cm.dashboard.noSpecialists')}</Typography>
      )}

      {!teamLoading && team && team.length > 0 && team.map((specialist) => {
        const inactive = isInactive(specialist.lastActivityAt)
        const levelKey = specialist.specialistLevel as SpecialistLevel | null
        return (
          <Box
            key={specialist.id}
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              p: 2,
              mb: 1,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
              <Link
                component={RouterLink}
                to={`/cm/specialist/${specialist.id}`}
                variant="body1"
                sx={{
                  fontWeight: 500,
                  color: 'text.primary',
                  textDecoration: 'none',
                  '&:hover': { textDecoration: 'underline' },
                }}
              >
                {specialist.fullName}
              </Link>
              <Chip
                label={t(`levels.${levelKey ?? 'unknown'}`)}
                color={LEVEL_CHIP_COLOR[levelKey ?? ''] ?? 'default'}
                size="small"
              />
              <Typography variant="body2" color="text.secondary">
                {t('cm.dashboard.overallProgress', { percentage: specialist.overallPercentage })}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {inactive && (
                  <WarningAmberIcon
                    sx={{ fontSize: 18, color: theme.palette.warning.main }}
                    titleAccess={t('cm.dashboard.inactiveWarning', { days: INACTIVE_DAYS_THRESHOLD })}
                  />
                )}
                <Typography variant="body2" color="text.secondary">
                  {specialist.lastActivityAt
                    ? t('cm.dashboard.lastActive', {
                        date: new Date(specialist.lastActivityAt).toLocaleDateString(),
                      })
                    : t('cm.dashboard.neverAssessed')}
                </Typography>
              </Box>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Button
                variant="text"
                size="small"
                onClick={() => navigate(`/cm/specialist/${specialist.id}`)}
              >
                {t('cm.dashboard.viewDetails')}
              </Button>
              <Button
                variant="outlined"
                size="small"
                onClick={() => navigate(`/cm/matrix/${specialist.id}/review`)}
              >
                {t('cm.dashboard.reviewMatrix')}
              </Button>
            </Box>
          </Box>
        )
      })}
    </Box>
  )
}
