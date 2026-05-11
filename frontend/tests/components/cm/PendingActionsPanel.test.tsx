import { render, screen } from '@testing-library/react'
import { axe, toHaveNoViolations } from 'jest-axe'
import { ThemeProvider } from '@mui/material/styles'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { MemoryRouter } from 'react-router-dom'
import i18next from 'i18next'
import theme from '../../../src/theme'
import en from '../../../src/i18n/en.json'
import PendingActionsPanel from '../../../src/components/cm/PendingActionsPanel'
import type { PendingActionsData } from '../../../src/types/domain'

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
    <MemoryRouter>
      <I18nextProvider i18n={testI18n}>
        <ThemeProvider theme={theme}>{children}</ThemeProvider>
      </I18nextProvider>
    </MemoryRouter>
  )
}

const emptyData: PendingActionsData = {
  disputes: [],
  promotions: [],
  matrixApprovals: [],
  updateProposals: [],
  total: 0,
}

const makeDispute = () => ({
  id: 'dispute-1',
  type: 'dispute' as const,
  specialistId: 'spec-1',
  specialistName: 'Alice Brown',
  description: 'Assessment dispute pending review',
  date: new Date().toISOString(),
})

const makePromotion = () => ({
  id: 'spec-2',
  type: 'promotion' as const,
  specialistId: 'spec-2',
  specialistName: 'Bob Smith',
  description: 'Promotion threshold reached — review required',
  date: new Date().toISOString(),
})

const makeMatrixApproval = () => ({
  id: 'matrix-1',
  type: 'matrix_approval' as const,
  specialistId: 'spec-3',
  specialistName: 'Carol White',
  description: 'Competency matrix awaiting approval',
  date: new Date().toISOString(),
})

describe('PendingActionsPanel', () => {
  it('renders loading skeletons when isLoading=true', () => {
    const { container } = render(
      <PendingActionsPanel data={undefined} isLoading={true} />,
      { wrapper }
    )
    // Skeletons render as span elements with aria-hidden or similar
    expect(container.firstChild).toBeTruthy()
  })

  it('renders empty state message when total=0', () => {
    render(<PendingActionsPanel data={emptyData} isLoading={false} />, { wrapper })
    expect(screen.getByText('All caught up — no actions pending')).toBeInTheDocument()
  })

  it('renders disputes group when disputes exist', () => {
    const data: PendingActionsData = {
      disputes: [makeDispute()],
      promotions: [],
      matrixApprovals: [],
      updateProposals: [],
      total: 1,
    }
    render(<PendingActionsPanel data={data} isLoading={false} />, { wrapper })
    expect(screen.getByText('Disputes')).toBeInTheDocument()
    expect(screen.getByText('Alice Brown')).toBeInTheDocument()
  })

  it('renders promotions group when promotions exist', () => {
    const data: PendingActionsData = {
      disputes: [],
      promotions: [makePromotion()],
      matrixApprovals: [],
      updateProposals: [],
      total: 1,
    }
    render(<PendingActionsPanel data={data} isLoading={false} />, { wrapper })
    expect(screen.getByText('Promotions')).toBeInTheDocument()
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()
  })

  it('renders matrix approvals group when matrix approvals exist', () => {
    const data: PendingActionsData = {
      disputes: [],
      promotions: [],
      matrixApprovals: [makeMatrixApproval()],
      updateProposals: [],
      total: 1,
    }
    render(<PendingActionsPanel data={data} isLoading={false} />, { wrapper })
    expect(screen.getByText('Matrix Approvals')).toBeInTheDocument()
    expect(screen.getByText('Carol White')).toBeInTheDocument()
  })

  it('skips empty group headers', () => {
    const data: PendingActionsData = {
      disputes: [makeDispute()],
      promotions: [],
      matrixApprovals: [],
      updateProposals: [],
      total: 1,
    }
    render(<PendingActionsPanel data={data} isLoading={false} />, { wrapper })
    expect(screen.queryByText('Promotions')).not.toBeInTheDocument()
    expect(screen.queryByText('Matrix Approvals')).not.toBeInTheDocument()
  })

  it('renders Review button for each item', () => {
    const data: PendingActionsData = {
      disputes: [makeDispute()],
      promotions: [],
      matrixApprovals: [],
      updateProposals: [],
      total: 1,
    }
    render(<PendingActionsPanel data={data} isLoading={false} />, { wrapper })
    expect(screen.getByRole('link', { name: 'Review' })).toBeInTheDocument()
  })

  it('has zero axe violations in Loading state', async () => {
    const { container } = render(
      <PendingActionsPanel data={undefined} isLoading={true} />,
      { wrapper }
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations in Empty state', async () => {
    const { container } = render(
      <PendingActionsPanel data={emptyData} isLoading={false} />,
      { wrapper }
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations with disputes', async () => {
    const data: PendingActionsData = {
      disputes: [makeDispute()],
      promotions: [],
      matrixApprovals: [],
      updateProposals: [],
      total: 1,
    }
    const { container } = render(
      <PendingActionsPanel data={data} isLoading={false} />,
      { wrapper }
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations with promotions', async () => {
    const data: PendingActionsData = {
      disputes: [],
      promotions: [makePromotion()],
      matrixApprovals: [],
      updateProposals: [],
      total: 1,
    }
    const { container } = render(
      <PendingActionsPanel data={data} isLoading={false} />,
      { wrapper }
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations with matrix approvals', async () => {
    const data: PendingActionsData = {
      disputes: [],
      promotions: [],
      matrixApprovals: [makeMatrixApproval()],
      updateProposals: [],
      total: 1,
    }
    const { container } = render(
      <PendingActionsPanel data={data} isLoading={false} />,
      { wrapper }
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations with all types', async () => {
    const data: PendingActionsData = {
      disputes: [makeDispute()],
      promotions: [makePromotion()],
      matrixApprovals: [makeMatrixApproval()],
      updateProposals: [],
      total: 3,
    }
    const { container } = render(
      <PendingActionsPanel data={data} isLoading={false} />,
      { wrapper }
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
