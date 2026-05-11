import { render } from '@testing-library/react'
import { axe, toHaveNoViolations } from 'jest-axe'
import { ThemeProvider } from '@mui/material/styles'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import i18next from 'i18next'
import theme from '../../../src/theme'
import en from '../../../src/i18n/en.json'
import AssessmentSessionView from '../../../src/components/session/AssessmentSessionView'

expect.extend(toHaveNoViolations)

const testI18n = i18next.createInstance()
testI18n.use(initReactI18next).init({
  resources: { en: { translation: en } },
  lng: 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <I18nextProvider i18n={testI18n}>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </I18nextProvider>
  )
}

const mockQuestion = {
  id: 'q-1',
  sessionId: 'sess-1',
  text: 'What are React hooks?',
  questionType: 'theoretical' as const,
  order: 1,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
}

describe('AssessmentSessionView', () => {
  it('has zero axe violations in FirstQuestion state', async () => {
    const { container } = render(
      <AssessmentSessionView
        question={mockQuestion}
        questionIndex={0}
        totalQuestions={5}
        draftAnswer=""
        isSubmitting={false}
        submitError={null}
        onAnswerChange={() => {}}
        onSubmit={() => {}}
        onSaveAndPause={() => {}}
      />,
      { wrapper },
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations in MiddleQuestion state', async () => {
    const { container } = render(
      <AssessmentSessionView
        question={{ ...mockQuestion, order: 3 }}
        questionIndex={2}
        totalQuestions={5}
        draftAnswer="Some answer text here"
        isSubmitting={false}
        submitError={null}
        onAnswerChange={() => {}}
        onSubmit={() => {}}
        onSaveAndPause={() => {}}
      />,
      { wrapper },
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations in SubmittingState', async () => {
    const { container } = render(
      <AssessmentSessionView
        question={mockQuestion}
        questionIndex={4}
        totalQuestions={5}
        draftAnswer="My complete answer"
        isSubmitting={true}
        submitError={null}
        onAnswerChange={() => {}}
        onSubmit={() => {}}
        onSaveAndPause={() => {}}
      />,
      { wrapper },
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
