import { AppBar, Box, Button, Divider, Toolbar, Typography } from '@mui/material'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import { useNavigate } from 'react-router'

export default function LandingPage() {
  const navigate = useNavigate()

  return (
    <Box sx={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      bgcolor: '#ffffff',
    }}>
      {/* Header bar — matches Layout AppBar */}
      <AppBar position="static" elevation={0} sx={{
        bgcolor: '#ffffff',
        borderBottom: '1px solid #E4EEE6',
      }}>
        <Toolbar>
          <Box component="img" src="/OneSTOP symbol.svg" alt="OneSTOP"
            sx={{ height: 28, mr: 1.5 }}
          />
          <Typography variant="h6" sx={{ fontWeight: 700, color: '#1E513D', letterSpacing: 0.5 }}>
            EICAT AI
          </Typography>
        </Toolbar>
      </AppBar>

      {/* Hero */}
      <Box sx={{
        flex: 1,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        px: 3,
        py: 8,
      }}>
        <Box component="img"
          src="/OneSTOP final logo-black.svg"
          alt="OneSTOP"
          sx={{ height: 108, mb: 6 }}
        />

        <Typography variant="h3" sx={{
          fontWeight: 700,
          color: '#1E513D',
          mb: 2,
          letterSpacing: '-0.5px',
        }}>
          EICAT AI
        </Typography>

        <Typography variant="h6" sx={{
          color: '#329B46',
          fontWeight: 500,
          mb: 3,
          letterSpacing: 0.2,
        }}>
          Automated impact assessment for invasive alien species
        </Typography>

        <Divider sx={{ width: 48, borderColor: '#3CBB54', borderWidth: 2, mb: 3 }} />

        <Typography sx={{
          color: 'text.secondary',
          maxWidth: 520,
          lineHeight: 1.8,
          mb: 5,
          fontSize: '1rem',
        }}>
          Upload published scientific literature, build species assessments, and
          let AI extract and classify environmental impacts using the EICAT framework —
          turning evidence into actionable conservation decisions.
        </Typography>

        <Button
          variant="contained"
          size="large"
          endIcon={<ArrowForwardIcon />}
          onClick={() => navigate('/papers')}
          sx={{ px: 4, py: 1.5, fontSize: '1rem' }}
        >
          Get Started
        </Button>
      </Box>

      {/* Footer */}
      <Box sx={{
        px: 4, py: 2,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        borderTop: '1px solid #E4EEE6',
        flexShrink: 0,
      }}>
        <Typography variant="caption" color="text.disabled">
          Part of the OneSTOP project · Funded by the European Union · Horizon Europe ID 101180559
        </Typography>
      </Box>
    </Box>
  )
}
