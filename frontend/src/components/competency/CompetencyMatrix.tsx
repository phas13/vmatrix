import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import {
  Box, Collapse, Divider, List, ListItem, Paper, Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import { useTranslation } from 'react-i18next'
import type { CompetencyMatrixProps } from './CompetencyMatrix.types'

export default function CompetencyMatrix({ categories, variant: _variant }: CompetencyMatrixProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

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
        return (
          <Paper key={cat.id} variant="outlined" sx={{ mb: 1 }}>
            <Box
              role="button"
              tabIndex={0}
              aria-expanded={isExpanded}
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
              {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </Box>

            <Collapse in={isExpanded} unmountOnExit>
              <Divider />
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
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>{item.name}</Typography>
                    <Typography variant="body2" color="text.secondary">{item.description}</Typography>
                  </ListItem>
                ))}
              </List>
            </Collapse>
          </Paper>
        )
      })}
    </Box>
  )
}
