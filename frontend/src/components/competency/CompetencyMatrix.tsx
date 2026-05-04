import { useId, useState } from 'react'
import type { KeyboardEvent } from 'react'
import {
  Box, Button, Collapse, Dialog, DialogActions, DialogContent, DialogTitle,
  Divider, IconButton, List, ListItem, Paper, TextField, Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import FlagIcon from '@mui/icons-material/Flag'
import FlagOutlinedIcon from '@mui/icons-material/FlagOutlined'
import { useTranslation } from 'react-i18next'
import type { CompetencyMatrixProps } from './CompetencyMatrix.types'

export default function CompetencyMatrix({
  categories,
  variant,
  onFlag,
  onUnflag,
  disabled,
}: CompetencyMatrixProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const idPrefix = useId()
  const [flagDialog, setFlagDialog] = useState<{
    subItemId: string
    existingNote: string
  } | null>(null)
  const [noteText, setNoteText] = useState('')

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
            <Box
              role="button"
              tabIndex={0}
              aria-expanded={isExpanded}
              aria-controls={panelId}
              onClick={() => toggle(cat.id)}
              onKeyDown={(e) => handleKeyDown(e, cat.id)}
              sx={{
                display: 'flex',
                alignItems: 'center',
                px: 2,
                py: 1.5,
                cursor: 'pointer',
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
              {isExpanded ? <ExpandLessIcon aria-hidden /> : <ExpandMoreIcon aria-hidden />}
            </Box>

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
                    {cat.subItems.map((item, itemIdx) => (
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
                            <Typography variant="body2" sx={{ fontWeight: 500 }}>{item.name}</Typography>
                            <Typography variant="body2" color="text.secondary">{item.description}</Typography>
                          </Box>

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
                    ))}
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
    </Box>
  )
}
