import { Suspense } from 'react';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { NotificationGuard } from './components';

export default function App() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <NotificationGuard>
        <RouterProvider router={router} />
      </NotificationGuard>
    </Suspense>
  );
}
