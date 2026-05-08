import { Box, Chip, LinearProgress, Tooltip, Typography } from '@mui/material'
import { alpha, styled, useTheme } from '@mui/material/styles'
import { useTranslation } from 'react-i18next'
import type { SpecialistLevel } from '../../types/domain'

const THRESHOLD = 90

interface LevelProgressIndicatorProps {
  level: SpecialistLevel | null
  percentage: number
  variant?: 'large' | 'compact'
}

const LevelBadge = styled(Chip)(({ theme }) => ({
  fontWeight: 600,
  borderRadius: theme.shape.borderRadius,
}))

export default function LevelProgressIndicator({
  level,
  percentage,
  variant = 'large',
}: LevelProgressIndicatorProps) {
  const theme = useTheme()
  const { t } = useTranslation()
  const safePercentage = Math.min(100, Math.max(0, percentage))
  const isThresholdReached = safePercentage >= THRESHOLD
  const barColor = isThresholdReached ? theme.palette.success.main : theme.palette.primary.main
  const levelLabel = level ? t(`levels.${level}`) : t('levels.unknown')

  if (variant === 'compact') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <LevelBadge label={levelLabel} size="small" />
        <LinearProgress
          variant="determinate"
          value={safePercentage}
          aria-label={t('dashboard.levelProgressAriaCompact', { level: levelLabel, percentage: safePercentage })}
          sx={{ flex: 1, '& .MuiLinearProgress-bar': { bgcolor: barColor } }}
        />
        <Typography variant="caption">{safePercentage}%</Typography>
      </Box>
    )
  }

  return (
    <Box
      sx={{
        p: 3,
        border: `1px solid ${isThresholdReached ? theme.palette.success.light : theme.palette.divider}`,
        borderRadius: 2,
        bgcolor: isThresholdReached ? alpha(theme.palette.success.light, 0.13) : 'background.paper',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <LevelBadge label={levelLabel} color={isThresholdReached ? 'success' : 'default'} />
        <Typography
          variant="h3"
          sx={{
            fontWeight: 700,
            color: isThresholdReached ? 'success.main' : 'text.primary',
          }}
        >
          {safePercentage}%
        </Typography>
      </Box>
      <Box sx={{ position: 'relative' }}>
        <LinearProgress
          variant="determinate"
          value={safePercentage}
          aria-label={t('dashboard.levelProgressAria', { level: levelLabel, percentage: safePercentage })}
          sx={{
            height: 12,
            borderRadius: 6,
            bgcolor: theme.palette.action.hover,
            '& .MuiLinearProgress-bar': { bgcolor: barColor, borderRadius: 6 },
          }}
        />
        <Tooltip title={t('dashboard.thresholdMarkerTitle', { threshold: THRESHOLD })}>
          <Box
            role="img"
            sx={{
              position: 'absolute',
              top: 0,
              left: `${THRESHOLD}%`,
              width: 2,
              height: '100%',
              bgcolor: theme.palette.warning.main,
              borderRadius: 1,
              cursor: 'help',
            }}
          />
        </Tooltip>
      </Box>
    </Box>
  )
}
