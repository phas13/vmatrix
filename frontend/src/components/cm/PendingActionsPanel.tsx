import { Box, Button, Chip, Skeleton, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { Link as RouterLink } from 'react-router-dom'
import type { PendingAction, PendingActionType, PendingActionsData } from '../../types/domain'

interface Props {
  data: PendingActionsData | undefined
  isLoading: boolean
}

const TYPE_PALETTE_KEY: Record<PendingActionType, string> = {
  dispute: 'error.main',
  promotion: 'success.main',
  matrix_approval: 'info.main',
  update_proposal: 'action.disabled',
}

function reviewPath(action: PendingAction): string {
  return `/cm/review/${action.type.replace(/_/g, '-')}/${action.id}`
}

interface GroupProps {
  type: PendingActionType
  items: PendingAction[]
  label: string
}

function ActionGroup({ type, items, label }: GroupProps) {
  const { t, i18n } = useTranslation()
  const paletteKey = TYPE_PALETTE_KEY[type] || 'action.disabled'

  return (
    <Box sx={{ mb: 2 }}>
      <Typography
        role="heading"
        aria-level={2}
        variant="subtitle1"
        sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}
      >
        {label}
        <Chip label={items.length} size="small" />
      </Typography>
      {items.map((item) => (
        <Box
          key={`${item.type}-${item.id}`}
          sx={{
            borderLeft: '4px solid',
            borderColor: paletteKey,
            pl: 2,
            mb: 1,
            py: 1,
          }}
        >
          <Typography variant="body2" fontWeight={500}>{item.specialistName}</Typography>
          <Typography variant="body2" color="text.secondary">{item.description}</Typography>
          <Typography variant="caption" color="text.secondary">
            {new Date(item.date).toLocaleDateString(i18n.language)}
          </Typography>
          <Box sx={{ mt: 0.5 }}>
            <Button
              component={RouterLink}
              to={reviewPath(item)}
              size="small"
              variant="outlined"
            >
              {t('cm.pending.review')}
            </Button>
          </Box>
        </Box>
      ))}
    </Box>
  )
}

export default function PendingActionsPanel({ data, isLoading }: Props) {
  const { t } = useTranslation()

  if (isLoading) {
    return (
      <Box>
        <Skeleton variant="rectangular" height={72} sx={{ mb: 1, borderRadius: 1 }} />
        <Skeleton variant="rectangular" height={72} sx={{ mb: 1, borderRadius: 1 }} />
        <Skeleton variant="rectangular" height={72} sx={{ mb: 1, borderRadius: 1 }} />
      </Box>
    )
  }

  const itemCount = data
    ? data.disputes.length
      + data.promotions.length
      + data.matrixApprovals.length
      + data.updateProposals.length
    : 0

  if (!data || itemCount === 0) {
    return (
      <Typography color="text.secondary">
        {t('cm.pending.allCaughtUp')}
      </Typography>
    )
  }

  return (
    <Box>
      {data.disputes.length > 0 && (
        <ActionGroup
          type="dispute"
          items={data.disputes}
          label={t('cm.pending.groupLabel.dispute')}
        />
      )}
      {data.promotions.length > 0 && (
        <ActionGroup
          type="promotion"
          items={data.promotions}
          label={t('cm.pending.groupLabel.promotion')}
        />
      )}
      {data.matrixApprovals.length > 0 && (
        <ActionGroup
          type="matrix_approval"
          items={data.matrixApprovals}
          label={t('cm.pending.groupLabel.matrix_approval')}
        />
      )}
      {data.updateProposals.length > 0 ? (
        <ActionGroup
          type="update_proposal"
          items={data.updateProposals}
          label={t('cm.pending.groupLabel.update_proposal')}
        />
      ) : (
        <Box sx={{ mb: 2 }}>
          <Typography role="heading" aria-level={2} variant="subtitle1" sx={{ mb: 0.5 }}>
            {t('cm.pending.groupLabel.update_proposal')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t('cm.pending.proposalsCurrent')}
          </Typography>
        </Box>
      )}
    </Box>
  )
}
