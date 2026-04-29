import { useState } from 'react';
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
import { listUsers, createUser } from '../../api/admin';
import type { CreateUserPayload } from '../../api/admin';
import type { User } from '../../types/domain';

// Frontend tests deferred pending Vitest setup

const ROLES = ['specialist', 'cm', 'hr', 'admin'] as const;
const LEVELS = ['junior', 'middle', 'senior'] as const;

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
  const [successMsg, setSuccessMsg] = useState('');

  const mutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setForm(emptyForm());
      setEmailError('');
      setSuccessMsg(t('admin.users.createSuccess'));
    },
    onError: (error: any) => {
      setSuccessMsg('');
      const status = error?.response?.status;
      if (status === 409) {
        setEmailError(t('admin.users.emailConflict'));
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setEmailError('');
    setSuccessMsg('');
    mutation.mutate(form);
  };

  const isSpecialist = form.role === 'specialist';

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
          onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
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
          inputProps={{ minLength: 8 }}
        />
        {isSpecialist && (
          <>
            <FormControl fullWidth required>
              <InputLabel>{t('admin.users.levelLabel')}</InputLabel>
              <Select
                value={form.specialistLevel ?? ''}
                label={t('admin.users.levelLabel')}
                onChange={(e) => setForm((f) => ({ ...f, specialistLevel: e.target.value as any }))}
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
                <MenuItem value="">
                  <em>—</em>
                </MenuItem>
                {cms.map((cm) => (
                  <MenuItem key={cm.id} value={cm.id}>
                    {cm.fullName}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </>
        )}
        {successMsg && <Alert severity="success">{successMsg}</Alert>}
        <Button
          type="submit"
          variant="contained"
          disabled={mutation.isPending}
          startIcon={mutation.isPending ? <CircularProgress size={16} /> : null}
        >
          {t('admin.users.create')}
        </Button>
      </Box>
    </Paper>
  );
}

function UserList() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'users', page],
    queryFn: () => listUsers(page),
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
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Email</TableCell>
            <TableCell>{t('admin.users.fullNameLabel')}</TableCell>
            <TableCell>{t('admin.users.roleLabel')}</TableCell>
            <TableCell>{t('admin.users.levelLabel')}</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {users.map((u) => (
            <TableRow key={u.id}>
              <TableCell>{u.email}</TableCell>
              <TableCell>{u.fullName}</TableCell>
              <TableCell>{t(`admin.users.roles.${u.role}`)}</TableCell>
              <TableCell>{u.specialistLevel ? t(`admin.users.levels.${u.specialistLevel}`) : '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {data && data.pages > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1, p: 2 }}>
          <Button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            ←
          </Button>
          <Typography sx={{ alignSelf: 'center' }}>
            {page} / {data.pages}
          </Typography>
          <Button disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)}>
            →
          </Button>
        </Box>
      )}
    </Paper>
  );
}

export default function UsersPage() {
  const { t } = useTranslation();

  // Load all users to populate CM dropdown (filter by role=cm client-side)
  const { data: allUsersData } = useQuery({
    queryKey: ['admin', 'users', 'all'],
    queryFn: () => listUsers(1, 100),
  });
  const cms = (allUsersData?.items ?? []).filter((u) => u.role === 'cm');

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" sx={{ mb: 3 }}>
        {t('admin.users.title')}
      </Typography>
      <CreateUserForm cms={cms} />
      <UserList />
    </Box>
  );
}
