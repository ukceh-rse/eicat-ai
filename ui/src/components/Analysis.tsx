import { Link } from 'react-router';
import { useState, useEffect } from 'react';
import { FaUpload, FaTrash } from 'react-icons/fa';
import ReactMarkdown from 'react-markdown';
import type { UploadMetadata, TaskStatus, Paper } from '../types';
import { FaMarkdown } from "react-icons/fa";

const API_BASE_URL = 'http://localhost:8000';

export default function Analysis() {
  const [uploads, setUploads] = useState<UploadMetadata[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [convertingTasks, setConvertingTasks] = useState<Map<string, string>>(new Map()) // upload_id -> task_id
  const [expandedMarkdown, setExpandedMarkdown] = useState<Map<string, Paper>>(new Map()) // upload_id -> paper
  const [loadingMarkdown, setLoadingMarkdown] = useState<string | null>(null)

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

  // Poll task statuses every 10 seconds
  useEffect(() => {
    const pollInterval = setInterval(async () => {
      if (convertingTasks.size === 0) return

      const taskPromises = Array.from(convertingTasks.entries()).map(async ([uploadId, taskId]) => {
        try {
          const response = await fetch(`${API_BASE_URL}/analysis/tasks/${taskId}/status`)
          if (!response.ok) return null

          const taskStatus: TaskStatus = await response.json()
          return { uploadId, taskId, taskStatus }
        } catch (err) {
          console.error(`Failed to poll task ${taskId}:`, err)
          return null
        }
      })

      const results = await Promise.all(taskPromises)

      let shouldRefreshUploads = false
      const newConvertingTasks = new Map(convertingTasks)

      results.forEach((result) => {
        if (!result) return

        const { uploadId, taskId, taskStatus } = result

        if (taskStatus.status === 'completed') {
          // Task completed - remove from converting tasks and refresh uploads to show markdown_available
          newConvertingTasks.delete(uploadId)
          shouldRefreshUploads = true
        } else if (taskStatus.status === 'failed') {
          // Task failed - remove from converting tasks and show error
          newConvertingTasks.delete(uploadId)
          alert(`Conversion failed: ${taskStatus.error || 'Unknown error'}`)
        }
        // For 'started' and 'processing' statuses, keep polling
      })

      setConvertingTasks(newConvertingTasks)

      // Refresh uploads list if any task completed
      if (shouldRefreshUploads) {
        try {
          const response = await fetch(`${API_BASE_URL}/uploads/`)
          if (response.ok) {
            const data = await response.json()
            setUploads(data)
          }
        } catch (err) {
          console.error('Failed to refresh uploads:', err)
        }
      }
    }, 10000) // Poll every 10 seconds

    return () => clearInterval(pollInterval)
  }, [convertingTasks])

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

      // Remove the deleted upload from the state and clear any expanded markdown
      setUploads(uploads.filter(upload => upload.id !== uploadId))
      setExpandedMarkdown(prev => {
        const newMap = new Map(prev)
        newMap.delete(uploadId)
        return newMap
      })
    } catch (err) {
      alert(`Failed to delete file: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleConvertToMarkdown = async (uploadId: string, filename: string) => {
    if (!confirm(`Convert "${filename}" to markdown? This may take a few minutes.`)) {
      return
    }

    try {
      const response = await fetch(`${API_BASE_URL}/analysis/to-markdown/${uploadId}`, {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()

      // Add task to converting tasks map
      setConvertingTasks(prev => new Map(prev).set(uploadId, result.task_id))

    } catch (err) {
      alert(`Failed to start conversion: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleToggleMarkdown = async (upload: UploadMetadata) => {
    // If already expanded, collapse it
    if (expandedMarkdown.has(upload.id)) {
      setExpandedMarkdown(prev => {
        const newMap = new Map(prev)
        newMap.delete(upload.id)
        return newMap
      })
      return
    }

    // Otherwise, load and expand
    setLoadingMarkdown(upload.id)
    try {
      const response = await fetch(`${API_BASE_URL}/analysis/get-markdown/${upload.id}`)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const paper: Paper = await response.json()
      setExpandedMarkdown(prev => new Map(prev).set(upload.id, paper))
    } catch (err) {
      alert(`Failed to load markdown: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setLoadingMarkdown(null)
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatTimestamp = (timestamp: string): { date: string; time: string } => {
    const dateObj = new Date(timestamp)
    const date = dateObj.toISOString().split('T')[0] // yyyy-mm-dd format
    const time = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    return { date, time }
  }

  const isConverting = (uploadId: string): boolean => {
    return convertingTasks.has(uploadId)
  }

  const isMarkdownExpanded = (uploadId: string): boolean => {
    return expandedMarkdown.has(uploadId)
  }

  if (loading) {
    return (
      <div className="card">
        <h1 className="text-3xl font-bold">Analysis</h1>
        <p>Loading uploads...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <h1 className="text-3xl font-bold">Analysis</h1>
        <p className="text-red-600">Error: {error}</p>
        <p>Please try refreshing the page or check your connection.</p>
      </div>
    )
  }

  return (
    <div className="card">
      <h1 className="text-3xl font-bold">Analysis</h1>
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
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {uploads.map((upload) => (
                <>
                  <tr key={upload.id}>
                    <td>
                      <div>
                        <a
                          href={`${API_BASE_URL}/uploads/${upload.id}/download`}
                          className="text-lg font-bold text-blue-600 hover:text-blue-900 hover:underline"
                          download
                        >
                          {upload.filename}
                        </a>
                      </div>
                      <div className="text-xs text-gray-400 pl-4">
                        <table className="w-full details-table">
                          <tbody>
                            <tr>
                              <td className="pr-4 font-medium">Type:</td>
                              <td>{upload.content_type}</td>
                            </tr>
                            <tr>
                              <td className="pr-4 font-medium">Size:</td>
                              <td>{formatFileSize(upload.size)}</td>
                            </tr>
                            <tr>
                              <td className="pr-4 font-medium">Uploaded:</td>
                              <td>{formatTimestamp(upload.timestamp).date}, {formatTimestamp(upload.timestamp).time}</td>
                            </tr>
                            {upload.markdown_available && (
                              <tr>
                                <td className="pr-4 font-medium">Markdown:</td>
                                <td>
                                  {loadingMarkdown === upload.id ? (
                                    <span className="text-gray-500 text-xs">Loading...</span>
                                  ) : (
                                    <a
                                      className="text-blue-600 hover:text-blue-900 hover:underline text-xs cursor-pointer"
                                      onClick={() => handleToggleMarkdown(upload)}
                                    >
                                      {isMarkdownExpanded(upload.id) ? "Hide" : "Show"}
                                    </a>
                                  )}
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </td>
                    <td className="cell-actions">
                      <div className="flex gap-2">
                        {/* Convert to markdown button - always visible, disabled if markdown available or converting */}
                        <button
                          className={`p-1 rounded ${
                            upload.markdown_available || isConverting(upload.id)
                              ? 'text-gray-400 cursor-not-allowed'
                              : 'text-green-600 hover:text-green-900 hover:bg-green-50'
                          }`}
                          title={
                            upload.markdown_available 
                              ? "Markdown already available" 
                              : isConverting(upload.id)
                              ? "Converting to markdown..."
                              : "Convert to Markdown"
                          }
                          onClick={() => handleConvertToMarkdown(upload.id, upload.filename)}
                          disabled={upload.markdown_available || isConverting(upload.id)}
                        >
                          {isConverting(upload.id) ? (
                            <div className="animate-spin h-5 w-5 border-2 border-yellow-600 border-t-transparent rounded-full"></div>
                          ) : (
                            <FaMarkdown className="h-5 w-5" />
                          )}
                        </button>

                        <button
                          className={`p-1 hover:bg-indigo-50 rounded ${
                            upload.markdown_available 
                              ? 'text-indigo-600 hover:text-indigo-900' 
                              : 'text-gray-400 cursor-not-allowed'
                          }`}
                          title={upload.markdown_available ? "Extract Data" : "Markdown conversion required before data extraction"}
                          disabled={!upload.markdown_available}
                        >
                          <FaUpload className="h-5 w-5" />
                        </button>
                        <button
                          className="text-red-600 hover:text-red-900 p-1 hover:bg-red-50 rounded"
                          title="Delete Upload"
                          onClick={() => handleDelete(upload.id, upload.filename)}
                        >
                          <FaTrash className="h-5 w-5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {isMarkdownExpanded(upload.id) && (
                    <tr key={`${upload.id}-markdown`}>
                      <td colSpan={2} className="p-4">{(() => {
                          const paper = expandedMarkdown.get(upload.id)!
                          return (
                            <div className="md-content max-h-96 overflow-y-auto" style={{
                              wordWrap: 'break-word',
                              overflowWrap: 'break-word',
                              width: '100%',
                              whiteSpace: 'pre-wrap'
                            }}>
                              <ReactMarkdown>
                                {paper.content}
                              </ReactMarkdown>
                            </div>
                          )
                        })()}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
