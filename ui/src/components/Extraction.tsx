import { Link } from 'react-router'
import { useState, useEffect } from 'react'
import { ArrowUpOnSquareIcon, TrashIcon } from '@heroicons/react/24/outline'

const API_BASE_URL = 'http://localhost:8000';

interface UploadMetadata {
  id: string
  filename: string
  content_type: string
  size: number
  timestamp: string
}

export default function Extraction() {
  const [uploads, setUploads] = useState<UploadMetadata[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
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

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatTimestamp = (timestamp: string): string => {
    return new Date(timestamp).toLocaleString()
  }

  if (loading) {
    return (
      <div className="card">
        <h1 className="text-3xl font-bold">Data Extraction</h1>
        <p>Loading uploads...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <h1 className="text-3xl font-bold">Data Extraction</h1>
        <p className="text-red-600">Error: {error}</p>
        <p>Please try refreshing the page or check your connection.</p>
      </div>
    )
  }

  return (
    <div className="card">
      <h1 className="text-3xl font-bold">Data Extraction</h1>
      <p className="mb-4">This page contains a list of texts ready to perform data extraction on.</p>

      {uploads.length === 0 ? (
        <p>
          No uploaded texts found. Please first upload a text on the{' '}
          <Link to="/upload" className="text-blue-600 hover:underline">
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
                <th>Size</th>
                <th>Upload Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {uploads.map((upload) => (
                <tr key={upload.id}>
                  <td>
                    <div className="cell-primary">
                      <a
                        href={`${API_BASE_URL}/uploads/${upload.id}/download`}
                        className="text-blue-600 hover:text-blue-900 hover:underline"
                        download
                      >
                        {upload.filename}
                      </a>
                    </div>
                    <div className="cell-secondary">{upload.content_type}</div>
                  </td>
                  <td className="cell-regular">
                    {formatFileSize(upload.size)}
                  </td>
                  <td className="cell-regular">
                    {formatTimestamp(upload.timestamp)}
                  </td>
                  <td className="cell-actions">
                    <div className="flex gap-2">
                      <button 
                        className="text-indigo-600 hover:text-indigo-900 p-1 hover:bg-indigo-50 rounded"
                        title="Extract Data"
                      >
                        <ArrowUpOnSquareIcon className="h-5 w-5" />
                      </button>
                      <button 
                        className="text-red-600 hover:text-red-900 p-1 hover:bg-red-50 rounded"
                        title="Delete Upload"
                        onClick={() => handleDelete(upload.id, upload.filename)}
                      >
                        <TrashIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
