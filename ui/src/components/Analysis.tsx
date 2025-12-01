import { Link } from 'react-router';
import { useState, useEffect } from 'react';
import type { UploadMetadata } from '../types';
import FileTableEntry from './FileTableEntry';

const API_BASE_URL = 'http://localhost:8000';

export default function Analysis() {
  const [uploads, setUploads] = useState<UploadMetadata[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchUploads = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/uploads/`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      setUploads(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch uploads')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUploads()
  }, [])

  const handleDelete = async (uploadId: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
      return
    }

    try {
      const response = await fetch(`${API_BASE_URL}/uploads/${uploadId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      // Remove the deleted upload from the state
      setUploads(uploads.filter(upload => upload.id !== uploadId))
    } catch (err) {
      alert(`Failed to delete file: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h1 className="page-title">Analysis</h1>
        <p>Loading uploads...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <h1 className="page-title">Analysis</h1>
        <p className="error-message">Error: {error}</p>
        <p>Please try refreshing the page or check your connection.</p>
      </div>
    )
  }

  return (
    <div className="card">
      <h1 className="page-title">Analysis</h1>
      <p className="page-description">This page contains a list of texts ready to perform data extraction on.</p>

      {uploads.length === 0 ? (
        <p>
          No uploaded texts found. Please first upload a text on the{' '}
          <Link to="/upload" className="link-primary">
            Upload
          </Link>{' '}
          page.
        </p>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {uploads.map((upload) => (
                <FileTableEntry
                  key={upload.id}
                  upload={upload}
                  onDelete={handleDelete}
                  onUploadUpdated={fetchUploads}
                  apiBaseUrl={API_BASE_URL}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
