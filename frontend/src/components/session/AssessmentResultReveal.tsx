import { useEffect, useState } from 'react'
import { Box, Chip, Paper, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { useTranslation } from 'react-i18next'

interface Props {
  score: number
  previousScore: number | null
  strengths: string
  areasForGrowth: string
  categoryName: string
  levelPercentage: number
}

export default function AssessmentResultReveal({
  score, previousScore, strengths, areasForGrowth, categoryName, levelPercentage,
}: Props) {
  const { t } = useTranslation()
  const theme = useTheme()
  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const [visibleSections, setVisibleSections] = useState<number>(
    prefersReducedMotion ? 3 : 0
  )

  useEffect(() => {
    if (prefersReducedMotion) return
    const timers = [
      setTimeout(() => setVisibleSections(1), 0),
      setTimeout(() => setVisibleSections(2), 300),
      setTimeout(() => setVisibleSections(3), 600),
    ]
    return () => timers.forEach(clearTimeout)
  }, [prefersReducedMotion])

  const scoreDelta = previousScore !== null ? score - previousScore : null
  const deltaLabel = scoreDelta !== null
    ? (scoreDelta >= 0 ? `+${scoreDelta}%` : `${scoreDelta}%`)
    : null

  return (
    <Box aria-live="polite" role="region" aria-label={t('session.resultAriaLabel')}>
      {visibleSections >= 1 && (
        <Paper
          elevation={0}
          sx={{ p: 3, mb: 2, border: `1px solid ${theme.palette.success.light}`, borderRadius: 2 }}
        >
          <Typography variant="overline" color="success.main" sx={{ fontWeight: 600 }}>
            {t('session.strengths')}
          </Typography>
          <Typography variant="body1" sx={{ mt: 1 }}>{strengths}</Typography>
        </Paper>
      )}

      {visibleSections >= 2 && (
        <Paper
          elevation={0}
          sx={{ p: 3, mb: 2, border: `1px solid ${theme.palette.warning.light}`, borderRadius: 2 }}
        >
          <Typography variant="overline" color="warning.main" sx={{ fontWeight: 600 }}>
            {t('session.areasForGrowth')}
          </Typography>
          <Typography variant="body1" sx={{ mt: 1 }}>{areasForGrowth}</Typography>
        </Paper>
      )}

      {visibleSections >= 3 && (
        <Paper
          elevation={0}
          sx={{ p: 3, border: `1px solid ${theme.palette.primary.light}`, borderRadius: 2 }}
        >
          <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>
            {t('session.score')}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 2, mt: 1 }}>
            <Typography variant="h3" color="primary.main">{score}%</Typography>
            {deltaLabel && (
              <Chip
                label={deltaLabel}
                size="small"
                color={scoreDelta! >= 0 ? 'success' : 'error'}
                variant="outlined"
              />
            )}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {t('session.categoryProgress', { category: categoryName })}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t('session.overallLevelPercentage', { percentage: levelPercentage })}
          </Typography>
        </Paper>
      )}
    </Box>
  )
}
