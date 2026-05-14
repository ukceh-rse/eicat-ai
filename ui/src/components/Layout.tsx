import { AppBar, Box, Button, Container, Toolbar, Typography } from '@mui/material'
import { Outlet, useLocation, useNavigate } from 'react-router'

function NavButton({ to, label }: { to: string; label: string }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const active = pathname.startsWith(to)
  return (
    <Button
      onClick={() => navigate(to)}
      sx={{
        textTransform: 'none',
        fontWeight: active ? 600 : 400,
        color: active ? '#1E513D' : 'text.secondary',
        bgcolor: active ? '#E4EEE6' : undefined,
        '&:hover': { bgcolor: '#E4EEE6', color: '#1E513D' },
      }}
    >
      {label}
    </Button>
  )
}

export default function Layout() {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', bgcolor: 'background.default' }}>
      <AppBar position="static" elevation={0} sx={{
        bgcolor: '#ffffff',
        borderBottom: '1px solid #E4EEE6',
      }}>
        <Toolbar>
          <Box component="img" src="/OneSTOP symbol.svg" alt="OneSTOP" sx={{ height: 28, mr: 1.5 }} />
          <Typography variant="h6" sx={{ fontWeight: 700, mr: 4, color: '#1E513D', letterSpacing: 0.5 }}>
            EICAT AI
          </Typography>
          <NavButton to="/papers" label="Papers" />
          <NavButton to="/analyses" label="Analyses" />
        </Toolbar>
      </AppBar>
      <Box sx={{ flex: 1, overflowY: 'auto' }}>
        <Container maxWidth="lg" sx={{ py: 4 }}>
          <Outlet />
        </Container>
      </Box>
      <Box sx={{
        px: 4, py: 2,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        borderTop: '1px solid #E4EEE6',
        bgcolor: '#ffffff',
        flexShrink: 0,
      }}>
        <Typography variant="caption" color="text.disabled">
          Part of the OneSTOP project · Funded by the European Union · Horizon Europe ID 101180559
        </Typography>
      </Box>
    </Box>
  )
}
