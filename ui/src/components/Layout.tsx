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
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static" elevation={0} sx={{
        bgcolor: '#ffffff',
        borderBottom: '1px solid #E4EEE6',
      }}>
        <Toolbar>
          <Box component="img" src="/OneSTOP symbol.svg" alt="OneSTOP" sx={{ height: 32, mr: 1.5 }} />
          <Typography variant="h6" sx={{ fontWeight: 700, mr: 4, color: '#1E513D', letterSpacing: 0.5 }}>
            EICAT AI
          </Typography>
          <NavButton to="/papers" label="Papers" />
          <NavButton to="/analyses" label="Analyses" />
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: 4, flex: 1 }}>
        <Outlet />
      </Container>
    </Box>
  )
}
