import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import {
  Box,
  Button,
  Chip,
  Paper,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { getCmSpecialistDetail } from '../../api/cm'
import type { SpecialistLevel } from '../../types/domain'

const LEVEL_CHIP_COLOR: Record<string, 'default' | 'primary' | 'success'> = {
  junior: 'default',
  middle: 'primary',
  senior: 'success',
}

export default function SpecialistDetailPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { specialistId } = useParams<{ specialistId: string }>()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['cm', 'specialist', specialistId],
    queryFn: () => getCmSpecialistDetail(specialistId!),
    enabled: !!specialistId,
    staleTime: 30 * 1000,
  })

  if (isLoading) {
    return (
      <Box>
        <Skeleton variant="rectangular" height={40} sx={{ mb: 2, borderRadius: 1 }} />
        <Skeleton variant="rectangular" height={200} sx={{ mb: 2, borderRadius: 1 }} />
        <Skeleton variant="rectangular" height={200} sx={{ borderRadius: 1 }} />
      </Box>
    )
  }

  if (isError || !data) {
    return (
      <Box>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/cm/dashboard')} sx={{ mb: 2 }}>
          {t('cm.specialistDetail.back')}
        </Button>
        <Typography color="error">{t('common.genericError')}</Typography>
      </Box>
    )
  }

  const levelKey = data.specialistLevel as SpecialistLevel | null

  return (
    <Box>
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => navigate('/cm/dashboard')}
        sx={{ mb: 2 }}
      >
        {t('cm.specialistDetail.back')}
      </Button>

      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Typography variant="h5">{data.fullName}</Typography>
        <Chip
          label={t(`levels.${levelKey ?? 'unknown'}`)}
          color={LEVEL_CHIP_COLOR[levelKey ?? ''] ?? 'default'}
        />
        <Typography variant="h6" color="text.secondary">
          {t('cm.specialistDetail.overallProgress')}: {data.overallPercentage}%
        </Typography>
      </Box>

      {/* Category Scores */}
      <Paper sx={{ mb: 3, p: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>{t('cm.specialistDetail.categoryScores')}</Typography>
        {data.categoryScores.length === 0 ? (
          <Typography color="text.secondary">{t('cm.specialistDetail.notAssessed')}</Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t('cm.specialistDetail.category')}</TableCell>
                <TableCell align="right">{t('cm.specialistDetail.score')}</TableCell>
                <TableCell align="right">{t('cm.specialistDetail.previousScore')}</TableCell>
                <TableCell align="right">{t('cm.specialistDetail.lastAssessed')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.categoryScores.map((cs) => (
                <TableRow key={cs.categoryId}>
                  <TableCell>{cs.categoryName}</TableCell>
                  <TableCell align="right">{cs.score ?? '—'}</TableCell>
                  <TableCell align="right">{cs.previousScore ?? '—'}</TableCell>
                  <TableCell align="right">
                    {cs.lastAssessedAt
                      ? new Date(cs.lastAssessedAt).toLocaleDateString()
                      : t('cm.specialistDetail.notAssessed')}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>

      {/* Session History */}
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>{t('cm.specialistDetail.sessionHistory')}</Typography>
        {data.sessions.items.length === 0 ? (
          <Typography color="text.secondary">{t('cm.specialistDetail.noSessions')}</Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t('cm.specialistDetail.date')}</TableCell>
                <TableCell>{t('cm.specialistDetail.category')}</TableCell>
                <TableCell align="right">{t('cm.specialistDetail.score')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.sessions.items.map((session) => (
                <TableRow key={session.id}>
                  <TableCell>{new Date(session.createdAt).toLocaleDateString()}</TableCell>
                  <TableCell>{session.categoryName ?? '—'}</TableCell>
                  <TableCell align="right">{session.finalScore ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>
    </Box>
  )
}
