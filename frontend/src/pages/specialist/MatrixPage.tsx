import { useEffect, useRef } from 'react'
import { Alert, Box, Button, Skeleton, Typography } from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getMatrix, generateMatrix } from '../../api/matrix'
import CompetencyMatrix from '../../components/competency/CompetencyMatrix'
import { useAuth } from '../../hooks/useAuth'

type AxiosLikeError = { response?: { status?: number } }

export default function MatrixPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const specialistId = user?.id ?? ''
  const autoTriggeredRef = useRef(false)

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
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            {t('matrix.domainLabel', { domain: displayMatrix.domain })}
          </Typography>
          <CompetencyMatrix
            categories={displayMatrix.categories}
            variant="specialist"
          />
        </>
      )}
    </Box>
  )
}
