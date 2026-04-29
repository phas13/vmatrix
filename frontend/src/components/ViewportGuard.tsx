import { Box, Typography } from '@mui/material';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTranslation } from 'react-i18next';

interface ViewportGuardProps {
  children: React.ReactNode;
}

export default function ViewportGuard({ children }: ViewportGuardProps) {
  const { t } = useTranslation();

  // SSR Guard
  if (typeof window === 'undefined') {
    return <>{children}</>;
  }

  const isMobile = useMediaQuery('(max-width: 767px)');

  if (isMobile) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          p: 4,
          bgcolor: 'background.default',
          textAlign: 'center',
        }}
      >
        <Typography variant="body1" color="text.secondary" maxWidth={360}>
          {t('viewport.mobileBlock')}
        </Typography>
      </Box>
    );
  }

  return <>{children}</>;
}
