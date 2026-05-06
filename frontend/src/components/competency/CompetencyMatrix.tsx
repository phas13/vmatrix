import { useId, useState } from 'react'
import type { KeyboardEvent } from 'react'
import {
  Box, Button, ButtonBase, Collapse, Dialog, DialogActions, DialogContent, DialogTitle,
  Divider, IconButton, List, ListItem, Paper, TextField, Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import EditIcon from '@mui/icons-material/Edit'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlined'
import FlagIcon from '@mui/icons-material/Flag'
import FlagOutlinedIcon from '@mui/icons-material/FlagOutlined'
import AssessmentIcon from '@mui/icons-material/Assessment'
import { useTranslation } from 'react-i18next'
import type { CompetencyMatrixProps } from './CompetencyMatrix.types'

export default function CompetencyMatrix({
  categories,
  variant,
  onFlag,
  onUnflag,
  onStartAssessment,
  disabled,
  onEditSubItem,
  onRemoveSubItem,
  localEdits = {},
  localRemovals = [],
}: CompetencyMatrixProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const idPrefix = useId()
  const [flagDialog, setFlagDialog] = useState<{
    subItemId: string
    existingNote: string
  } | null>(null)
  const [noteText, setNoteText] = useState('')
  const [editDialog, setEditDialog] = useState<{
    subItemId: string
    name: string
    description: string
  } | null>(null)

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const handleKeyDown = (e: KeyboardEvent, id: string) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      toggle(id)
    }
  }

  if (categories.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 6 }}>
        <Typography color="text.secondary">{t('matrix.empty')}</Typography>
      </Box>
    )
  }

  return (
    <Box component="section" aria-label={t('matrix.ariaLabel')}>
      {categories.map((cat) => {
        const isExpanded = expanded.has(cat.id)
        const panelId = `${idPrefix}-cat-${cat.id}`
        return (
          <Paper key={cat.id} variant="outlined" sx={{ mb: 1 }}>
            <ButtonBase
              aria-expanded={isExpanded}
              aria-controls={panelId}
              onClick={() => toggle(cat.id)}
              onKeyDown={(e) => handleKeyDown(e, cat.id)}
              sx={{
                width: '100%',
                textAlign: 'left',
                display: 'flex',
                alignItems: 'center',
                px: 2,
                py: 1.5,
                '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: '-2px' },
                borderRadius: 1,
              }}
            >
              <Box sx={{ flexGrow: 1 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>{cat.name}</Typography>
                {cat.description && (
                  <Typography variant="body2" color="text.secondary">{cat.description}</Typography>
                )}
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
                {t('matrix.itemCount', { count: cat.subItems.length })}
              </Typography>
              {onStartAssessment && (
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<AssessmentIcon />}
                  sx={{ mr: 1, flexShrink: 0 }}
                  onClick={(e) => {
                    e.stopPropagation()
                    onStartAssessment(cat.id, cat.name)
                  }}
                >
                  {t('session.confirmStart')}
                </Button>
              )}
              {isExpanded ? <ExpandLessIcon aria-hidden /> : <ExpandMoreIcon aria-hidden />}
            </ButtonBase>

            <Collapse in={isExpanded} unmountOnExit>
              <Divider />
              <Box id={panelId}>
                {cat.subItems.length === 0 ? (
                  <Box sx={{ px: 4, py: 3 }}>
                    <Typography variant="body2" color="text.secondary">
                      {t('matrix.categoryEmpty')}
                    </Typography>
                  </Box>
                ) : (
                  <List dense role="list" aria-label={t('matrix.categoryItems', { name: cat.name })}>
                    {cat.subItems.map((item, itemIdx) => {
                      if (localRemovals.includes(item.id)) return null

                      const localEdit = localEdits[item.id]
                      const displayName = localEdit?.name ?? item.name
                      const displayDescription = localEdit?.description ?? item.description
                      const isLocallyEdited = !!localEdit

                      return (
                        <ListItem
                          key={item.id}
                          tabIndex={isExpanded ? 0 : -1}
                          sx={{
                            flexDirection: 'column',
                            alignItems: 'flex-start',
                            pl: 4,
                            borderBottom: itemIdx < cat.subItems.length - 1 ? '1px solid' : 'none',
                            borderColor: 'divider',
                            py: 1.5,
                          }}
                        >
                          <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', gap: 1 }}>
                            <Box sx={{ flexGrow: 1 }}>
                              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                {displayName}
                                {isLocallyEdited && (
                                  <Typography component="span" variant="caption" color="warning.main" sx={{ ml: 1 }}>
                                    {t('matrix.edited')}
                                  </Typography>
                                )}
                              </Typography>
                              <Typography variant="body2" color="text.secondary">{displayDescription}</Typography>
                            </Box>

                            {variant === 'cm-review' && (
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
                                {item.isFlagged && (
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <FlagIcon sx={{ color: 'warning.main', fontSize: 18 }} aria-hidden />
                                    {item.flagNote && (
                                      <Typography
                                        variant="caption"
                                        color="warning.main"
                                        sx={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                        title={item.flagNote}
                                      >
                                        {item.flagNote.length > 40 ? `${item.flagNote.slice(0, 40)}…` : item.flagNote}
                                      </Typography>
                                    )}
                                  </Box>
                                )}
                                {onEditSubItem && (
                                  <IconButton
                                    size="small"
                                    aria-label={t('matrix.editSubItemAriaLabel')}
                                    onClick={() => setEditDialog({ subItemId: item.id, name: displayName, description: displayDescription })}
                                  >
                                    <EditIcon sx={{ fontSize: 18 }} />
                                  </IconButton>
                                )}
                                {onRemoveSubItem && (
                                  <IconButton
                                    size="small"
                                    aria-label={t('matrix.removeSubItemAriaLabel')}
                                    color="error"
                                    onClick={() => onRemoveSubItem(item.id)}
                                  >
                                    <DeleteOutlineIcon sx={{ fontSize: 18 }} />
                                  </IconButton>
                                )}
                              </Box>
                            )}

                            {variant === 'specialist' && item.isFlagged && onUnflag && (
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
                                <FlagIcon sx={{ color: 'warning.main', fontSize: 18 }} aria-hidden />
                                {item.flagNote && (
                                  <Typography variant="caption" color="warning.main" sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {item.flagNote.length > 60 ? `${item.flagNote.slice(0, 60)}…` : item.flagNote}
                                  </Typography>
                                )}
                                <IconButton
                                  size="small"
                                  aria-label={t('matrix.unflagAriaLabel')}
                                  disabled={disabled}
                                  onClick={() => onUnflag(item.id)}
                                >
                                  <FlagIcon sx={{ color: 'warning.main', fontSize: 18 }} />
                                </IconButton>
                              </Box>
                            )}

                            {variant === 'specialist' && !item.isFlagged && onFlag && (
                              <IconButton
                                size="small"
                                aria-label={t('matrix.flagAriaLabel')}
                                disabled={disabled}
                                onClick={() => {
                                  setFlagDialog({ subItemId: item.id, existingNote: '' })
                                  setNoteText('')
                                }}
                              >
                                <FlagOutlinedIcon sx={{ fontSize: 18 }} />
                              </IconButton>
                            )}
                          </Box>
                        </ListItem>
                      )
                    })}
                  </List>
                )}
              </Box>
            </Collapse>
          </Paper>
        )
      })}

      <Dialog open={!!flagDialog} onClose={() => setFlagDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('matrix.flagDialogTitle')}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            multiline
            rows={3}
            fullWidth
            label={t('matrix.flagNoteLabel')}
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            slotProps={{ htmlInput: { maxLength: 500 } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFlagDialog(null)}>{t('common.cancel')}</Button>
          <Button
            variant="contained"
            disabled={!noteText.trim() || disabled}
            onClick={() => {
              if (flagDialog && onFlag) {
                onFlag(flagDialog.subItemId, noteText.trim())
                setFlagDialog(null)
              }
            }}
          >
            {t('matrix.flagConfirm')}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!editDialog} onClose={() => setEditDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('matrix.editSubItemDialogTitle')}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            label={t('matrix.subItemNameLabel')}
            value={editDialog?.name ?? ''}
            onChange={(e) => setEditDialog((d) => d ? { ...d, name: e.target.value } : null)}
            slotProps={{ htmlInput: { maxLength: 255 } }}
            sx={{ mb: 2, mt: 1 }}
          />
          <TextField
            multiline
            rows={3}
            fullWidth
            label={t('matrix.subItemDescriptionLabel')}
            value={editDialog?.description ?? ''}
            onChange={(e) => setEditDialog((d) => d ? { ...d, description: e.target.value } : null)}
            slotProps={{ htmlInput: { maxLength: 1000 } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialog(null)}>{t('common.cancel')}</Button>
          <Button
            variant="contained"
            disabled={!editDialog?.name.trim()}
            onClick={() => {
              if (editDialog && onEditSubItem) {
                onEditSubItem(editDialog.subItemId, editDialog.name.trim(), editDialog.description.trim())
                setEditDialog(null)
              }
            }}
          >
            {t('matrix.saveEdit')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
