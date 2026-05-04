import { Box, Button, Chip, Skeleton, Typography } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { getCmTeam } from '../../api/cm'
import { useAuth } from '../../hooks/useAuth'

export default function CMDashboardPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const navigate = useNavigate()
  const cmId = user?.id ?? ''

  const { data: team, isLoading } = useQuery({
    queryKey: ['cm', 'team', cmId],
    queryFn: getCmTeam,
    enabled: !!cmId,
    staleTime: 30 * 1000,
  })

  if (isLoading) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>{t('cm.dashboard.title')}</Typography>
        <Skeleton variant="rectangular" height={64} sx={{ mb: 1, borderRadius: 1 }} />
        <Skeleton variant="rectangular" height={64} sx={{ mb: 1, borderRadius: 1 }} />
      </Box>
    )
  }

  if (!team || team.length === 0) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>{t('cm.dashboard.title')}</Typography>
        <Typography color="text.secondary">{t('cm.dashboard.noSpecialists')}</Typography>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3 }}>{t('cm.dashboard.title')}</Typography>
      {team.map((specialist) => (
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
          <Box>
            <Typography variant="body1" sx={{ fontWeight: 500 }}>{specialist.fullName}</Typography>
            <Typography variant="body2" color="text.secondary">{specialist.email}</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Chip
              label={specialist.isActive ? 'Active' : 'Inactive'}
              size="small"
              color={specialist.isActive ? 'success' : 'default'}
            />
            <Button
              variant="outlined"
              size="small"
              onClick={() => navigate(`/cm/matrix/${specialist.id}/review`)}
            >
              {t('cm.dashboard.reviewMatrix')}
            </Button>
          </Box>
        </Box>
      ))}
    </Box>
  )
}
