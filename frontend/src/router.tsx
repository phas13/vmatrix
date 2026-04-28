import { createBrowserRouter, redirect, Outlet } from 'react-router-dom';
import { getMe } from './api/auth';
import PublicLayout from './layouts/PublicLayout';
import SpecialistLayout from './layouts/SpecialistLayout';
import CMLayout from './layouts/CMLayout';
import HRLayout from './layouts/HRLayout';
import AdminLayout from './layouts/AdminLayout';
import LoginPage from './pages/LoginPage';
import PlaceholderPage from './pages/PlaceholderPage';

const ROLE_HOMES: Record<string, string> = {
  specialist: '/specialist/dashboard',
  cm: '/cm/dashboard',
  hr: '/hr/dashboard',
  admin: '/admin/users',
};

async function rootLoader() {
  try {
    const user = await getMe();
    return redirect(ROLE_HOMES[user.role] ?? '/login');
  } catch {
    return redirect('/login');
  }
}

function requireRole(role: string) {
  return async () => {
    try {
      const user = await getMe();
      if (user.role !== role) return redirect(ROLE_HOMES[user.role] ?? '/login');
      return { user };
    } catch {
      return redirect('/login');
    }
  };
}

export const router = createBrowserRouter([
  { path: '/', loader: rootLoader, element: <Outlet /> },
  {
    path: '/login',
    element: <PublicLayout />,
    children: [{ index: true, element: <LoginPage /> }],
  },
  {
    path: '/specialist',
    loader: requireRole('specialist'),
    element: <SpecialistLayout />,
    children: [
      { path: 'dashboard', element: <PlaceholderPage title="Specialist Dashboard" /> },
      { path: 'matrix', element: <PlaceholderPage title="Competency Matrix" /> },
      { path: 'history', element: <PlaceholderPage title="Assessment History" /> },
    ],
  },
  {
    path: '/cm',
    loader: requireRole('cm'),
    element: <CMLayout />,
    children: [
      { path: 'dashboard', element: <PlaceholderPage title="CM Dashboard" /> },
    ],
  },
  {
    path: '/hr',
    loader: requireRole('hr'),
    element: <HRLayout />,
    children: [
      { path: 'dashboard', element: <PlaceholderPage title="HR Dashboard" /> },
    ],
  },
  {
    path: '/admin',
    loader: requireRole('admin'),
    element: <AdminLayout />,
    children: [
      { path: 'users', element: <PlaceholderPage title="Admin — Users" /> },
      { path: 'settings', element: <PlaceholderPage title="Admin — Settings" /> },
    ],
  },
]);
