import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle,
  Skeleton, Typography,
} from '@mui/material'
import AssessmentIcon from '@mui/icons-material/Assessment'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getMatrix, generateMatrix, flagSubItem, unflagSubItem, submitMatrix } from '../../api/matrix'
import { createSessionStream } from '../../api/sessions'
import CompetencyMatrix from '../../components/competency/CompetencyMatrix'
import { useAuth } from '../../hooks/useAuth'
import { useSessionStore } from '../../store/sessionStore'

type AxiosLikeError = { response?: { status?: number } }

const MAX_QUESTIONS = 10

export default function MatrixPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const specialistId = user?.id ?? ''
  const autoTriggeredRef = useRef(false)

  const { setActiveSessionId, reset } = useSessionStore()

  const [confirmCategory, setConfirmCategory] = useState<{ id: string; name: string } | null>(null)
  const [isStartingSession, setIsStartingSession] = useState(false)
  const [sessionStartError, setSessionStartError] = useState<string | null>(null)

  const {
    data: matrix,
    isLoading: isFetching,
    error: fetchError,
  } = useQuery({
    queryKey: ['matrix', specialistId],
    queryFn: () => getMatrix(specialistId),
    retry: (failureCount, error: unknown) => {
      const axiosError = error as AxiosLikeError
      if (axiosError?.response?.status === 404) return false
      return failureCount < 2
    },
    enabled: !!specialistId,
    staleTime: 5 * 60 * 1000,
  })

  const generateMutation = useMutation({
    mutationFn: () => generateMatrix(specialistId),
    onSuccess: (data) => {
      queryClient.setQueryData(['matrix', specialistId], data)
    },
  })

  const flagMutation = useMutation({
    mutationFn: ({ subItemId, note }: { subItemId: string; note: string }) =>
      flagSubItem(specialistId, subItemId, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matrix', specialistId] })
    },
  })

  const unflagMutation = useMutation({
    mutationFn: (subItemId: string) => unflagSubItem(specialistId, subItemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matrix', specialistId] })
    },
  })

  const submitMutation = useMutation({
    mutationFn: () => submitMatrix(specialistId),
    onSuccess: (data) => {
      queryClient.setQueryData(['matrix', specialistId], data)
    },
  })

  useEffect(() => {
    if (!specialistId) return
    if (autoTriggeredRef.current) return
    const axiosError = fetchError as AxiosLikeError | null
    const is404 = axiosError?.response?.status === 404
    if (is404) {
      autoTriggeredRef.current = true
      generateMutation.mutate()
    }
  }, [fetchError, specialistId])

  async function handleStartSession() {
    if (!confirmCategory) return
    setIsStartingSession(true)
    setSessionStartError(null)
    try {
      reset()
      const result = await createSessionStream(confirmCategory.id)
      setActiveSessionId(result.sessionId)
      setConfirmCategory(null)
      navigate(`/specialist/session/${result.sessionId}`)
    } catch {
      setSessionStartError(t('session.startError'))
    } finally {
      setIsStartingSession(false)
    }
  }

  const fetchAxiosError = fetchError as AxiosLikeError | null
  const isFetchErrorNon404 =
    !!fetchError && fetchAxiosError?.response?.status !== 404

  const displayMatrix = matrix ?? generateMutation.data
  const isGenerating = generateMutation.isPending
  const isInitialLoading = isFetching && !matrix

  if (isInitialLoading || isGenerating) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>{t('matrix.title')}</Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          {isGenerating ? t('matrix.generating') : t('matrix.loading')}
        </Typography>
        <Skeleton variant="rectangular" height={64} sx={{ mb: 1, borderRadius: 1 }} />
        <Skeleton variant="rectangular" height={64} sx={{ mb: 1, borderRadius: 1 }} />
        <Skeleton variant="rectangular" height={64} sx={{ borderRadius: 1 }} />
      </Box>
    )
  }

  if (isFetchErrorNon404) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>{t('matrix.title')}</Typography>
        <Alert
          severity="error"
          action={
            <Button
              color="inherit"
              size="small"
              onClick={() => queryClient.invalidateQueries({ queryKey: ['matrix', specialistId] })}
            >
              {t('matrix.retry')}
            </Button>
          }
        >
          {t('matrix.fetchError')}
        </Alert>
      </Box>
    )
  }

  if (generateMutation.isError) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>{t('matrix.title')}</Typography>
        <Alert
          severity="error"
          action={
            <Button
              color="inherit"
              size="small"
              onClick={() => {
                if (!specialistId) return
                generateMutation.mutate()
              }}
            >
              {t('matrix.retry')}
            </Button>
          }
        >
          {t('matrix.generateError')}
        </Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 1 }}>{t('matrix.title')}</Typography>
      {displayMatrix && (
        <>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
            <Typography variant="body2" color="text.secondary">
              {t('matrix.domainLabel', { domain: displayMatrix.domain })}
            </Typography>
            <Chip
              label={t(`matrix.status.${displayMatrix.status}`)}
              size="small"
              color={
                displayMatrix.status === 'APPROVED' ? 'success' :
                displayMatrix.status === 'PENDING_APPROVAL' ? 'warning' : 'default'
              }
            />
          </Box>

          {displayMatrix.status === 'PENDING_REVIEW' && (
            <Box sx={{ mb: 3, display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="contained"
                onClick={() => submitMutation.mutate()}
                disabled={submitMutation.isPending}
              >
                {submitMutation.isPending
                  ? t('matrix.submitting')
                  : t('matrix.submitForReview')}
              </Button>
            </Box>
          )}

          {displayMatrix.status === 'PENDING_APPROVAL' && (
            <Box sx={{ mb: 3 }}>
              <Alert severity="info">{t('matrix.status.PENDING_APPROVAL')}</Alert>
            </Box>
          )}

          {submitMutation.isError && (
            <Box sx={{ mb: 2 }}>
              <Alert severity="error">{t('matrix.submitError')}</Alert>
            </Box>
          )}

          <CompetencyMatrix
            categories={displayMatrix.categories}
            variant="specialist"
            disabled={
              flagMutation.isPending ||
              unflagMutation.isPending ||
              displayMatrix.status !== 'PENDING_REVIEW'
            }
            onFlag={
              displayMatrix.status === 'PENDING_REVIEW'
                ? (subItemId, note) => flagMutation.mutate({ subItemId, note })
                : undefined
            }
            onUnflag={
              displayMatrix.status === 'PENDING_REVIEW'
                ? (subItemId) => unflagMutation.mutate(subItemId)
                : undefined
            }
            onStartAssessment={
              displayMatrix.status === 'APPROVED'
                ? (categoryId, categoryName) => setConfirmCategory({ id: categoryId, name: categoryName })
                : undefined
            }
          />
        </>
      )}

      {/* Confirmation dialog */}
      <Dialog open={!!confirmCategory} onClose={() => !isStartingSession && setConfirmCategory(null)} maxWidth="xs" fullWidth>
        <DialogTitle>{t('session.confirmTitle')}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, pt: 1 }}>
            <Typography variant="body2">
              <strong>{t('session.confirmCategory')}:</strong> {confirmCategory?.name}
            </Typography>
            <Typography variant="body2">
              <strong>{t('session.confirmLevel')}:</strong> {user?.specialistLevel ?? '—'}
            </Typography>
            <Typography variant="body2">
              {t('session.confirmEstimate', {
                minutes: MAX_QUESTIONS * 2,
                questions: MAX_QUESTIONS,
              })}
            </Typography>
            {sessionStartError && (
              <Alert severity="error" sx={{ mt: 1 }}>{sessionStartError}</Alert>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmCategory(null)} disabled={isStartingSession}>
            {t('session.cancel')}
          </Button>
          <Button
            variant="contained"
            startIcon={<AssessmentIcon />}
            onClick={handleStartSession}
            disabled={isStartingSession}
          >
            {isStartingSession ? t('common.loading') : t('session.confirmStart')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
