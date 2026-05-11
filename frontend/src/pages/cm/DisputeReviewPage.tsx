import { useState } from 'react'
import { Alert, Box, Button, CircularProgress, TextField, Typography } from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { getCmDisputeDetail, resolveCmDispute } from '../../api/cm'
import SplitPanelReview from '../../components/cm/SplitPanelReview'
import { useAuth } from '../../hooks/useAuth'
import type { DisputeDecision, DisputeTranscriptItem } from '../../types/domain'

function TranscriptItem({ item, index }: { item: DisputeTranscriptItem; index: number }) {
  const { t } = useTranslation()
  return (
    <Box sx={{ mb: 2, p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
      <Typography variant="subtitle2" color="text.secondary">
        {t('cm.dispute.questionLabel', { num: index + 1 })} — {item.questionType}
      </Typography>
      <Typography variant="body1" sx={{ mt: 0.5, fontWeight: 500 }}>
        {item.questionText}
      </Typography>
      {item.responseText && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {t('cm.dispute.responseLabel')}
          </Typography>
          <Typography variant="body2">{item.responseText}</Typography>
        </Box>
      )}
      {item.aiRationale && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {t('cm.dispute.aiRationaleLabel')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {item.aiRationale}
          </Typography>
        </Box>
      )}
    </Box>
  )
}

export default function DisputeReviewPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const cmId = user?.id

  const [decision, setDecision] = useState<DisputeDecision | null>(null)
  const [cmNote, setCmNote] = useState('')
  const [overrideScore, setOverrideScore] = useState<number | ''>('')

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['cm', 'dispute', id],
    queryFn: () => getCmDisputeDetail(id!),
    enabled: !!id,
    staleTime: 0,
  })

  const mutation = useMutation({
    mutationFn: (req: Parameters<typeof resolveCmDispute>[1]) => resolveCmDispute(id!, req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cm', 'pending', cmId] })
      setTimeout(() => navigate('/cm/dashboard'), 1500)
    },
  })

  function handleSubmit() {
    if (!decision) return
    if (decision === 'upheld') {
      mutation.mutate({ decision: 'upheld' })
    } else {
      mutation.mutate({
        decision: 'overridden',
        cmNote: cmNote.trim(),
        overrideScore: Number(overrideScore),
      })
    }
  }

  if (isError) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={() => refetch()}>
            {t('common.genericError')}
          </Button>
        }
      >
        {t('cm.dispute.loadError')}
      </Alert>
    )
  }

  const sortedTranscript = data
    ? [...data.transcript].sort((a, b) => a.order - b.order)
    : []

  const leftContent = data ? (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        {data.specialistName} — {data.categoryName}
      </Typography>
      {sortedTranscript.map((item, idx) => (
        <TranscriptItem key={item.questionId} item={item} index={idx} />
      ))}
      <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2">{t('cm.dispute.specialistExplanation')}</Typography>
        <Typography variant="body2">{data.specialistExplanation}</Typography>
      </Box>
    </Box>
  ) : null

  const rightContent = data ? (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {t('cm.dispute.aiScore')}
      </Typography>
      <Typography variant="h4" sx={{ mb: 2 }}>
        {data.aiScore ?? '—'}
      </Typography>

      {data.status === 'resolved' ? (
        <Box>
          <Typography>
            {data.cmDecision === 'upheld'
              ? t('cm.dispute.resolvedUphold')
              : t('cm.dispute.resolvedOverride')}
          </Typography>
          {data.cmDecision === 'overridden' && data.cmNote && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              {t('cm.dispute.overrideNote')}: {data.cmNote}
            </Typography>
          )}
        </Box>
      ) : (
        <Box>
          {!decision && (
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <Button
                variant="outlined"
                onClick={() => setDecision('upheld')}
                disabled={mutation.isPending}
              >
                {t('cm.dispute.uphold')}
              </Button>
              <Button
                variant="outlined"
                color="error"
                onClick={() => setDecision('overridden')}
                disabled={mutation.isPending}
              >
                {t('cm.dispute.override')}
              </Button>
            </Box>
          )}

          {decision === 'overridden' && (
            <Box sx={{ mb: 2 }}>
              <TextField
                type="number"
                label={t('cm.dispute.overrideScore')}
                value={overrideScore}
                onChange={(e) => setOverrideScore(e.target.value === '' ? '' : Number(e.target.value))}
                inputProps={{ min: 0, max: 100 }}
                required
                fullWidth
                sx={{ mb: 1 }}
                onKeyDown={(e) => { if (e.key === 'Enter') e.preventDefault() }}
              />
              <TextField
                multiline
                rows={4}
                label={t('cm.dispute.overrideNote')}
                value={cmNote}
                onChange={(e) => setCmNote(e.target.value)}
                required
                fullWidth
                onKeyDown={(e) => { if (e.key === 'Enter') e.preventDefault() }}
              />
            </Box>
          )}

          {decision === 'upheld' && (
            <Button
              variant="contained"
              onClick={handleSubmit}
              disabled={mutation.isPending}
              startIcon={mutation.isPending ? <CircularProgress size={16} /> : undefined}
            >
              {t('cm.dispute.confirmUphold')}
            </Button>
          )}

          {decision === 'overridden' && (
            <Button
              variant="contained"
              color="error"
              onClick={handleSubmit}
              disabled={mutation.isPending || !cmNote.trim() || overrideScore === ''}
              startIcon={mutation.isPending ? <CircularProgress size={16} /> : undefined}
            >
              {t('cm.dispute.confirmOverride')}
            </Button>
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
