import { render } from '@testing-library/react'
import { axe, toHaveNoViolations } from 'jest-axe'
import { ThemeProvider } from '@mui/material/styles'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { MemoryRouter } from 'react-router-dom'
import i18next from 'i18next'
import theme from '../../../src/theme'
import en from '../../../src/i18n/en.json'
import CompetencyMatrix from '../../../src/components/competency/CompetencyMatrix'
import type { CategoryData } from '../../../src/components/competency/CompetencyMatrix.types'

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
      description: 'Knowledge of hooks',
      order: 1,
      isFlagged: false,
      flagNote: null,
    },
  ],
}

describe('CompetencyMatrix', () => {
  it('has zero axe violations in SpecialistView variant', async () => {
    const { container } = render(
      <CompetencyMatrix categories={[mockCategory]} variant="specialist" />,
      { wrapper },
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations in CMReviewView variant', async () => {
    const { container } = render(
      <CompetencyMatrix
        categories={[mockCategory]}
        variant="cm-review"
        localEdits={{}}
        localRemovals={[]}
      />,
      { wrapper },
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('has zero axe violations in EmptyState', async () => {
    const { container } = render(
      <CompetencyMatrix categories={[]} variant="specialist" />,
      { wrapper },
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
