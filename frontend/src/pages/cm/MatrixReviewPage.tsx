import { useState } from 'react'
import { Alert, Box, Button, Chip, Skeleton, Typography } from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { getMatrix, approveMatrix } from '../../api/matrix'
import type { MatrixApprovePayload } from '../../api/matrix'
import CompetencyMatrix from '../../components/competency/CompetencyMatrix'
import { useAuth } from '../../hooks/useAuth'

export default function MatrixReviewPage() {
  const { t } = useTranslation()
  const { specialistId = '' } = useParams<{ specialistId: string }>()
  const { user } = useAuth()
  const cmId = user?.id ?? ''
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [localEdits, setLocalEdits] = useState<Record<string, { name: string; description: string }>>({})
  const [localRemovals, setLocalRemovals] = useState<string[]>([])

  const { data: matrix, isLoading, error } = useQuery({
    queryKey: ['matrix', specialistId],
    queryFn: () => getMatrix(specialistId),
    enabled: !!specialistId,
    staleTime: 5 * 60 * 1000,
  })

  const approveMutation = useMutation({
    mutationFn: (payload: MatrixApprovePayload) => approveMatrix(specialistId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matrix', specialistId] })
      queryClient.invalidateQueries({ queryKey: ['cm', 'team', cmId] })
      navigate('/cm/dashboard')
    },
  })

  const handleEditSubItem = (subItemId: string, name: string, description: string) => {
    setLocalEdits((prev) => ({ ...prev, [subItemId]: { name, description } }))
  }

  const handleRemoveSubItem = (subItemId: string) => {
    setLocalRemovals((prev) => Array.from(new Set([...prev, subItemId])))
    setLocalEdits((prev) => {
      const next = { ...prev }
      delete next[subItemId]
      return next
    })
  }

  const handleApprove = () => {
    const payload: MatrixApprovePayload = {
      sub_item_edits: Object.entries(localEdits).map(([id, edit]) => ({
        id,
        name: edit.name,
        description: edit.description,
      })),
      sub_items_to_remove: localRemovals,
    }
    approveMutation.mutate(payload)
  }

  if (isLoading) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>{t('cm.matrixReview.title')}</Typography>
        <Skeleton variant="rectangular" height={64} sx={{ mb: 1, borderRadius: 1 }} />
        <Skeleton variant="rectangular" height={64} sx={{ mb: 1, borderRadius: 1 }} />
      </Box>
    )
  }

  if (error || !matrix) {
    const errorMessage = (error as any)?.response?.data?.detail?.detail || t('matrix.fetchError')
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>{t('cm.matrixReview.title')}</Typography>
        <Alert severity="error">{errorMessage}</Alert>
      </Box>
    )
  }

  const hasChanges = Object.keys(localEdits).length > 0 || localRemovals.length > 0

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 1 }}>{t('cm.matrixReview.title')}</Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Typography variant="body2" color="text.secondary">
          {t('matrix.domainLabel', { domain: matrix.domain })}
        </Typography>
        <Chip
          label={t(`matrix.status.${matrix.status}`)}
          size="small"
          color={matrix.status === 'APPROVED' ? 'success' : matrix.status === 'PENDING_APPROVAL' ? 'warning' : 'default'}
        />
      </Box>

      {matrix.status === 'APPROVED' && (
        <Alert severity="success" sx={{ mb: 3 }}>{t('cm.matrixReview.alreadyApproved')}</Alert>
      )}

      {matrix.status === 'PENDING_APPROVAL' && (
        <>
          <Box sx={{ mb: 3, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
            {hasChanges && (
              <Button
                variant="outlined"
                onClick={() => { setLocalEdits({}); setLocalRemovals([]) }}
              >
                {t('cm.matrixReview.discardChanges')}
              </Button>
            )}
            <Button
              variant="contained"
              onClick={handleApprove}
              disabled={approveMutation.isPending}
            >
              {approveMutation.isPending ? t('cm.matrixReview.approving') : t('cm.matrixReview.approve')}
            </Button>
          </Box>

          {approveMutation.isError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {(approveMutation.error as any)?.response?.data?.detail?.detail || t('cm.matrixReview.approveError')}
            </Alert>
          )}
        </>
      )}

      <CompetencyMatrix
        categories={matrix.categories}
        variant={matrix.status === 'PENDING_APPROVAL' ? 'cm-review' : 'specialist'}
        localEdits={localEdits}
        localRemovals={localRemovals}
        onEditSubItem={matrix.status === 'PENDING_APPROVAL' ? handleEditSubItem : undefined}
        onRemoveSubItem={matrix.status === 'PENDING_APPROVAL' ? handleRemoveSubItem : undefined}
      />
    </Box>
  )
}
