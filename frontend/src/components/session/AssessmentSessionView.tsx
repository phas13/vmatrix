import { Box, Button, LinearProgress, TextField, Typography, Chip } from '@mui/material'
import PauseIcon from '@mui/icons-material/Pause'
import { useTranslation } from 'react-i18next'
import { useTheme } from '@mui/material/styles'
import type { AssessmentQuestion } from '../../types/domain'

interface Props {
  question: AssessmentQuestion
  questionIndex: number
  totalQuestions: number
  draftAnswer: string
  isSubmitting: boolean
  submitError: string | null
  onAnswerChange: (text: string) => void
  onSubmit: (text: string) => void
  onSaveAndPause: () => void
}

export default function AssessmentSessionView({
  question, questionIndex, totalQuestions, draftAnswer,
  isSubmitting, submitError, onAnswerChange, onSubmit, onSaveAndPause,
}: Props) {
  const { t } = useTranslation()
  const theme = useTheme()

  const progress = (questionIndex / totalQuestions) * 100

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: theme.palette.background.default,
      }}
    >
      <Box
        sx={{
          px: 3,
          py: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: `1px solid ${theme.palette.divider}`,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          {t('session.questionProgress', { current: questionIndex + 1, total: totalQuestions })}
        </Typography>
        <Button
          size="small"
          startIcon={<PauseIcon />}
          onClick={onSaveAndPause}
          disabled={isSubmitting}
        >
          {t('session.saveAndPause')}
        </Button>
      </Box>

      <LinearProgress variant="determinate" value={progress} sx={{ height: 4 }} />

      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          maxWidth: 800,
          mx: 'auto',
          width: '100%',
          px: 3,
          pt: 4,
          pb: 3,
          gap: 3,
        }}
      >
        <Chip
          label={t(`session.questionType.${question.questionType}`)}
          size="small"
          variant="outlined"
          sx={{ alignSelf: 'flex-start' }}
        />

        <Typography variant="h6" component="h2">
          {question.text}
        </Typography>

        <TextField
          multiline
          minRows={6}
          maxRows={16}
          fullWidth
          label={t('session.answerLabel')}
          value={draftAnswer}
          onChange={(e) => onAnswerChange(e.target.value)}
          disabled={isSubmitting}
          onKeyDown={(e) => {
            // Enter key must NOT submit — button click required (AC3)
            if (e.key === 'Enter' && !e.shiftKey) {
              e.stopPropagation()
            }
          }}
          aria-label={t('session.answerLabel')}
        />

        {submitError && (
          <Typography variant="body2" color="error">
            {submitError}
          </Typography>
        )}

        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            variant="contained"
            size="large"
            disabled={isSubmitting || !draftAnswer.trim()}
            onClick={() => onSubmit(draftAnswer)}
          >
            {isSubmitting ? t('common.loading') : t('session.submitAnswer')}
          </Button>
        </Box>
      </Box>
    </Box>
  )
}
