import { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, Chip, CircularProgress, Link, Typography } from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { approveMatrixProposal, getCmPending, getMatrixProposalDetail, rejectMatrixProposal } from '../../api/cm'
import SplitPanelReview from '../../components/cm/SplitPanelReview'
import { useAuth } from '../../hooks/useAuth'

export default function MatrixUpdateProposalReviewPage() {
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

  const [actionErrorMsg, setActionErrorMsg] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['cm', 'proposal', id],
    queryFn: () => getMatrixProposalDetail(id!),
    enabled: !!id,
    staleTime: 0,
  })

  async function navigateAfterDecision() {
    let nextProposalId: string | null = null
    try {
      const pending = await queryClient.fetchQuery({
        queryKey: ['cm', 'pending', cmId],
        queryFn: getCmPending,
      })
      nextProposalId = pending.updateProposals[0]?.id ?? null
    } catch {
      // fall through to dashboard
    }

    navigateTimeoutRef.current = setTimeout(() => {
      if (nextProposalId) {
        navigate(`/cm/review/update-proposal/${nextProposalId}`)
      } else {
        navigate('/cm/dashboard')
      }
    }, 1500)
  }

  const approveMutation = useMutation({
    mutationFn: () => approveMatrixProposal(id!),
    onSuccess: async () => {
      setActionErrorMsg(null)
      setActionSuccess(t('cm.proposal.approveSuccess'))
      queryClient.invalidateQueries({ queryKey: ['cm', 'proposal', id] })
      queryClient.invalidateQueries({ queryKey: ['cm', 'pending', cmId] })
      await navigateAfterDecision()
    },
    onError: (err) => {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        setActionErrorMsg(t('cm.proposal.alreadyDecided'))
        queryClient.invalidateQueries({ queryKey: ['cm', 'proposal', id] })
      } else {
        setActionErrorMsg(t('cm.proposal.approveError'))
      }
    },
  })

  const rejectMutation = useMutation({
    mutationFn: () => rejectMatrixProposal(id!),
    onSuccess: async () => {
      setActionErrorMsg(null)
      setActionSuccess(t('cm.proposal.rejectSuccess'))
      queryClient.invalidateQueries({ queryKey: ['cm', 'proposal', id] })
      queryClient.invalidateQueries({ queryKey: ['cm', 'pending', cmId] })
      await navigateAfterDecision()
    },
    onError: (err) => {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        setActionErrorMsg(t('cm.proposal.alreadyDecided'))
        queryClient.invalidateQueries({ queryKey: ['cm', 'proposal', id] })
      } else {
        setActionErrorMsg(t('cm.proposal.rejectError'))
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
        {t('cm.proposal.loadError')}
      </Alert>
    )
  }

  const isPending = approveMutation.isPending || rejectMutation.isPending

  const dateToUse = data?.sourceDate || data?.createdAt
  const daysAgo = dateToUse
    ? Math.max(0, Math.floor((Date.now() - new Date(dateToUse).getTime()) / 86_400_000))
    : 0

  const leftContent = data ? (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        {t('cm.proposal.proposedChange')}
      </Typography>
      <Typography variant="body2" sx={{ mb: 2, whiteSpace: 'pre-wrap' }}>
        {data.proposedChange}
      </Typography>

      {data.sourceDate && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          {t('cm.proposal.sourceDate')}: {new Date(data.sourceDate).toLocaleDateString()}
        </Typography>
      )}

      {data.sourceUrl && (
        <Box sx={{ mt: 1 }}>
          <Link
            href={data.sourceUrl.startsWith('http') ? data.sourceUrl : '#'}
            target="_blank"
            rel="noopener noreferrer"
            variant="body2"
          >
            {t('cm.proposal.sourceUrl')}
          </Link>
        </Box>
      )}
    </Box>
  ) : null

  const rightContent = data ? (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
        {t('cm.proposal.sourceAttribution', { source: data.sourceName, count: daysAgo })}
      </Typography>

      {actionErrorMsg && (
        <Alert severity="error" sx={{ mb: 2 }}>{actionErrorMsg}</Alert>
      )}
      {actionSuccess && (
        <Alert severity="success" sx={{ mb: 2 }}>{actionSuccess}</Alert>
      )}

      {data.isDecided ? (
        <Chip
          label={t(data.status === 'APPROVED' ? 'cm.proposal.decidedApproved' : 'cm.proposal.decidedRejected')}
          color={data.status === 'APPROVED' ? 'success' : 'error'}
          variant="outlined"
        />
      ) : (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            onClick={() => approveMutation.mutate()}
            disabled={isPending}
            startIcon={approveMutation.isPending ? <CircularProgress size={16} /> : undefined}
          >
            {t('cm.proposal.approve')}
          </Button>
          <Button
            variant="outlined"
            color="error"
            onClick={() => rejectMutation.mutate()}
            disabled={isPending}
            startIcon={rejectMutation.isPending ? <CircularProgress size={16} /> : undefined}
          >
            {t('cm.proposal.reject')}
          </Button>
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
