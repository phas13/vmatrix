import { Box, Chip, LinearProgress, Typography } from '@mui/material'
import { styled, useTheme } from '@mui/material/styles'
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
  const isThresholdReached = percentage >= THRESHOLD
  const barColor = isThresholdReached ? theme.palette.success.main : theme.palette.primary.main
  const displayLevel = level ?? '—'

  if (variant === 'compact') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <LevelBadge label={displayLevel} size="small" />
        <Box
          sx={{ flex: 1 }}
          role="progressbar"
          aria-valuenow={percentage}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${displayLevel}: ${percentage}%`}
        >
          <LinearProgress
            variant="determinate"
            value={percentage}
            sx={{ '& .MuiLinearProgress-bar': { bgcolor: barColor } }}
          />
        </Box>
        <Typography variant="caption">{percentage}%</Typography>
      </Box>
    )
  }

  return (
    <Box
      sx={{
        p: 3,
        border: `1px solid ${isThresholdReached ? theme.palette.success.light : theme.palette.divider}`,
        borderRadius: 2,
        bgcolor: isThresholdReached ? theme.palette.success.light + '22' : 'background.paper',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <LevelBadge label={displayLevel} color={isThresholdReached ? 'success' : 'default'} />
        <Typography
          variant="h3"
          sx={{
            fontWeight: 700,
            color: isThresholdReached ? 'success.main' : 'text.primary',
          }}
        >
          {percentage}%
        </Typography>
      </Box>
      <Box sx={{ position: 'relative' }}>
        <Box
          role="progressbar"
          aria-valuenow={percentage}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${displayLevel} level: ${percentage}% overall progress`}
        >
          <LinearProgress
            variant="determinate"
            value={percentage}
            sx={{
              height: 12,
              borderRadius: 6,
              bgcolor: theme.palette.action.hover,
              '& .MuiLinearProgress-bar': { bgcolor: barColor, borderRadius: 6 },
            }}
          />
        </Box>
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: `${THRESHOLD}%`,
            width: 2,
            height: '100%',
            bgcolor: theme.palette.warning.main,
            borderRadius: 1,
          }}
          title="Promotion threshold (90%)"
        />
      </Box>
    </Box>
  )
}
