import React from 'react';
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
const UsersPage = React.lazy(() => import('./pages/admin/UsersPage'));
const SettingsPage = React.lazy(() => import('./pages/admin/SettingsPage'));
const DashboardPage = React.lazy(() => import('./pages/specialist/DashboardPage'));
const HistoryPage = React.lazy(() => import('./pages/specialist/HistoryPage'));
const MatrixPage = React.lazy(() => import('./pages/specialist/MatrixPage'));
const SessionPage = React.lazy(() => import('./pages/specialist/SessionPage'));
const SessionResultPage = React.lazy(() => import('./pages/specialist/SessionResultPage'));
const CMDashboardPage = React.lazy(() => import('./pages/cm/DashboardPage'));
const MatrixReviewPage = React.lazy(() => import('./pages/cm/MatrixReviewPage'));
const SpecialistDetailPage = React.lazy(() => import('./pages/cm/SpecialistDetailPage'));

const CMReviewPlaceholderPage = React.lazy(() => import('./pages/cm/CMReviewPlaceholderPage'));
const DisputeReviewPage = React.lazy(() => import('./pages/cm/DisputeReviewPage'));
const PromotionReviewPage = React.lazy(() => import('./pages/cm/PromotionReviewPage'));

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
          { path: 'dashboard', element: <DashboardPage /> },
          { path: 'matrix', element: <MatrixPage /> },
          { path: 'history', element: <HistoryPage /> },
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
      { path: 'specialist/:specialistId', element: <SpecialistDetailPage /> },
      { path: 'matrix/:specialistId/review', element: <MatrixReviewPage /> },
      { path: 'review/dispute/:id', element: <DisputeReviewPage /> },
      { path: 'review/promotion/:id', element: <PromotionReviewPage /> },
      { path: 'review/:type/:id', element: <CMReviewPlaceholderPage /> },
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
