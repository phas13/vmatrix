import {
  AppBar,
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useTheme } from '@mui/material';

const DRAWER_WIDTH = 240;

const navItems = [
  { labelKey: 'nav.dashboard', path: '/cm/dashboard', icon: <DashboardIcon /> },
];

export default function CMLayout() {
  const theme = useTheme();
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();

  const toggleLang = () => {
    const next = i18n.language === 'uk' ? 'en' : 'uk';
    i18n.changeLanguage(next);
    localStorage.setItem('vmatrix_lang', next);
  };

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{ zIndex: theme.zIndex.drawer + 1, bgcolor: 'primary.main' }}
        elevation={0}
      >
        <Toolbar>
          <Typography variant="h4" sx={{ flexGrow: 1, color: '#FFFFFF' }}>
            vmatrix
          </Typography>
          <Typography
            component="button"
            onClick={toggleLang}
            sx={{ cursor: 'pointer', border: 'none', bgcolor: 'transparent', color: '#FFFFFF', fontWeight: 500 }}
          >
            {t('lang.switch')}
          </Typography>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' },
        }}
      >
        <Toolbar />
        <List>
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <ListItem key={item.path} disablePadding>
                <ListItemButton
                  onClick={() => navigate(item.path)}
                  sx={{
                    borderLeft: isActive ? `3px solid ${theme.palette.primary.main}` : '3px solid transparent',
                    bgcolor: isActive ? 'primary.light' : 'transparent',
                    '& .MuiListItemText-primary': { fontWeight: isActive ? 500 : 400 },
                  }}
                >
                  <ListItemIcon sx={{ color: isActive ? 'primary.main' : 'inherit' }}>
                    {item.icon}
                  </ListItemIcon>
                  <ListItemText primary={t(item.labelKey)} />
                </ListItemButton>
              </ListItem>
            );
          })}
        </List>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 8 }}>
        <Outlet />
      </Box>
    </Box>
  );
}
