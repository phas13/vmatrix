import { createBrowserRouter, redirect, Outlet } from 'react-router-dom';
import { getMe } from './api/auth';
import PublicLayout from './layouts/PublicLayout';
import SpecialistLayout from './layouts/SpecialistLayout';
import FullScreenLayout from './layouts/FullScreenLayout';
import CMLayout from './layouts/CMLayout';
import HRLayout from './layouts/HRLayout';
import AdminLayout from './layouts/AdminLayout';
import LoginPage from './pages/LoginPage';
import PlaceholderPage from './pages/PlaceholderPage';
import UsersPage from './pages/admin/UsersPage';
import SettingsPage from './pages/admin/SettingsPage';
import MatrixPage from './pages/specialist/MatrixPage'
import SessionPage from './pages/specialist/SessionPage'
import SessionResultPage from './pages/specialist/SessionResultPage'
import CMDashboardPage from './pages/cm/DashboardPage'
import MatrixReviewPage from './pages/cm/MatrixReviewPage';

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
    children: [
      {
        element: <SpecialistLayout />,
        children: [
          { path: 'dashboard', element: <PlaceholderPage title="Specialist Dashboard" /> },
          { path: 'matrix', element: <MatrixPage /> },
          { path: 'history', element: <PlaceholderPage title="Assessment History" /> },
        ],
      },
      {
        element: <FullScreenLayout />,
        children: [
          { path: 'session/:sessionId', element: <SessionPage /> },
          { path: 'session/:sessionId/result', element: <SessionResultPage /> },
        ],
      },
    ],
  },
  {
    path: '/cm',
    loader: requireRole('cm'),
    element: <CMLayout />,
    children: [
      { path: 'dashboard', element: <CMDashboardPage /> },
      { path: 'matrix/:specialistId/review', element: <MatrixReviewPage /> },
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
      { path: 'users', element: <UsersPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
]);
