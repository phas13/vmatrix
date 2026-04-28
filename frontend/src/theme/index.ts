import { createTheme } from '@mui/material/styles';
import type { Shadows } from '@mui/material/styles';
import { palette } from './palette';
import { typography } from './typography';

const theme = createTheme({
  palette,
  typography,
  shadows: Array(25).fill('none') as Shadows,
  components: {
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: { root: { boxShadow: 'none' } },
    },
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: { root: { boxShadow: 'none', border: '1px solid #DDE3EA' } },
    },
  },
});

export default theme;
