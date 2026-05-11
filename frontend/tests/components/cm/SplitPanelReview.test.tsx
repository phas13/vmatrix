import { render } from '@testing-library/react'
import { axe, toHaveNoViolations } from 'jest-axe'
import { ThemeProvider } from '@mui/material/styles'
import { MemoryRouter } from 'react-router-dom'
import theme from '../../../src/theme'
import SplitPanelReview from '../../../src/components/cm/SplitPanelReview'

expect.extend(toHaveNoViolations)

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </MemoryRouter>
  )
}

describe('SplitPanelReview', () => {
  it('renders loading skeletons when isLoading=true', () => {
    const { container } = render(
      <SplitPanelReview isLoading={true} leftContent={<></>} rightContent={<></>} />,
      { wrapper }
    )
    expect(container.firstChild).toBeTruthy()
  })

  it('renders left and right panel content when not loading', () => {
    const { getByText } = render(
      <SplitPanelReview
        isLoading={false}
        leftContent={<div>Left panel content</div>}
        rightContent={<div>Right panel content</div>}
      />,
      { wrapper }
    )
    expect(getByText('Left panel content')).toBeInTheDocument()
    expect(getByText('Right panel content')).toBeInTheDocument()
  })

  it('has zero axe violations in Loading state', async () => {
    const { container } = render(
      <SplitPanelReview isLoading={true} leftContent={<></>} rightContent={<></>} />,
      { wrapper }
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations in Ready state', async () => {
    const { container } = render(
      <SplitPanelReview
        isLoading={false}
        leftContent={<p>Transcript content</p>}
        rightContent={<button>Uphold</button>}
      />,
      { wrapper }
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations in Deciding state (disabled buttons)', async () => {
    const { container } = render(
      <SplitPanelReview
        isLoading={false}
        leftContent={<p>Full transcript</p>}
        rightContent={
          <div>
            <button disabled>Uphold</button>
            <button disabled>Override</button>
          </div>
        }
      />,
      { wrapper }
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations in Resolved state', async () => {
    const { container } = render(
      <SplitPanelReview
        isLoading={false}
        leftContent={<p>Full transcript</p>}
        rightContent={<p>Decision: Upheld</p>}
      />,
      { wrapper }
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
