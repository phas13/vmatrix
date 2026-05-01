import { useEffect, useState } from 'react';
import { Alert, Snackbar } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { getUnreadNotifications } from '../api/users';
import { useAuth } from '../hooks/useAuth';

export default function NotificationGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');

  const { data: notifications } = useQuery({
    queryKey: ['notifications', 'unread'],
    queryFn: getUnreadNotifications,
    enabled: !!user,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (notifications && notifications.length > 0) {
      const resetNotification = notifications.find((n) => n.type === 'credential_reset');
      if (resetNotification) {
        setMessage(resetNotification.content);
        setOpen(true);
      }
    }
  }, [notifications]);

  return (
    <>
      {children}
      <Snackbar
        open={open}
        autoHideDuration={10000}
        onClose={() => setOpen(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity="info" onClose={() => setOpen(false)} variant="filled" sx={{ width: '100%' }}>
          {message}
        </Alert>
      </Snackbar>
    </>
  );
}
