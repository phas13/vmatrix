import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import theme from '../../src/theme';
import SpecialistLayout from '../../src/layouts/SpecialistLayout';
import CMLayout from '../../src/layouts/CMLayout';
import HRLayout from '../../src/layouts/HRLayout';
import AdminLayout from '../../src/layouts/AdminLayout';
import PublicLayout from '../../src/layouts/PublicLayout';
import FullScreenLayout from '../../src/layouts/FullScreenLayout';

expect.extend(toHaveNoViolations);

function makeWrapper(initialPath = '/') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <ThemeProvider theme={theme}>
          <MemoryRouter initialEntries={[initialPath]}>
            {children}
          </MemoryRouter>
        </ThemeProvider>
      </QueryClientProvider>
    );
  };
}

describe('SpecialistLayout', () => {
  it('renders without crashing and has a Drawer', () => {
    const { container } = render(<SpecialistLayout />, { wrapper: makeWrapper('/specialist/dashboard') });
    const drawer = container.querySelector('.MuiDrawer-root');
    expect(drawer).not.toBeNull();
  });

  it('has no axe violations', async () => {
    const { container } = render(<SpecialistLayout />, { wrapper: makeWrapper('/specialist/dashboard') });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe('CMLayout', () => {
  it('renders AppBar with blue background', () => {
    const { container } = render(<CMLayout />, { wrapper: makeWrapper('/cm/dashboard') });
    const appBar = container.querySelector('.MuiAppBar-root') as HTMLElement | null;
    expect(appBar).not.toBeNull();
  });

  it('has no axe violations', async () => {
    const { container } = render(<CMLayout />, { wrapper: makeWrapper('/cm/dashboard') });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe('HRLayout', () => {
  it('has no axe violations', async () => {
    const { container } = render(<HRLayout />, { wrapper: makeWrapper('/hr/dashboard') });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe('AdminLayout', () => {
  it('has no axe violations', async () => {
    const { container } = render(<AdminLayout />, { wrapper: makeWrapper('/admin/users') });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe('PublicLayout', () => {
  it('has no axe violations', async () => {
    const { container } = render(<PublicLayout />, { wrapper: makeWrapper('/login') });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe('FullScreenLayout', () => {
  it('renders only Outlet content (no AppBar or Drawer)', () => {
    const { container } = render(<FullScreenLayout />, { wrapper: makeWrapper('/') });
    expect(container.querySelector('.MuiAppBar-root')).toBeNull();
    expect(container.querySelector('.MuiDrawer-root')).toBeNull();
  });

  it('has no axe violations', async () => {
    const { container } = render(<FullScreenLayout />, { wrapper: makeWrapper('/') });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
