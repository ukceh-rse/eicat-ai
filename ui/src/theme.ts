import { createTheme } from '@mui/material/styles'

export const theme = createTheme({
  palette: {
    primary: { main: '#3CBB54', dark: '#329B46', contrastText: '#fff' },
    background: { default: '#ffffff' },
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: "'Satoshi', sans-serif",
    h1: { fontFamily: "'Gabarito', sans-serif" },
    h2: { fontFamily: "'Gabarito', sans-serif" },
    h3: { fontFamily: "'Gabarito', sans-serif" },
    h4: { fontFamily: "'Gabarito', sans-serif" },
    h5: { fontFamily: "'Gabarito', sans-serif" },
    h6: { fontFamily: "'Gabarito', sans-serif" },
  },
  components: {
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiPaper: { defaultProps: { elevation: 0 } },
    MuiAppBar: {
      styleOverrides: {
        root: { backgroundImage: 'none' },
      },
    },
  },
})
