import { render } from '@testing-library/react'
import { axe, toHaveNoViolations } from 'jest-axe'
import { ThemeProvider } from '@mui/material/styles'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import i18next from 'i18next'
import theme from '../../../src/theme'
import en from '../../../src/i18n/en.json'
import AssessmentResultReveal from '../../../src/components/session/AssessmentResultReveal'

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

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

describe('AssessmentResultReveal', () => {
  it('has zero axe violations for initial assessment', async () => {
    const { container } = render(
      <AssessmentResultReveal
        score={85}
        previousScore={null}
        strengths="Strong analytical skills"
        areasForGrowth="Improve TypeScript patterns"
        categoryName="Frontend Development"
        levelPercentage={45}
      />,
      { wrapper },
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations for improved score', async () => {
    const { container } = render(
      <AssessmentResultReveal
        score={92}
        previousScore={85}
        strengths="Significant improvement in testing"
        areasForGrowth="Focus on performance optimization"
        categoryName="Frontend Development"
        levelPercentage={52}
      />,
      { wrapper },
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations for declined score', async () => {
    const { container } = render(
      <AssessmentResultReveal
        score={78}
        previousScore={85}
        strengths="Maintains solid foundation"
        areasForGrowth="Gaps in modern CSS practices"
        categoryName="Frontend Development"
        levelPercentage={42}
      />,
      { wrapper },
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
