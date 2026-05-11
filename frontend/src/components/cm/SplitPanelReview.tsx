import React, { useEffect, useRef } from 'react'
import { Box, Skeleton, useTheme } from '@mui/material'

interface SplitPanelReviewProps {
  leftContent: React.ReactNode
  rightContent: React.ReactNode
  isLoading: boolean
}

function SplitPanelReview({ leftContent, rightContent, isLoading }: SplitPanelReviewProps) {
  const theme = useTheme()
  const rightPanelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isLoading && rightPanelRef.current) {
      const firstFocusable = rightPanelRef.current.querySelector<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      firstFocusable?.focus()
    }
  }, [isLoading])

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          gap: 2,
          alignItems: 'flex-start',
          [theme.breakpoints.down('lg')]: { flexDirection: 'column' },
        }}
      >
        <Box sx={{ flex: '0 0 60%', [theme.breakpoints.down('lg')]: { flex: '0 0 100%' } }}>
          <Skeleton variant="rectangular" height={80} sx={{ mb: 1 }} />
          <Skeleton variant="rectangular" height={80} sx={{ mb: 1 }} />
          <Skeleton variant="rectangular" height={80} sx={{ mb: 1 }} />
        </Box>
        <Box sx={{ flex: '0 0 40%', [theme.breakpoints.down('lg')]: { flex: '0 0 100%' } }}>
          <Skeleton variant="rectangular" height={80} sx={{ mb: 1 }} />
          <Skeleton variant="rectangular" height={80} sx={{ mb: 1 }} />
          <Skeleton variant="rectangular" height={80} sx={{ mb: 1 }} />
        </Box>
      </Box>
    )
  }

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 2,
        alignItems: 'flex-start',
        [theme.breakpoints.down('lg')]: { flexDirection: 'column' },
      }}
    >
      <Box
        sx={{
          flex: '0 0 60%',
          overflowY: 'auto',
          maxHeight: 'calc(100vh - 160px)',
          [theme.breakpoints.down('lg')]: { flex: '0 0 100%' },
        }}
      >
        {leftContent}
      </Box>
      <Box
        ref={rightPanelRef}
        sx={{
          flex: '0 0 40%',
          position: 'sticky',
          top: 16,
          [theme.breakpoints.down('lg')]: { flex: '0 0 100%' },
        }}
      >
        {rightContent}
      </Box>
    </Box>
  )
}

export default SplitPanelReview
