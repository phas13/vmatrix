import { render, screen } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { ThemeProvider } from '@mui/material/styles';
import { I18nextProvider } from 'react-i18next';
import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import theme from '../../src/theme';
import en from '../../src/i18n/en.json';
import ViewportGuard from '../../src/components/ViewportGuard';

expect.extend(toHaveNoViolations);

const testI18n = i18next.createInstance();
testI18n.use(initReactI18next).init({
  resources: { en: { translation: en } },
  lng: 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <I18nextProvider i18n={testI18n}>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </I18nextProvider>
  );
}

describe('ViewportGuard', () => {
  it('blocks access and shows message on mobile (< 768px)', () => {
    mockMatchMedia(true); // matches '(max-width: 767px)'
    render(<ViewportGuard><div data-testid="app">App</div></ViewportGuard>, { wrapper });
    expect(screen.queryByTestId('app')).not.toBeInTheDocument();
    expect(screen.getByText(/optimized for desktop/i)).toBeInTheDocument();
  });

  it('renders children on desktop (>= 768px)', () => {
    mockMatchMedia(false); // does not match '(max-width: 767px)'
    render(<ViewportGuard><div data-testid="app">App</div></ViewportGuard>, { wrapper });
    expect(screen.getByTestId('app')).toBeInTheDocument();
  });

  it('block screen has no axe violations', async () => {
    mockMatchMedia(true);
    const { container } = render(<ViewportGuard><div>App</div></ViewportGuard>, { wrapper });
    expect(await axe(container)).toHaveNoViolations();
  });
});
