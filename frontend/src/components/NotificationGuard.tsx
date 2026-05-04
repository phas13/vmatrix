import { useEffect, useState } from 'react';
import { Alert, Snackbar } from '@mui/material';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getUnreadNotifications, markNotificationRead } from '../api/users';
import { useAuth } from '../hooks/useAuth';

const HANDLED_TYPES = ['credential_reset', 'matrix_approved', 'matrix_pending_review']

export default function NotificationGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState<{ id: string; message: string } | null>(null);

  const { data: notifications } = useQuery({
    queryKey: ['notifications', 'unread'],
    queryFn: getUnreadNotifications,
    enabled: !!user,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!notifications || notifications.length === 0) return;
    const found = notifications.find((n) => HANDLED_TYPES.includes(n.type));
    if (found && !open) {
      setCurrent({ id: found.id, message: found.content });
      setOpen(true);
    }
  }, [notifications, open]);

  const handleClose = async () => {
    setOpen(false);
    if (current) {
      await markNotificationRead(current.id);
      queryClient.invalidateQueries({ queryKey: ['notifications', 'unread'] });
      setCurrent(null);
    }
  };

  return (
    <>
      {children}
      <Snackbar
        open={open}
        autoHideDuration={10000}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity="info" onClose={handleClose} variant="filled" sx={{ width: '100%' }}>
          {current?.message ?? ''}
        </Alert>
      </Snackbar>
    </>
  );
}
