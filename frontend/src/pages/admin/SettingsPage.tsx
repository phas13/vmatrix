import { useState, useEffect } from 'react';
import { Alert, Box, Button, CircularProgress, Skeleton, TextField, Typography } from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { getSettings, updateSettings } from '../../api/admin';

// Frontend tests deferred pending Vitest setup

export default function SettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [threshold, setThreshold] = useState<number>(90);
  const [domain, setDomain] = useState<string>('');
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const { data, isLoading } = useQuery({ queryKey: ['admin', 'settings'], queryFn: getSettings });

  useEffect(() => {
    if (data) {
      setThreshold(data.promotionThreshold);
      setDomain(data.defaultCompetencyDomain);
    }
  }, [data]);

  const { mutate, isPending } = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'settings'] });
      setErrorMsg('');
      setSuccessMsg(t('admin.settings.saveSuccess'));
      setTimeout(() => setSuccessMsg(''), 5000);
    },
    onError: () => setErrorMsg(t('admin.settings.saveError')),
  });

  const handleSave = () => {
    setErrorMsg('');
    mutate({ promotionThreshold: threshold, defaultCompetencyDomain: domain });
  };

  if (isLoading) return <Skeleton variant="rectangular" height={200} />;

  return (
    <Box sx={{ p: 3, maxWidth: 480 }}>
      <Typography variant="h5" sx={{ mb: 3 }}>
        {t('admin.settings.title')}
      </Typography>
      {successMsg && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {successMsg}
        </Alert>
      )}
      {errorMsg && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {errorMsg}
        </Alert>
      )}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <TextField
          type="number"
          label={t('admin.settings.promotionThreshold')}
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
          slotProps={{ htmlInput: { min: 1, max: 100 } }}
          fullWidth
        />
        <TextField
          label={t('admin.settings.defaultDomain')}
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          fullWidth
        />
        <Button
          onClick={handleSave}
          disabled={isPending}
          variant="contained"
          startIcon={isPending ? <CircularProgress size={16} /> : null}
        >
          {t('admin.settings.save')}
        </Button>
      </Box>
    </Box>
  );
}
