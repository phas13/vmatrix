import type { Meta, StoryObj } from '@storybook/react'
import AssessmentSessionView from './AssessmentSessionView'

const mockQuestion = {
  id: 'q-1',
  sessionId: 'sess-1',
  text: 'What are React hooks and how do they improve component design?',
  questionType: 'theoretical' as const,
  order: 1,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
}

const meta: Meta<typeof AssessmentSessionView> = {
  title: 'Components/Session/AssessmentSessionView',
  component: AssessmentSessionView,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof AssessmentSessionView>

export const FirstQuestion: Story = {
  args: {
    question: mockQuestion,
    questionIndex: 0,
    totalQuestions: 5,
    draftAnswer: '',
    isSubmitting: false,
    submitError: null,
    onAnswerChange: () => {},
    onSubmit: () => {},
    onSaveAndPause: () => {},
  },
}

export const MiddleQuestion: Story = {
  args: {
    question: {
      ...mockQuestion,
      id: 'q-3',
      text: 'Describe a blue-green deployment strategy and its benefits.',
      questionType: 'practical',
      order: 3,
    },
    questionIndex: 2,
    totalQuestions: 5,
    draftAnswer: 'Blue-green deployment uses two identical production environments...',
    isSubmitting: false,
    submitError: null,
    onAnswerChange: () => {},
    onSubmit: () => {},
    onSaveAndPause: () => {},
  },
}

export const SubmittingState: Story = {
  args: {
    question: mockQuestion,
    questionIndex: 4,
    totalQuestions: 5,
    draftAnswer: 'My complete answer to this question.',
    isSubmitting: true,
    submitError: null,
    onAnswerChange: () => {},
    onSubmit: () => {},
    onSaveAndPause: () => {},
  },
}
