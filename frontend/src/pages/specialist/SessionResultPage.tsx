import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Alert, Box, Button, CircularProgress, Divider, Paper, Typography } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { getSession } from '../../api/sessions'
import AssessmentResultReveal from '../../components/session/AssessmentResultReveal'
import { useSessionStore } from '../../store/sessionStore'

interface LocationState {
  levelPercentage?: number
}

export default function SessionResultPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const theme = useTheme()
  const location = useLocation()
  const { activeSessionId } = useSessionStore()

  const resolvedSessionId = sessionId ?? activeSessionId ?? ''
  const locationState = (location.state ?? {}) as LocationState
  const levelPercentage = locationState.levelPercentage ?? 0

  const { data: session, isLoading, isError } = useQuery({
    queryKey: ['sessions', resolvedSessionId],
    queryFn: () => getSession(resolvedSessionId),
    enabled: !!resolvedSessionId,
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    )
  }

  if (isError || !session) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 2 }}>
        <Alert severity="error">{t('common.genericError')}</Alert>
        <Button variant="outlined" onClick={() => navigate('/specialist/matrix')}>
          {t('session.backToMatrix')}
        </Button>
      </Box>
    )
  }

  const sortedQuestions = [...session.questions].sort((a, b) => a.order - b.order)
  const responseMap = Object.fromEntries(session.responses.map(r => [r.questionId, r]))

  return (
    <Box sx={{ maxWidth: 800, mx: 'auto', px: 3, py: 4 }}>
      {session.finalScore !== null && session.strengths && session.areasForGrowth && (
        <AssessmentResultReveal
          score={session.finalScore}
          previousScore={session.previousScore}
          strengths={session.strengths}
          areasForGrowth={session.areasForGrowth}
          categoryName={''}
          levelPercentage={levelPercentage}
        />
      )}

      <Divider sx={{ my: 4 }} />

      <Typography variant="h6" gutterBottom>{t('session.reviewTitle')}</Typography>
      {sortedQuestions.map((q, idx) => {
        const resp = responseMap[q.id]
        return (
          <Paper key={q.id} elevation={0} variant="outlined" sx={{ p: 3, mb: 2, borderRadius: 2 }}>
            <Typography variant="caption" color="text.secondary">
              {t('session.questionProgress', { current: idx + 1, total: sortedQuestions.length })}
              {' · '}
              {t(`session.questionType.${q.questionType}`)}
            </Typography>
            <Typography variant="body1" sx={{ mt: 1, fontWeight: 500 }}>{q.text}</Typography>
            {resp && (
              <>
                <Typography variant="body2" sx={{ mt: 2 }}>{resp.responseText}</Typography>
                {resp.aiRationale && (
                  <Box sx={{ mt: 2, pl: 2, borderLeft: `3px solid ${theme.palette.primary.light}` }}>
                    <Typography variant="body2" color="text.secondary">
                      {t('session.aiCommentaryPrefix')} {resp.aiRationale}
                    </Typography>
                  </Box>
                )}
              </>
            )}
          </Paper>
        )
      })}

      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <Button variant="contained" onClick={() => navigate('/specialist/matrix')}>
          {t('session.backToMatrix')}
        </Button>
      </Box>
    </Box>
  )
}
