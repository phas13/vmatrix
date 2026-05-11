import type { Meta, StoryObj } from '@storybook/react'
import CompetencyMatrix from './CompetencyMatrix'
import type { CategoryData } from './CompetencyMatrix.types'

const mockCategory: CategoryData = {
  id: 'cat-1',
  matrixId: 'matrix-1',
  name: 'Frontend Development',
  description: 'Core frontend skills',
  order: 1,
  subItems: [
    {
      id: 'item-1',
      categoryId: 'cat-1',
      name: 'React Hooks',
      description: 'Knowledge of useState, useEffect, custom hooks',
      order: 1,
      isFlagged: false,
      flagNote: null,
    },
    {
      id: 'item-2',
      categoryId: 'cat-1',
      name: 'TypeScript',
      description: 'Proficiency with TypeScript types and generics',
      order: 2,
      isFlagged: true,
      flagNote: 'Needs review',
    },
  ],
}

const meta: Meta<typeof CompetencyMatrix> = {
  title: 'Components/Competency/CompetencyMatrix',
  component: CompetencyMatrix,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof CompetencyMatrix>

export const SpecialistView: Story = {
  args: {
    categories: [mockCategory],
    variant: 'specialist',
  },
}

export const CMReviewView: Story = {
  args: {
    categories: [mockCategory],
    variant: 'cm-review',
    localEdits: {},
    localRemovals: [],
  },
}

export const EmptyState: Story = {
  args: {
    categories: [],
    variant: 'specialist',
  },
}
