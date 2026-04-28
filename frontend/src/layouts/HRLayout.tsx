import { AppBar, Box, Toolbar, Typography } from '@mui/material';
import { Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export default function HRLayout() {
  const { t, i18n } = useTranslation();

  const toggleLang = () => {
    const next = i18n.language === 'uk' ? 'en' : 'uk';
    i18n.changeLanguage(next);
    localStorage.setItem('vmatrix_lang', next);
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column' }}>
      <AppBar position="fixed" sx={{ bgcolor: 'background.paper', color: 'text.primary' }} elevation={0}>
        <Toolbar>
          <Typography variant="h4" sx={{ flexGrow: 1 }}>
            vmatrix
          </Typography>
          <Typography
            component="button"
            onClick={toggleLang}
            sx={{ cursor: 'pointer', border: 'none', bgcolor: 'transparent', color: 'primary.main', fontWeight: 500 }}
          >
            {t('lang.switch')}
          </Typography>
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 8 }}>
        <Outlet />
      </Box>
    </Box>
  );
}
