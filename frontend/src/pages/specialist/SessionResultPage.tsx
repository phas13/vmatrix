import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  Alert, Box, Button, CircularProgress, Divider,
  Paper, Snackbar, TextField, Typography,
} from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { getSession, submitDispute } from '../../api/sessions'
import AssessmentResultReveal from '../../components/session/AssessmentResultReveal'
import { useSessionStore } from '../../store/sessionStore'

export default function SessionResultPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const theme = useTheme()
  const queryClient = useQueryClient()
  const { activeSessionId } = useSessionStore()

  const resolvedSessionId = sessionId ?? activeSessionId ?? ''

  const [disputeOpen, setDisputeOpen] = useState(false)
  const [disputeText, setDisputeText] = useState('')
  const [disputeSubmitting, setDisputeSubmitting] = useState(false)
  const [disputeError, setDisputeError] = useState<string | null>(null)
  const [snackbarOpen, setSnackbarOpen] = useState(false)

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

  async function handleDisputeSubmit() {
    if (!disputeText.trim()) return
    setDisputeSubmitting(true)
    setDisputeError(null)
    try {
      await submitDispute(resolvedSessionId, disputeText)
      await queryClient.invalidateQueries({ queryKey: ['sessions', resolvedSessionId] })
      setDisputeOpen(false)
      setDisputeText('')
      setSnackbarOpen(true)
    } catch (err: unknown) {
      const axiosError = err as { response?: { status?: number; data?: { detail?: { detail?: string } } } }
      const status = axiosError.response?.status
      const detail = axiosError.response?.data?.detail?.detail
      if (status === 409) {
        setDisputeError(t('session.disputeAlreadySubmitted'))
      } else if (detail) {
        setDisputeError(detail)
      } else {
        setDisputeError(t('common.genericError'))
      }
    } finally {
      setDisputeSubmitting(false)
    }
  }

  return (
    <Box sx={{ maxWidth: 800, mx: 'auto', px: 3, py: 4 }}>
      {session.finalScore !== null && session.strengths && session.areasForGrowth && (
        <AssessmentResultReveal
          score={session.finalScore}
          previousScore={session.previousScore}
          strengths={session.strengths}
          areasForGrowth={session.areasForGrowth}
          categoryName={session.categoryName ?? ''}
          levelPercentage={session.levelPercentage}
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

      {session.status === 'COMPLETED' && session.dispute === null && (
        <Box sx={{ mt: 4 }}>
          {!disputeOpen ? (
            <Button
              variant="outlined"
              color="inherit"
              size="small"
              onClick={() => setDisputeOpen(true)}
              sx={{ color: 'text.secondary', borderColor: 'divider' }}
            >
              {t('session.disputeButton')}
            </Button>
          ) : (
            <Paper elevation={0} variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
              <Typography variant="subtitle2" gutterBottom>{t('session.disputeDialogTitle')}</Typography>
              <TextField
                multiline
                fullWidth
                minRows={4}
                value={disputeText}
                onChange={(e) => setDisputeText(e.target.value)}
                placeholder={t('session.disputeExplanationPlaceholder')}
                label={t('session.disputeExplanationLabel')}
                disabled={disputeSubmitting}
              />
              {disputeError && (
                <Alert severity="error" sx={{ mt: 1 }}>{disputeError}</Alert>
              )}
              <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
                <Button
                  variant="contained"
                  onClick={handleDisputeSubmit}
                  disabled={disputeSubmitting || !disputeText.trim()}
                >
                  {disputeSubmitting ? <CircularProgress size={20} /> : t('session.disputeSubmit')}
                </Button>
                <Button
                  variant="text"
                  onClick={() => { setDisputeOpen(false); setDisputeText(''); setDisputeError(null) }}
                  disabled={disputeSubmitting}
                >
                  {t('session.cancel')}
                </Button>
              </Box>
            </Paper>
          )}
        </Box>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <Button variant="contained" onClick={() => navigate('/specialist/matrix')}>
          {t('session.backToMatrix')}
        </Button>
      </Box>

      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={() => setSnackbarOpen(false)}
        message={t('session.disputeSubmitSuccess')}
      />
    </Box>
  )
}
