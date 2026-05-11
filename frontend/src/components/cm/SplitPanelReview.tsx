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
  const focusedRef = useRef(false)

  useEffect(() => {
    if (isLoading || focusedRef.current || !rightPanelRef.current) return

    const focusables = Array.from(
      rightPanelRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      ),
    ).filter(
      (el) =>
        !el.hasAttribute('disabled')
        && el.getAttribute('aria-hidden') !== 'true',
    )

    if (focusables.length > 0) {
      focusables[0].focus()
      focusedRef.current = true
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
