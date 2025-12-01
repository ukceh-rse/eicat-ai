import { Link } from 'react-router';
import { useEffect } from 'react';
import { useUploadStore } from '../store/uploadStore';
import FileTableRow from './FileTableRow';

export default function Analysis() {
  const { uploads, loading, error, fetchUploads, deleteUpload, setError } = useUploadStore()

  useEffect(() => {
    fetchUploads()
  }, [fetchUploads])

  const handleDelete = async (uploadId: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return
    await deleteUpload(uploadId)
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
        <button 
          onClick={() => {
            setError(null)
            fetchUploads()
          }}
          className="button-primary"
        >
          Retry
        </button>
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
          <Link to="/upload" className="link-primary">Upload</Link>{' '}
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
                <FileTableRow
                  key={upload.id}
                  uploadId={upload.id}
                  onDelete={handleDelete}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}