import { render, screen } from '@testing-library/react'
import { axe, toHaveNoViolations } from 'jest-axe'
import { ThemeProvider } from '@mui/material/styles'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import i18next from 'i18next'
import theme from '../../../src/theme'
import en from '../../../src/i18n/en.json'
import LevelProgressIndicator from '../../../src/components/shared/LevelProgressIndicator'

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

describe('LevelProgressIndicator', () => {
  it('renders the percentage and level chip in the large variant', () => {
    render(<LevelProgressIndicator level="junior" percentage={42} />, { wrapper })
    expect(screen.getByText('42%')).toBeInTheDocument()
    expect(screen.getByText('Junior')).toBeInTheDocument()
  })

  it('exposes role="progressbar" with correct ARIA values', () => {
    render(<LevelProgressIndicator level="middle" percentage={78} />, { wrapper })
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '78')
    expect(bar).toHaveAttribute('aria-valuemin', '0')
    expect(bar).toHaveAttribute('aria-valuemax', '100')
  })

  it('clamps percentage > 100 to 100 in display and ARIA', () => {
    render(<LevelProgressIndicator level="senior" percentage={120} />, { wrapper })
    expect(screen.getByText('100%')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
  })

  it('clamps negative percentage to 0', () => {
    render(<LevelProgressIndicator level="junior" percentage={-10} />, { wrapper })
    expect(screen.getByText('0%')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
  })

  it('renders fallback dash when level is null', () => {
    render(<LevelProgressIndicator level={null} percentage={0} />, { wrapper })
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('renders compact variant with caption percentage', () => {
    render(<LevelProgressIndicator level="junior" percentage={35} variant="compact" />, { wrapper })
    expect(screen.getByText('35%')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '35')
  })

  it('large variant has no axe violations', async () => {
    const { container } = render(
      <LevelProgressIndicator level="middle" percentage={78} />,
      { wrapper },
    )
    expect(await axe(container)).toHaveNoViolations()
  })

  it('compact variant has no axe violations', async () => {
    const { container } = render(
      <LevelProgressIndicator level="senior" percentage={92} variant="compact" />,
      { wrapper },
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
