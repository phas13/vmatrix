import { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, Chip, CircularProgress, LinearProgress, TextField, Typography } from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios, { AxiosError } from 'axios'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { approveCmPromotion, getCmPending, getCmPromotionDetail, rejectCmPromotion } from '../../api/cm'
import SplitPanelReview from '../../components/cm/SplitPanelReview'
import { useAuth } from '../../hooks/useAuth'

function ScoreDelta({ current, previous }: { current: number, previous: number | null | undefined }) {
  if (previous == null) return null
  const diff = current - previous
  const sign = diff >= 0 ? '+' : '-'
  return (
    <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
      ({sign}{Math.abs(diff)})
    </Typography>
  )
}

export default function PromotionReviewPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const cmId = user?.id
  const navigateTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (navigateTimeoutRef.current) {
        clearTimeout(navigateTimeoutRef.current)
        navigateTimeoutRef.current = null
      }
    }
  }, [])

  const [showRejectForm, setShowRejectForm] = useState(false)
  const [rejectNote, setRejectNote] = useState('')
  const [actionErrorMsg, setActionErrorMsg] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['cm', 'promotion', id],
    queryFn: () => getCmPromotionDetail(id!),
    enabled: !!id,
    staleTime: 0,
  })

  async function navigateAfterDecision() {
    let nextPromotionId: string | null = null
    try {
      const pending = await queryClient.fetchQuery({
        queryKey: ['cm', 'pending', cmId],
        queryFn: getCmPending,
      })
      const otherPromos = pending.promotions.filter(p => p.id !== id)
      nextPromotionId = otherPromos.length > 0 ? otherPromos[0].id : null
    } catch {
      // fall through to dashboard
    }
    
    // Ensure 1.5s delay is respected regardless of query timing
    navigateTimeoutRef.current = setTimeout(() => {
      if (nextPromotionId) {
        navigate(`/cm/review/promotion/${nextPromotionId}`)
      } else {
        navigate('/cm/dashboard')
      }
    }, 1500)
  }

  const approveMutation = useMutation({
    mutationFn: () => approveCmPromotion(id!, {}),
    onSuccess: async () => {
      setActionErrorMsg(null)
      setActionSuccess(t('cm.promotion.approveSuccess'))
      queryClient.invalidateQueries({ queryKey: ['cm', 'promotion', id] })
      queryClient.invalidateQueries({ queryKey: ['cm', 'pending', cmId] })
      queryClient.invalidateQueries({ queryKey: ['cm', 'team', cmId] })
      await navigateAfterDecision()
    },
    onError: (err) => {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        setActionErrorMsg(t('cm.promotion.alreadyDecided'))
        queryClient.invalidateQueries({ queryKey: ['cm', 'promotion', id] })
      } else {
        setActionErrorMsg(t('cm.promotion.approveError'))
      }
    },
  })

  const rejectMutation = useMutation({
    mutationFn: () => rejectCmPromotion(id!, { cmNote: rejectNote.trim() || undefined }),
    onSuccess: async () => {
      setActionErrorMsg(null)
      setActionSuccess(t('cm.promotion.rejectSuccess'))
      queryClient.invalidateQueries({ queryKey: ['cm', 'promotion', id] })
      queryClient.invalidateQueries({ queryKey: ['cm', 'pending', cmId] })
      queryClient.invalidateQueries({ queryKey: ['cm', 'team', cmId] })
      await navigateAfterDecision()
    },
    onError: (err) => {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        setActionErrorMsg(t('cm.promotion.alreadyDecided'))
        queryClient.invalidateQueries({ queryKey: ['cm', 'promotion', id] })
      } else {
        setActionErrorMsg(t('cm.promotion.rejectError'))
      }
    },
  })

  if (isError) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={() => refetch()}>
            {t('common.retry')}
          </Button>
        }
      >
        {t('cm.promotion.loadError')}
      </Alert>
    )
  }

  const isPending = approveMutation.isPending || rejectMutation.isPending

  const leftContent = data ? (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Typography variant="h6">{data.specialistName}</Typography>
        {data.currentLevel && (
          <Chip label={data.currentLevel} size="small" variant="outlined" />
        )}
      </Box>

      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        {t('cm.promotion.categoryScores')}
      </Typography>
      <Box sx={{ mb: 2 }}>
        {data.categoryScores.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t('cm.promotion.notAssessed')}
          </Typography>
        ) : (
          data.categoryScores.map((cs) => (
            <Box key={cs.categoryId} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2">{cs.categoryName}</Typography>
              <Typography variant="body2">
                {cs.score ?? '—'}
                <ScoreDelta current={cs.score ?? 0} previous={cs.previousScore} />
              </Typography>
            </Box>
          ))
        )}
      </Box>

      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        {t('cm.promotion.overallProgress')}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Box sx={{ flex: 1 }}>
          <LinearProgress variant="determinate" value={data.overallPercentage} />
        </Box>
        <Typography variant="body2">{data.overallPercentage}%</Typography>
      </Box>

      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        {t('cm.promotion.sessionHistory')}
      </Typography>
      {data.sessions.items.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {t('cm.promotion.noSessions')}
        </Typography>
      ) : (
        data.sessions.items.map((s) => (
          <Box key={s.id} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="body2">{s.categoryName ?? '—'}</Typography>
            <Typography variant="body2">{s.finalScore ?? '—'}</Typography>
          </Box>
        ))
      )}
    </Box>
  ) : null

  const rightContent = data ? (
    <Box>
      <Box sx={{ mb: 2 }}>
        <Typography variant="caption" color="text.secondary">
          {t('cm.promotion.currentLevel')}
        </Typography>
        <Typography variant="h6">
          {data.currentLevel ?? '—'} → {data.nextLevel ?? '—'}
        </Typography>
      </Box>

      <Box sx={{ mb: 2 }}>
        <Typography variant="caption" color="text.secondary">
          {t('cm.promotion.threshold')}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
          <Box sx={{ flex: 1 }}>
            <LinearProgress variant="determinate" value={Math.min(data.overallPercentage, 100)} color={data.overallPercentage >= data.threshold ? 'success' : 'primary'} />
          </Box>
          <Typography variant="body2">{data.overallPercentage}% / {data.threshold}%</Typography>
        </Box>
      </Box>

      {actionErrorMsg && (
        <Alert severity="error" sx={{ mb: 2 }}>{actionErrorMsg}</Alert>
      )}
      {actionSuccess && (
        <Alert severity="success" sx={{ mb: 2 }}>{actionSuccess}</Alert>
      )}

      {data.isDecided ? (
        <Typography>
          {t(data.decision === 'approved' ? 'cm.promotion.decidedApproved' : 'cm.promotion.decidedRejected')}
        </Typography>
      ) : (
        <Box>
          {!showRejectForm && (
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <Button
                variant="contained"
                onClick={() => approveMutation.mutate()}
                disabled={isPending}
                startIcon={approveMutation.isPending ? <CircularProgress size={16} /> : undefined}
              >
                {t('cm.promotion.approve')}
              </Button>
              <Button
                variant="outlined"
                color="error"
                onClick={() => setShowRejectForm(true)}
                disabled={isPending}
              >
                {t('cm.promotion.reject')}
              </Button>
            </Box>
          )}

          {showRejectForm && (
            <Box>
              <TextField
                multiline
                rows={3}
                label={t('cm.promotion.rejectNote')}
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
                fullWidth
                sx={{ mb: 1 }}
                onKeyDown={(e) => { if (e.key === 'Enter') e.preventDefault() }}
              />
              <Button
                variant="contained"
                color="error"
                onClick={() => rejectMutation.mutate()}
                disabled={isPending}
                startIcon={rejectMutation.isPending ? <CircularProgress size={16} /> : undefined}
              >
                {t('cm.promotion.confirmReject')}
              </Button>
            </Box>
          )}
        </Box>
      )}
    </Box>
  ) : null

  return (
    <SplitPanelReview
      isLoading={isLoading}
      leftContent={leftContent}
      rightContent={rightContent}
    />
  )
}
