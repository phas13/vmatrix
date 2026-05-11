import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router-dom'
import PendingActionsPanel from './PendingActionsPanel'
import type { PendingActionsData } from '../../types/domain'

const meta: Meta<typeof PendingActionsPanel> = {
  title: 'Components/CM/PendingActionsPanel',
  component: PendingActionsPanel,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <MemoryRouter>
        <Story />
      </MemoryRouter>
    ),
  ],
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof PendingActionsPanel>

const makeDispute = (n = 1) =>
  Array.from({ length: n }, (_, i) => ({
    id: `dispute-${i + 1}`,
    type: 'dispute' as const,
    specialistId: `spec-${i + 1}`,
    specialistName: `Specialist ${i + 1}`,
    description: 'Assessment dispute pending review',
    date: new Date().toISOString(),
  }))

const makePromotion = () => ({
  id: 'promo-1',
  type: 'promotion' as const,
  specialistId: 'spec-2',
  specialistName: 'Jane Smith',
  description: 'Promotion threshold reached — review required',
  date: new Date().toISOString(),
})

const makeMatrixApproval = () => ({
  id: 'matrix-1',
  type: 'matrix_approval' as const,
  specialistId: 'spec-3',
  specialistName: 'Bob Lee',
  description: 'Competency matrix awaiting approval',
  date: new Date().toISOString(),
})

const makeUpdateProposal = () => ({
  id: 'update-1',
  type: 'update_proposal' as const,
  specialistId: 'spec-4',
  specialistName: 'Alice Wang',
  description: 'Update proposal pending review',
  date: new Date().toISOString(),
})

const emptyData: PendingActionsData = {
  disputes: [],
  promotions: [],
  matrixApprovals: [],
  updateProposals: [],
  total: 0,
}

export const Loading: Story = {
  args: { data: undefined, isLoading: true },
}

export const Empty: Story = {
  args: { data: emptyData, isLoading: false },
}

export const HasDisputes: Story = {
  args: {
    data: {
      disputes: makeDispute(2),
      promotions: [],
      matrixApprovals: [],
      updateProposals: [],
      total: 2,
    },
    isLoading: false,
  },
}

export const HasPromotions: Story = {
  args: {
    data: {
      disputes: [],
      promotions: [makePromotion()],
      matrixApprovals: [],
      updateProposals: [],
      total: 1,
    },
    isLoading: false,
  },
}

export const HasMatrixApprovals: Story = {
  args: {
    data: {
      disputes: [],
      promotions: [],
      matrixApprovals: [makeMatrixApproval()],
      updateProposals: [],
      total: 1,
    },
    isLoading: false,
  },
}

export const AllTypes: Story = {
  args: {
    data: {
      disputes: makeDispute(1),
      promotions: [makePromotion()],
      matrixApprovals: [makeMatrixApproval()],
      updateProposals: [makeUpdateProposal()],
      total: 4,
    },
    isLoading: false,
  },
}
