import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AxiosError } from 'axios';
import { listUsers, createUser, updateUserCm } from '../../api/admin';
import type { CreateUserPayload } from '../../api/admin';
import type { User } from '../../types/domain';
import type { ApiError } from '../../types/api';

// Frontend tests deferred pending Vitest setup

const ROLES = ['specialist', 'cm', 'hr', 'admin'] as const;
const LEVELS = ['junior', 'middle', 'senior'] as const;
const PER_PAGE = 20;
const SUCCESS_AUTO_DISMISS_MS = 5000;

const emptyForm = (): CreateUserPayload => ({
  email: '',
  fullName: '',
  role: '',
  password: '',
  specialistLevel: undefined,
  cmId: undefined,
});

function CreateUserForm({ cms }: { cms: User[] }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CreateUserPayload>(emptyForm);
  const [emailError, setEmailError] = useState('');
  const [genericError, setGenericError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const mutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setForm(emptyForm());
      setEmailError('');
      setGenericError('');
      setSuccessMsg(t('admin.users.createSuccess'));
    },
    onError: (error: AxiosError<ApiError>) => {
      setSuccessMsg('');
      const status = error.response?.status;
      if (status === 409) {
        setEmailError(t('admin.users.emailConflict'));
        return;
      }
      const detail = error.response?.data?.detail;
      setGenericError(typeof detail === 'string' && detail ? detail : t('common.genericError'));
    },
  });

  useEffect(() => {
    if (!successMsg) return;
    const timer = setTimeout(() => setSuccessMsg(''), SUCCESS_AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [successMsg]);

  const isSpecialist = form.role === 'specialist';
  const isFormValid =
    !!form.email &&
    !!form.fullName.trim() &&
    !!form.role &&
    form.password.length >= 8 &&
    (!isSpecialist || !!form.specialistLevel);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mutation.isPending || !isFormValid) return;
    setEmailError('');
    setGenericError('');
    setSuccessMsg('');
    mutation.mutate(form);
  };

  return (
    <Paper sx={{ p: 3, mb: 4 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        {t('admin.users.create')}
      </Typography>
      <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <TextField
          label={t('admin.users.emailLabel')}
          type="email"
          value={form.email}
          onChange={(e) => {
            setForm((f) => ({ ...f, email: e.target.value }));
            if (emailError) setEmailError('');
          }}
          required
          fullWidth
          error={!!emailError}
          helperText={emailError || undefined}
        />
        <TextField
          label={t('admin.users.fullNameLabel')}
          value={form.fullName}
          onChange={(e) => setForm((f) => ({ ...f, fullName: e.target.value }))}
          required
          fullWidth
        />
        <FormControl fullWidth required>
          <InputLabel>{t('admin.users.roleLabel')}</InputLabel>
          <Select
            value={form.role}
            label={t('admin.users.roleLabel')}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                role: e.target.value,
                specialistLevel: undefined,
                cmId: undefined,
              }))
            }
          >
            {ROLES.map((r) => (
              <MenuItem key={r} value={r}>
                {t(`admin.users.roles.${r}`)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField
          label={t('admin.users.passwordLabel')}
          type="password"
          value={form.password}
          onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
          required
          fullWidth
          slotProps={{ htmlInput: { minLength: 8, maxLength: 72 } }}
        />
        {isSpecialist && (
          <>
            <FormControl fullWidth required>
              <InputLabel>{t('admin.users.levelLabel')}</InputLabel>
              <Select
                value={form.specialistLevel ?? ''}
                label={t('admin.users.levelLabel')}
                onChange={(e) => setForm((f) => ({ ...f, specialistLevel: e.target.value as string }))}
              >
                {LEVELS.map((l) => (
                  <MenuItem key={l} value={l}>
                    {t(`admin.users.levels.${l}`)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>{t('admin.users.cmLabel')}</InputLabel>
              <Select
                value={form.cmId ?? ''}
                label={t('admin.users.cmLabel')}
                onChange={(e) => setForm((f) => ({ ...f, cmId: e.target.value || undefined }))}
              >
                <MenuItem value="">{t('admin.users.cmNone')}</MenuItem>
                {cms.map((cm) => (
                  <MenuItem key={cm.id} value={cm.id}>
                    {cm.fullName}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </>
        )}
        {genericError && (
          <Alert severity="error" onClose={() => setGenericError('')}>
            {genericError}
          </Alert>
        )}
        {successMsg && (
          <Alert severity="success" role="status" onClose={() => setSuccessMsg('')}>
            {successMsg}
          </Alert>
        )}
        <Button
          type="submit"
          variant="contained"
          disabled={mutation.isPending || !isFormValid}
          startIcon={mutation.isPending ? <CircularProgress size={16} /> : null}
        >
          {t('admin.users.create')}
        </Button>
      </Box>
    </Paper>
  );
}

function UserList({ activeCMs }: { activeCMs: User[] }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [reassignError, setReassignError] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'users', 'list', page, PER_PAGE],
    queryFn: () => listUsers({ page, perPage: PER_PAGE }),
  });

  const reassignMutation = useMutation({
    mutationFn: ({ userId, cmId }: { userId: string; cmId: string | null }) =>
      updateUserCm(userId, { cmId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setReassignError('');
    },
    onError: (error: AxiosError<ApiError>) => {
      const detail = error.response?.data?.detail;
      // Handle both string and RFC 7807 detail object
      const message = typeof detail === 'object' && detail !== null ? (detail as any).detail : detail;
      setReassignError(typeof message === 'string' && message ? message : t('admin.users.reassignError'));
    },
  });

  if (isLoading) {
    return (
      <Box>
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} height={48} sx={{ mb: 1 }} />
        ))}
      </Box>
    );
  }

  const users = data?.items ?? [];

  if (users.length === 0) {
    return (
      <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
        {t('admin.users.noUsers')}
      </Typography>
    );
  }

  return (
    <Paper>
      {reassignError && (
        <Alert severity="error" onClose={() => setReassignError('')} sx={{ mb: 0 }}>
          {reassignError}
        </Alert>
      )}
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>{t('admin.users.columns.email')}</TableCell>
            <TableCell>{t('admin.users.columns.fullName')}</TableCell>
            <TableCell>{t('admin.users.columns.role')}</TableCell>
            <TableCell>{t('admin.users.columns.level')}</TableCell>
            <TableCell>{t('admin.users.columns.cmAssignment')}</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {users.map((u) => (
            <TableRow key={u.id}>
              <TableCell>{u.email}</TableCell>
              <TableCell>{u.fullName}</TableCell>
              <TableCell>{t(`admin.users.roles.${u.role}`)}</TableCell>
              <TableCell>
                {u.specialistLevel ? t(`admin.users.levels.${u.specialistLevel}`) : t('admin.users.noLevel')}
              </TableCell>
              <TableCell>
                {u.role === 'specialist' ? (
                  <FormControl size="small" sx={{ minWidth: 180 }}>
                    <Select
                      value={u.cmId ?? ''}
                      displayEmpty
                      disabled={reassignMutation.isPending}
                      onChange={(e) => {
                        const selected = e.target.value as string;
                        reassignMutation.mutate({ userId: u.id, cmId: selected || null });
                      }}
                    >
                      <MenuItem value="">{t('admin.users.cmUnassigned')}</MenuItem>
                      {activeCMs.map((cm) => (
                        <MenuItem key={cm.id} value={cm.id}>
                          {cm.fullName}
                        </MenuItem>
                      ))}
                      {/* Fix: ensure current CM is shown even if inactive or role changed */}
                      {u.cmId && !activeCMs.some((c) => c.id === u.cmId) && (
                        <MenuItem value={u.cmId} disabled>
                          {t('admin.users.unknownCm')} ({u.cmId.slice(0, 8)})
                        </MenuItem>
                      )}
                    </Select>
                  </FormControl>
                ) : (
                  t('admin.users.notApplicable')
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {data && data.pages > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1, p: 2 }}>
          <Button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            aria-label={t('common.previous')}
          >
            {t('common.previous')}
          </Button>
          <Typography sx={{ alignSelf: 'center' }}>
            {page} / {data.pages}
          </Typography>
          <Button
            disabled={page >= data.pages}
            onClick={() => setPage((p) => p + 1)}
            aria-label={t('common.next')}
          >
            {t('common.next')}
          </Button>
        </Box>
      )}
    </Paper>
  );
}

export default function UsersPage() {
  const { t } = useTranslation();

  // CM dropdown: server-side filter by role + active status to avoid the 100-user cap.
  const { data: cmsData } = useQuery({
    queryKey: ['admin', 'users', 'cms'],
    queryFn: () => listUsers({ role: 'cm', active: true, perPage: 500 }),
  });
  const cms = cmsData?.items ?? [];

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" sx={{ mb: 3 }}>
        {t('admin.users.title')}
      </Typography>
      <CreateUserForm cms={cms} />
      <UserList activeCMs={cms} />
    </Box>
  );
}
