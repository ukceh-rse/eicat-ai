import { Link } from 'react-router';
import { useState, useEffect } from 'react';
import { FaTrash, FaBug } from 'react-icons/fa';
import ReactMarkdown from 'react-markdown';
import type { UploadMetadata, TaskStatus, Paper, Impact } from '../types';
import { FaMarkdown } from "react-icons/fa";

const API_BASE_URL = 'http://localhost:8000';
const SPECIES_NAMES = {
  "scientific_name": "Passer domesticus",
  "vernacular_names": [
    "house sparrow"
  ]
}

export default function Analysis() {
  const [uploads, setUploads] = useState<UploadMetadata[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [convertingTasks, setConvertingTasks] = useState<Map<string, string>>(new Map()) // upload_id -> task_id
  const [extractingTasks, setExtractingTasks] = useState<Map<string, string>>(new Map()) // upload_id -> task_id
  const [expandedMarkdown, setExpandedMarkdown] = useState<Map<string, Paper>>(new Map()) // upload_id -> paper
  const [expandedImpacts, setExpandedImpacts] = useState<Map<string, Impact[]>>(new Map()) // upload_id -> impacts
  const [loadingMarkdown, setLoadingMarkdown] = useState<string | null>(null)
  const [loadingImpacts, setLoadingImpacts] = useState<string | null>(null)

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
      const allTasks = new Map([...convertingTasks, ...extractingTasks])
      if (allTasks.size === 0) return

      const taskPromises = Array.from(allTasks.entries()).map(async ([uploadId, taskId]) => {
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
      const newExtractingTasks = new Map(extractingTasks)

      results.forEach((result) => {
        if (!result) return

        const { uploadId, taskStatus } = result

        if (taskStatus.status === 'completed') {
          // Task completed - remove from appropriate tasks and refresh uploads
          if (convertingTasks.has(uploadId)) {
            newConvertingTasks.delete(uploadId)
          }
          if (extractingTasks.has(uploadId)) {
            newExtractingTasks.delete(uploadId)
          }
          shouldRefreshUploads = true
        } else if (taskStatus.status === 'failed') {
          // Task failed - remove from tasks and show error
          if (convertingTasks.has(uploadId)) {
            newConvertingTasks.delete(uploadId)
            alert(`Conversion failed: ${taskStatus.error || 'Unknown error'}`)
          }
          if (extractingTasks.has(uploadId)) {
            newExtractingTasks.delete(uploadId)
            alert(`Impact extraction failed: ${taskStatus.error || 'Unknown error'}`)
          }
        }
        // For 'started' and 'processing' statuses, keep polling
      })

      setConvertingTasks(newConvertingTasks)
      setExtractingTasks(newExtractingTasks)

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
  }, [convertingTasks, extractingTasks])

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

      // Remove the deleted upload from the state and clear any expanded content
      setUploads(uploads.filter(upload => upload.id !== uploadId))
      setExpandedMarkdown(prev => {
        const newMap = new Map(prev)
        newMap.delete(uploadId)
        return newMap
      })
      setExpandedImpacts(prev => {
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

  const handleExtractImpacts = async (uploadId: string, filename: string) => {
    if (!confirm(`Extract impacts from "${filename}"? This may take a few minutes.`)) {
      return
    }

    try {
      const response = await fetch(`${API_BASE_URL}/analysis/extract-impacts/${uploadId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(SPECIES_NAMES),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()

      // Add task to extracting tasks map
      setExtractingTasks(prev => new Map(prev).set(uploadId, result.task_id))

    } catch (err) {
      alert(`Failed to start impact extraction: ${err instanceof Error ? err.message : 'Unknown error'}`)
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

  const handleToggleImpacts = async (upload: UploadMetadata) => {
    // If already expanded, collapse it
    if (expandedImpacts.has(upload.id)) {
      setExpandedImpacts(prev => {
        const newMap = new Map(prev)
        newMap.delete(upload.id)
        return newMap
      })
      return
    }

    // Otherwise, load and expand
    setLoadingImpacts(upload.id)
    try {
      const response = await fetch(`${API_BASE_URL}/analysis/get-impacts/${upload.id}`)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const impacts: Impact[] = await response.json()
      setExpandedImpacts(prev => new Map(prev).set(upload.id, impacts))
    } catch (err) {
      alert(`Failed to load impacts: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setLoadingImpacts(null)
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

  const isExtracting = (uploadId: string): boolean => {
    return extractingTasks.has(uploadId)
  }

  const isMarkdownExpanded = (uploadId: string): boolean => {
    return expandedMarkdown.has(uploadId)
  }

  const isImpactsExpanded = (uploadId: string): boolean => {
    return expandedImpacts.has(uploadId)
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
                            {upload.impacts_available && (
                              <tr>
                                <td className="pr-4 font-medium">Impacts:</td>
                                <td>
                                  {loadingImpacts === upload.id ? (
                                    <span className="text-gray-500 text-xs">Loading...</span>
                                  ) : (
                                    <a
                                      className="text-blue-600 hover:text-blue-900 hover:underline text-xs cursor-pointer"
                                      onClick={() => handleToggleImpacts(upload)}
                                    >
                                      {isImpactsExpanded(upload.id) ? "Hide" : "Show"}
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
                          className={`p-1 rounded ${upload.markdown_available || isConverting(upload.id)
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
                          className={`p-1 hover:bg-indigo-50 rounded ${upload.markdown_available && !isExtracting(upload.id)
                              ? 'text-indigo-600 hover:text-indigo-900'
                              : 'text-gray-400 cursor-not-allowed'
                            }`}
                          title={
                            !upload.markdown_available
                              ? "Markdown conversion required before data extraction"
                              : isExtracting(upload.id)
                                ? "Extracting impacts..."
                                : upload.impacts_available
                                  ? "Extract Data (Already Extracted)"
                                  : "Extract Data"
                          }
                          onClick={() => handleExtractImpacts(upload.id, upload.filename)}
                          disabled={!upload.markdown_available || isExtracting(upload.id)}
                        >
                          {isExtracting(upload.id) ? (
                            <div className="animate-spin h-5 w-5 border-2 border-indigo-600 border-t-transparent rounded-full"></div>
                          ) : (
                            <FaBug className="h-5 w-5" />
                          )}
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
                  {isImpactsExpanded(upload.id) && (
                    <tr key={`${upload.id}-impacts`}>
                      <td colSpan={2} className="p-4">{(() => {
                        const impacts = expandedImpacts.get(upload.id)!
                        return (
                          <div className="impacts-content max-h-96 overflow-y-auto">
                            <h4 className="font-bold mb-3 text-gray-800">
                              Extracted Impacts ({impacts.length} found)
                            </h4>
                            {impacts.length === 0 ? (
                              <p className="text-gray-500 italic">No impacts found in this paper.</p>
                            ) : (
                              <div className="overflow-x-auto">
                                <table className="w-full text-sm border-collapse border border-gray-300">
                                  <thead>
                                    <tr className="bg-gray-100">
                                      <th className="border border-gray-300 px-2 py-1 text-left font-medium">Species</th>
                                      <th className="border border-gray-300 px-2 py-1 text-left font-medium">Mechanism</th>
                                      <th className="border border-gray-300 px-2 py-1 text-left font-medium">Category</th>
                                      <th className="border border-gray-300 px-2 py-1 text-left font-medium">Confidence</th>
                                      <th className="border border-gray-300 px-2 py-1 text-left font-medium">Impacted Species</th>
                                      <th className="border border-gray-300 px-2 py-1 text-left font-medium">Evidence</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {impacts.map((impact, index) => (
                                      <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                        <td className="border border-gray-300 px-2 py-1 font-medium">
                                          {impact.alien_species}
                                        </td>
                                        <td className="border border-gray-300 px-2 py-1">
                                          {impact.mechanism}
                                        </td>
                                        <td className="border border-gray-300 px-2 py-1 font-medium">
                                          <span className={`px-1 py-0.5 rounded text-xs font-bold ${
                                            impact.category === 'MV' ? 'bg-red-100 text-red-800' :
                                            impact.category === 'MR' ? 'bg-red-100 text-red-600' :
                                            impact.category === 'MO' ? 'bg-orange-100 text-orange-800' :
                                            impact.category === 'MN' ? 'bg-yellow-100 text-yellow-800' :
                                            impact.category === 'MC' ? 'bg-green-100 text-green-800' :
                                            'bg-gray-100 text-gray-800'
                                          }`}>
                                            {impact.category}
                                          </span>
                                        </td>
                                        <td className="border border-gray-300 px-2 py-1">
                                          {impact.confidence || 'N/A'}
                                        </td>
                                        <td className="border border-gray-300 px-2 py-1">
                                          {impact.impacted_species.length > 0 
                                            ? impact.impacted_species.join(', ') 
                                            : 'Not specified'
                                          }
                                        </td>
                                        <td className="border border-gray-300 px-2 py-1 text-xs max-w-xs">
                                          <div className="truncate" title={impact.evidence}>
                                            {impact.evidence.length > 100 
                                              ? `${impact.evidence.substring(0, 100)}...` 
                                              : impact.evidence
                                            }
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
