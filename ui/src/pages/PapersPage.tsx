import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert, Box, CircularProgress, IconButton, Paper,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Tooltip, Typography,
} from '@mui/material'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import DeleteIcon from '@mui/icons-material/Delete'
import DownloadIcon from '@mui/icons-material/Download'
import { useNavigate } from 'react-router'
import { api } from '../api/client'
import { usePapersStore } from '../store/papersStore'
import { PaperStatusChip } from '../components/StatusChips'
import ConfirmDeleteDialog from '../components/ConfirmDeleteDialog'

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1_048_576) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1_048_576).toFixed(1)} MB`
}

export default function PapersPage() {
  const { papers, loading, fetch, upload, remove } = usePapersStore()
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<{ id: string; filename: string } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => { fetch() }, [fetch])

  useEffect(() => {
    if (!papers.some((p) => p.status === 'converting')) return
    const id = setInterval(fetch, 3000)
    return () => clearInterval(id)
  }, [papers, fetch])

  const handleFiles = useCallback(async (files: FileList | null) => {
    if (!files?.length) return
    setError(null)
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        if (file.type !== 'application/pdf') {
          setError(`${file.name} is not a PDF — skipped.`)
          continue
        }
        await upload(file)
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setUploading(false)
    }
  }, [upload])

  return (
    <Box>
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 2 }}>Papers</Typography>

      <Paper
        variant="outlined"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }}
        sx={{
          p: 5, mb: 3, textAlign: 'center', cursor: 'pointer', borderStyle: 'dashed',
          bgcolor: dragging ? 'action.hover' : 'transparent',
          transition: 'background-color 0.15s',
          '&:hover': { bgcolor: 'action.hover' },
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          multiple
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
        {uploading ? (
          <CircularProgress size={32} />
        ) : (
          <>
            <UploadFileIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
            <Typography color="text.secondary">
              Drag &amp; drop PDFs here, or click to browse
            </Typography>
          </>
        )}
      </Paper>

      {error && (
        <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loading && !papers.length ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Filename</TableCell>
                <TableCell>Size</TableCell>
                <TableCell>Uploaded</TableCell>
                <TableCell>Status</TableCell>
                <TableCell width={72} />
              </TableRow>
            </TableHead>
            <TableBody>
              {papers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 6, color: 'text.disabled' }}>
                    No papers uploaded yet
                  </TableCell>
                </TableRow>
              ) : papers.map((p) => (
                <TableRow
                  key={p.id}
                  hover
                  sx={{ cursor: p.status === 'ready' ? 'pointer' : 'default' }}
                  onClick={() => { if (p.status === 'ready') navigate(`/papers/${p.id}`) }}
                >
                  <TableCell>{p.filename}</TableCell>
                  <TableCell>{formatBytes(p.size)}</TableCell>
                  <TableCell>{new Date(p.uploaded_at).toLocaleDateString()}</TableCell>
                  <TableCell><PaperStatusChip status={p.status} /></TableCell>
                  <TableCell padding="none" sx={{ whiteSpace: 'nowrap' }}>
                    <Tooltip title="Download PDF">
                      <IconButton
                        size="small"
                        component="a"
                        href={api.papers.download(p.id)}
                        download={p.filename}
                        onClick={(e) => e.stopPropagation()}
                        sx={{ mr: 0.5 }}
                      >
                        <DownloadIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton
                        size="small"
                        color="error"
                        sx={{ mr: 1 }}
                        onClick={(e) => { e.stopPropagation(); setPendingDelete({ id: p.id, filename: p.filename }) }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <ConfirmDeleteDialog
        open={!!pendingDelete}
        title="Delete paper?"
        message={`"${pendingDelete?.filename}" will be permanently deleted.`}
        onConfirm={() => remove(pendingDelete!.id)}
        onClose={() => setPendingDelete(null)}
      />
    </Box>
  )
}
