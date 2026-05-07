import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Alert, Box, Button, CircularProgress, Typography } from '@mui/material'
import { evaluateSession, getSession, submitAnswer } from '../../api/sessions'
import AssessmentSessionView from '../../components/session/AssessmentSessionView'
import { useSessionStore } from '../../store/sessionStore'
import type { AssessmentQuestion } from '../../types/domain'

type PageState = 'loading' | 'active' | 'error' | 'all-answered'

export default function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const {
    activeSessionId,
    currentQuestionIndex,
    answers,
    setCurrentQuestionIndex,
    setAnswer,
    reset,
  } = useSessionStore()

  const resolvedSessionId = sessionId ?? activeSessionId ?? ''

  const [pageState, setPageState] = useState<PageState>('loading')
  const [questions, setQuestions] = useState<AssessmentQuestion[]>([])
  const [isEvaluating, setIsEvaluating] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)

  const { data: sessionData, isLoading, isError } = useQuery({
    queryKey: ['sessions', resolvedSessionId],
    queryFn: () => getSession(resolvedSessionId),
    enabled: !!resolvedSessionId,
    staleTime: 0,
  })

  useEffect(() => {
    if (sessionData) {
      const sorted = [...sessionData.questions].sort((a, b) => a.order - b.order)
      setQuestions(sorted)
      setCurrentQuestionIndex(sessionData.responses.length)
      setPageState('active')
    }
  }, [sessionData, setCurrentQuestionIndex])

  useEffect(() => {
    if (isError) setPageState('error')
  }, [isError])

  useEffect(() => {
    if (pageState !== 'all-answered' || isEvaluating) return
    setIsEvaluating(true)
    evaluateSession(resolvedSessionId)
      .then((result) => {
        reset()
        queryClient.invalidateQueries({ queryKey: ['sessions', resolvedSessionId] })
        navigate(`/specialist/session/${resolvedSessionId}/result`, {
          state: { levelPercentage: result.levelPercentage },
        })
      })
      .catch((err) => {
        // If session was already completed (e.g. parallel request or refresh during evaluation),
        // just navigate to results.
        if (err.response?.status === 409) {
          reset()
          navigate(`/specialist/session/${resolvedSessionId}/result`)
          return
        }
        setEvalError(t('session.evaluationError'))
        setIsEvaluating(false)
      })
  }, [pageState]) // eslint-disable-line react-hooks/exhaustive-deps

  const submitMutation = useMutation({
    mutationFn: ({ qId, text }: { qId: string; text: string }) =>
      submitAnswer(resolvedSessionId, {
        question_id: qId,
        response_text: text,
      }),
    onSuccess: (_, { qId }) => {
      const nextIndex = currentQuestionIndex + 1
      setCurrentQuestionIndex(nextIndex)
      setAnswer(qId, '')
      queryClient.invalidateQueries({ queryKey: ['sessions', resolvedSessionId] })
      if (nextIndex >= questions.length) {
        setPageState('all-answered')
      }
    },
  })

  async function handleSaveAndPause() {
    const currentQuestion = questions[currentQuestionIndex]
    const draft = answers[currentQuestion?.id] ?? ''
    if (currentQuestion && draft.trim()) {
      try {
        await submitMutation.mutateAsync({ qId: currentQuestion.id, text: draft })
      } catch (err) {
        console.error('Failed to auto-save draft on pause:', err)
      }
    }
    navigate('/specialist/matrix')
  }

  if (pageState === 'loading' && isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    )
  }

  if (pageState === 'error') {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 2 }}>
        <Alert severity="error">{t('common.genericError')}</Alert>
        <Button variant="outlined" onClick={() => navigate('/specialist/matrix')}>
          {t('session.backToMatrix')}
        </Button>
      </Box>
    )
  }

  if (pageState === 'all-answered') {
    if (evalError) {
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 2 }}>
          <Alert severity="error">{evalError}</Alert>
          <Button
            variant="contained"
            onClick={() => { setEvalError(null); setPageState('all-answered') }}
          >
            {t('session.retryEvaluation')}
          </Button>
        </Box>
      )
    }
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 2 }}>
        <CircularProgress size={48} />
        <Typography variant="h6">{t('session.evaluating')}</Typography>
        <Typography variant="body2" color="text.secondary">{t('session.evaluatingHint')}</Typography>
      </Box>
    )
  }

  if (pageState === 'active' && questions.length > 0) {
    const currentQuestion = questions[currentQuestionIndex]
    if (!currentQuestion) {
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 2 }}>
          <CircularProgress size={48} />
          <Typography variant="h6">{t('session.evaluating')}</Typography>
          <Typography variant="body2" color="text.secondary">{t('session.evaluatingHint')}</Typography>
        </Box>
      )
    }

    return (
      <AssessmentSessionView
        question={currentQuestion}
        questionIndex={currentQuestionIndex}
        totalQuestions={questions.length}
        draftAnswer={answers[currentQuestion.id] ?? ''}
        isSubmitting={submitMutation.isPending}
        submitError={submitMutation.isError ? t('common.genericError') : null}
        onAnswerChange={(text) => setAnswer(currentQuestion.id, text)}
        onSubmit={(text) => submitMutation.mutate({ qId: currentQuestion.id, text })}
        onSaveAndPause={handleSaveAndPause}
      />
    )
  }

  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <CircularProgress />
    </Box>
  )
}
