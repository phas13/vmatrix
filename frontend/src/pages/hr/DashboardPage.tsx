import { Alert, Box, Button, Chip, Skeleton, Typography, useTheme } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getHrStats } from '../../api/hr'

const LEVELS = ['junior', 'middle', 'senior'] as const

export default function HRDashboardPage() {
  const { t } = useTranslation()
  const theme = useTheme()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['hr', 'stats'],
    queryFn: getHrStats,
    staleTime: 5 * 60 * 1000,
  })

  return (
    <Box sx={{ p: 3, maxWidth: 900, mx: 'auto' }}>
      <Typography variant="h4" gutterBottom>
        {t('hr.dashboard.title')}
      </Typography>

      {isError && (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => refetch()}>
              {t('common.retry')}
            </Button>
          }
          sx={{ mb: 3 }}
        >
          {t('hr.dashboard.loadError')}
        </Alert>
      )}

      {/* Level Distribution */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          {t('hr.dashboard.levelDistribution')}
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          {isLoading
            ? LEVELS.map((l) => <Skeleton key={l} variant="rounded" width={120} height={56} />)
            : LEVELS.map((level) => {
                const count = data?.levelDistribution[level] ?? 0
                return (
                  <Box
                    key={level}
                    sx={{
                      p: 2,
                      border: `1px solid ${theme.palette.divider}`,
                      borderRadius: 2,
                      minWidth: 120,
                      textAlign: 'center',
                    }}
                  >
                    <Typography variant="h4" color="primary">
                      {count}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'capitalize' }}>
                      {level}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {t('hr.dashboard.specialists')}
                    </Typography>
                  </Box>
                )
              })}
        </Box>
      </Box>

      {/* Average Progress per Level */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          {t('hr.dashboard.avgProgress')}
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          {isLoading
            ? LEVELS.map((l) => <Skeleton key={l} variant="rounded" width={140} height={56} />)
            : LEVELS.map((level) => {
                const pct = data?.avgProgressPerLevel[level]
                return (
                  <Box
                    key={level}
                    sx={{
                      p: 2,
                      border: `1px solid ${theme.palette.divider}`,
                      borderRadius: 2,
                      minWidth: 140,
                      textAlign: 'center',
                    }}
                  >
                    <Typography variant="h4" color="text.primary">
                      {pct !== undefined ? `${pct}%` : '—'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'capitalize' }}>
                      {level}
                    </Typography>
                  </Box>
                )
              })}
        </Box>
      </Box>

      {/* Strongest Areas */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          {t('hr.dashboard.strongestAreas')}
        </Typography>
        {isLoading ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {[1, 2, 3].map((i) => <Skeleton key={i} variant="text" height={32} />)}
          </Box>
        ) : !data?.strongestAreas.length ? (
          <Typography variant="body2" color="text.secondary">
            {t('hr.dashboard.noData')}
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {data.strongestAreas.map((area) => (
              <Box key={area.categoryName} sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body1" sx={{ flex: 1 }}>
                  {area.categoryName}
                </Typography>
                <Chip
                  label={`${t('hr.dashboard.avgScore')}: ${area.avgScore}%`}
                  color="success"
                  size="small"
                />
              </Box>
            ))}
          </Box>
        )}
      </Box>

      {/* Weakest Areas */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          {t('hr.dashboard.weakestAreas')}
        </Typography>
        {isLoading ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {[1, 2, 3].map((i) => <Skeleton key={i} variant="text" height={32} />)}
          </Box>
        ) : !data?.weakestAreas.length ? (
          <Typography variant="body2" color="text.secondary">
            {t('hr.dashboard.noData')}
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {data.weakestAreas.map((area) => (
              <Box key={area.categoryName} sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body1" sx={{ flex: 1 }}>
                  {area.categoryName}
                </Typography>
                <Chip
                  label={`${t('hr.dashboard.avgScore')}: ${area.avgScore}%`}
                  color="warning"
                  size="small"
                />
              </Box>
            ))}
          </Box>
        )}
      </Box>
    </Box>
  )
}
