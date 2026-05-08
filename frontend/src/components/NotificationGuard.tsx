import { useEffect, useState } from 'react';
import { Alert, Snackbar } from '@mui/material';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { getUnreadNotifications, markNotificationRead } from '../api/users';
import { useAuth } from '../hooks/useAuth';

const HANDLED_TYPES = [
  'credential_reset',
  'matrix_approved',
  'matrix_pending_review',
  'dispute_resolved',
  'promotion_approved',
  'promotion_rejected',
  'new_cm_assignment',
  'promotion_suggestion',
]

const SEVERITY_MAP: Record<string, 'success' | 'info' | 'warning' | 'error'> = {
  promotion_approved: 'success',
  promotion_rejected: 'warning',
}

export default function NotificationGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState<{ id: string; type: string; message: string } | null>(null);

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
      setCurrent({ id: found.id, type: found.type, message: found.content });
      setOpen(true);
    }
  }, [notifications, open]);

  const handleClose = async (_event?: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') return;
    
    if (current) {
      try {
        await markNotificationRead(current.id);
        setOpen(false);
        queryClient.invalidateQueries({ queryKey: ['notifications', 'unread'] });
        setCurrent(null);
      } catch (error) {
        console.error('Failed to mark notification as read:', error);
        // Keep it open so the user can try again or at least see it's still there
        // Or we could close it but not invalidate, but then it might pop up again.
        // The safest for UX is probably to close it but warn the user.
        setOpen(false);
      }
    } else {
      setOpen(false);
    }
  };

  const displayMessage = current
    ? t(`notifications.types.${current.type}`, { defaultValue: current.message })
    : '';

  const severity = current ? (SEVERITY_MAP[current.type] ?? 'info') : 'info';

  return (
    <>
      {children}
      <Snackbar
        open={open}
        autoHideDuration={10000}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity={severity} onClose={handleClose} variant="filled" sx={{ width: '100%' }}>
          {displayMessage}
        </Alert>
      </Snackbar>
    </>
  );
}
