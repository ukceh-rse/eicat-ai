import { useState } from 'react'
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material'
import type { VerifiedChoice } from '../types'

export interface RerunCounts {
  verified: number
  unverified: number
}

interface Props {
  counts: RerunCounts
  onRun: (verified: VerifiedChoice | undefined) => Promise<void>
  onClose: () => void
}

const plural = (n: number, word: string) => `${n} ${word} impact${n === 1 ? '' : 's'}`

// confirms a re-run, saying what happens to the existing AI impacts; discarding verified ones asks twice
export default function RerunDialog({ counts, onRun, onClose }: Props) {
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async (verified: VerifiedChoice | undefined) => {
    setBusy(true)
    try {
      await onRun(verified)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  const choice = counts.verified > 0 ? 'keep' : undefined

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{confirmDiscard ? 'Discard verified impacts?' : 'Re-run analysis'}</DialogTitle>
      <DialogContent>
        {confirmDiscard ? (
          <DialogContentText>
            {plural(counts.verified, 'verified')} and {plural(counts.unverified, 'unverified')} will be replaced by
            the new run's results. Your verifications and edits stay in each impact's history, but the impacts will
            no longer be shown.
          </DialogContentText>
        ) : (
          <DialogContentText>
            {counts.verified > 0 && <>{plural(counts.verified, 'verified')} will be kept and </>}
            {plural(counts.unverified, 'unverified')} will be replaced by the new run's results. Impacts you added
            or removed are not changed, and new AI impacts with the same mechanism as one of them are listed under
            Suppressed.
          </DialogContentText>
        )}
        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        {confirmDiscard ? (
          <Button color="error" variant="contained" disabled={busy} onClick={() => run('discard')}>
            Discard and run
          </Button>
        ) : (
          <>
            {counts.verified > 0 && (
              <Button color="error" disabled={busy} onClick={() => setConfirmDiscard(true)}>
                Discard verified
              </Button>
            )}
            <Button variant="contained" disabled={busy} onClick={() => run(choice)}>
              {counts.verified > 0 ? 'Keep verified and run' : 'Run'}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  )
}
