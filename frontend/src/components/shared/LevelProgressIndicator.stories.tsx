import type { Meta, StoryObj } from '@storybook/react'
import LevelProgressIndicator from './LevelProgressIndicator'

const meta: Meta<typeof LevelProgressIndicator> = {
  title: 'Components/Shared/LevelProgressIndicator',
  component: LevelProgressIndicator,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  argTypes: {
    level: {
      control: 'select',
      options: [null, 'junior', 'middle', 'senior'],
    },
    percentage: {
      control: { type: 'range', min: 0, max: 100, step: 1 },
    },
    variant: {
      control: 'inline-radio',
      options: ['large', 'compact'],
    },
  },
}

export default meta
type Story = StoryObj<typeof LevelProgressIndicator>

export const LargeJuniorNormal: Story = {
  args: { level: 'junior', percentage: 42, variant: 'large' },
}

export const LargeMiddleApproachingThreshold: Story = {
  args: { level: 'middle', percentage: 78, variant: 'large' },
}

export const LargeSeniorThresholdReached: Story = {
  args: { level: 'senior', percentage: 92, variant: 'large' },
}

export const LargeNullLevel: Story = {
  args: { level: null, percentage: 0, variant: 'large' },
}

export const LargeOverflowClamped: Story = {
  args: { level: 'senior', percentage: 120, variant: 'large' },
}

export const CompactJunior: Story = {
  args: { level: 'junior', percentage: 35, variant: 'compact' },
}

export const CompactSeniorThreshold: Story = {
  args: { level: 'senior', percentage: 95, variant: 'compact' },
}
