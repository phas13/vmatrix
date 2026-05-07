import type { Meta, StoryObj } from '@storybook/react'
import AssessmentResultReveal from './AssessmentResultReveal'

const meta: Meta<typeof AssessmentResultReveal> = {
  title: 'Components/Session/AssessmentResultReveal',
  component: AssessmentResultReveal,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof AssessmentResultReveal>

export const InitialAssessment: Story = {
  args: {
    score: 85,
    previousScore: null,
    strengths: 'Strong analytical skills and deep understanding of React hooks.',
    areasForGrowth: 'Could improve on advanced TypeScript patterns and testing strategies.',
    categoryName: 'Frontend Development',
    levelPercentage: 45,
  },
}

export const ImprovedScore: Story = {
  args: {
    score: 92,
    previousScore: 85,
    strengths: 'Significant improvement in testing. Excellent grasp of system architecture.',
    areasForGrowth: 'Continue focusing on performance optimization and mentoring.',
    categoryName: 'Frontend Development',
    levelPercentage: 52,
  },
}

export const DeclinedScore: Story = {
  args: {
    score: 78,
    previousScore: 85,
    strengths: 'Still maintains a solid foundation in core principles.',
    areasForGrowth: 'Recent responses show gaps in modern CSS practices. Refresh on CSS Grid and Flexbox is recommended.',
    categoryName: 'Frontend Development',
    levelPercentage: 42,
  },
}
