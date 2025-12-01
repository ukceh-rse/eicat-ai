import { useState, useEffect } from 'react';
import type { UploadMetadata, Paper, Impact, TaskStatus } from '../types';
import FileTableRow from './FileTableRow';
import MarkdownExpandedRow from './MarkdownExpandedRow';
import ImpactsExpandedRow from './ImpactsExpandedRow';

interface FileTableEntryProps {
  upload: UploadMetadata;
  onDelete: (uploadId: string, filename: string) => void;
  onUploadUpdated: () => void; // Callback when upload status changes (for refreshing main list)
  apiBaseUrl: string;
}

const SPECIES_NAMES = {
  "scientific_name": "Passer domesticus",
  "vernacular_names": [
    "house sparrow"
  ]
}

export default function FileTableEntry({
  upload,
  onDelete,
  onUploadUpdated,
  apiBaseUrl,
}: FileTableEntryProps) {
  // Local state for this specific file entry
  const [isConverting, setIsConverting] = useState(false)
  const [isExtracting, setIsExtracting] = useState(false)
  const [convertingTaskId, setConvertingTaskId] = useState<string | null>(null)
  const [extractingTaskId, setExtractingTaskId] = useState<string | null>(null)
  const [expandedMarkdown, setExpandedMarkdown] = useState<Paper | null>(null)
  const [expandedImpacts, setExpandedImpacts] = useState<Impact[] | null>(null)
  const [loadingMarkdown, setLoadingMarkdown] = useState(false)
  const [loadingImpacts, setLoadingImpacts] = useState(false)

  // Poll for task completion
  useEffect(() => {
    if (!convertingTaskId && !extractingTaskId) return

    const pollInterval = setInterval(async () => {
      try {
        // Check converting task
        if (convertingTaskId) {
          const response = await fetch(`${apiBaseUrl}/analysis/tasks/${convertingTaskId}/status`)
          if (response.ok) {
            const taskStatus: TaskStatus = await response.json()
            if (taskStatus.status === 'completed') {
              setIsConverting(false)
              setConvertingTaskId(null)
              onUploadUpdated() // Notify parent to refresh upload list
            } else if (taskStatus.status === 'failed') {
              setIsConverting(false)
              setConvertingTaskId(null)
              alert(`Conversion failed: ${taskStatus.error || 'Unknown error'}`)
            }
          }
        }

        // Check extracting task  
        if (extractingTaskId) {
          const response = await fetch(`${apiBaseUrl}/analysis/tasks/${extractingTaskId}/status`)
          if (response.ok) {
            const taskStatus: TaskStatus = await response.json()
            if (taskStatus.status === 'completed') {
              setIsExtracting(false)
              setExtractingTaskId(null)
              onUploadUpdated() // Notify parent to refresh upload list
            } else if (taskStatus.status === 'failed') {
              setIsExtracting(false)
              setExtractingTaskId(null)
              alert(`Impact extraction failed: ${taskStatus.error || 'Unknown error'}`)
            }
          }
        }
      } catch (err) {
        console.error('Failed to poll task status:', err)
      }
    }, 5000) // Poll every 5 seconds

    return () => clearInterval(pollInterval)
  }, [convertingTaskId, extractingTaskId, apiBaseUrl, onUploadUpdated])

  const handleConvertToMarkdown = async (uploadId: string, filename: string) => {
    if (!confirm(`Convert "${filename}" to markdown? This may take a few minutes.`)) {
      return
    }

    try {
      const response = await fetch(`${apiBaseUrl}/analysis/to-markdown/${uploadId}`, {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      setIsConverting(true)
      setConvertingTaskId(result.task_id)

    } catch (err) {
      alert(`Failed to start conversion: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleExtractImpacts = async (uploadId: string, filename: string) => {
    if (!confirm(`Extract impacts from "${filename}"? This may take a few minutes.`)) {
      return
    }

    try {
      const response = await fetch(`${apiBaseUrl}/analysis/extract-impacts/${uploadId}`, {
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
      setIsExtracting(true)
      setExtractingTaskId(result.task_id)

    } catch (err) {
      alert(`Failed to start impact extraction: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleToggleMarkdown = async (upload: UploadMetadata) => {
    // If already expanded, collapse it
    if (expandedMarkdown) {
      setExpandedMarkdown(null)
      return
    }

    // Otherwise, load and expand
    setLoadingMarkdown(true)
    try {
      const response = await fetch(`${apiBaseUrl}/analysis/get-markdown/${upload.id}`)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const paper: Paper = await response.json()
      setExpandedMarkdown(paper)
    } catch (err) {
      alert(`Failed to load markdown: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setLoadingMarkdown(false)
    }
  }

  const handleToggleImpacts = async (upload: UploadMetadata) => {
    // If already expanded, collapse it
    if (expandedImpacts) {
      setExpandedImpacts(null)
      return
    }

    // Otherwise, load and expand
    setLoadingImpacts(true)
    try {
      const response = await fetch(`${apiBaseUrl}/analysis/get-impacts/${upload.id}`)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const impacts: Impact[] = await response.json()
      setExpandedImpacts(impacts)
    } catch (err) {
      alert(`Failed to load impacts: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setLoadingImpacts(false)
    }
  }

  return (
    <>
      <FileTableRow
        upload={upload}
        onDelete={onDelete}
        onConvertToMarkdown={handleConvertToMarkdown}
        onExtractImpacts={handleExtractImpacts}
        onToggleMarkdown={handleToggleMarkdown}
        onToggleImpacts={handleToggleImpacts}
        isConverting={isConverting}
        isExtracting={isExtracting}
        isMarkdownExpanded={!!expandedMarkdown}
        isImpactsExpanded={!!expandedImpacts}
        loadingMarkdown={loadingMarkdown}
        loadingImpacts={loadingImpacts}
        apiBaseUrl={apiBaseUrl}
      />
      {expandedMarkdown && (
        <MarkdownExpandedRow
          uploadId={upload.id}
          paper={expandedMarkdown}
        />
      )}
      {expandedImpacts && (
        <ImpactsExpandedRow
          uploadId={upload.id}
          impacts={expandedImpacts}
        />
      )}
    </>
  )
}