import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Box, Button, CircularProgress, Typography, Alert } from '@mui/material'
import { getSession, submitAnswer } from '../../api/sessions'
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
  } = useSessionStore()

  const resolvedSessionId = sessionId ?? activeSessionId ?? ''

  const [pageState, setPageState] = useState<PageState>('loading')
  const [questions, setQuestions] = useState<AssessmentQuestion[]>([])

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
      // Sync current index based on persisted responses
      setCurrentQuestionIndex(sessionData.responses.length)
      setPageState('active')
    }
  }, [sessionData, setCurrentQuestionIndex])

  useEffect(() => {
    if (isError) setPageState('error')
  }, [isError])

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
        // Even if submission fails, we still navigate away to respect user intent to pause,
        // but the draft remains in local store (sessionStorage) for next time.
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
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 2 }}>
        <CircularProgress />
        <Typography>{t('session.allAnswered')}</Typography>
      </Box>
    )
  }

  if (pageState === 'active' && questions.length > 0) {
    const currentQuestion = questions[currentQuestionIndex]
    if (!currentQuestion) {
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 2 }}>
          <CircularProgress />
          <Typography>{t('session.allAnswered')}</Typography>
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
