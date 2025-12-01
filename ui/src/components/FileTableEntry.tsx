import { useEffect } from 'react';
import { useUploadStore } from '../store/uploadStore';
import type { UploadMetadata } from '../types';
import FileTableRow from './FileTableRow';
import MarkdownExpandedRow from './MarkdownExpandedRow';
import ImpactsExpandedRow from './ImpactsExpandedRow';

interface FileTableEntryProps {
  upload: UploadMetadata;
  onDelete: (uploadId: string, filename: string) => void;
}

export default function FileTableEntry({
  upload,
  onDelete,
}: FileTableEntryProps) {
  const {
    getTaskState,
    getLoadingState,
    expandedMarkdown,
    expandedImpacts,
    convertToMarkdown,
    extractImpacts,
    loadMarkdown,
    loadImpacts,
    startTaskPolling
  } = useUploadStore()

  const taskState = getTaskState(upload.id)
  const loadingState = getLoadingState(upload.id)
  const currentExpandedMarkdown = expandedMarkdown[upload.id]
  const currentExpandedImpacts = expandedImpacts[upload.id]

  // Start polling when component mounts and there are active tasks
  useEffect(() => {
    if (taskState.isConverting || taskState.isExtracting) {
      startTaskPolling()
    }
  }, [taskState.isConverting, taskState.isExtracting, startTaskPolling])

  const handleConvertToMarkdown = async (uploadId: string, filename: string) => {
    await convertToMarkdown(uploadId, filename)
  }

  const handleExtractImpacts = async (uploadId: string, filename: string) => {
    await extractImpacts(uploadId, filename)
  }

  const handleToggleMarkdown = async () => {
    await loadMarkdown(upload.id)
  }

  const handleToggleImpacts = async () => {
    await loadImpacts(upload.id)
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
        isConverting={taskState.isConverting}
        isExtracting={taskState.isExtracting}
        isMarkdownExpanded={!!currentExpandedMarkdown}
        isImpactsExpanded={!!currentExpandedImpacts}
        loadingMarkdown={loadingState.loadingMarkdown}
        loadingImpacts={loadingState.loadingImpacts}
      />
      {currentExpandedMarkdown && (
        <MarkdownExpandedRow
          uploadId={upload.id}
          paper={currentExpandedMarkdown}
        />
      )}
      {currentExpandedImpacts && (
        <ImpactsExpandedRow
          uploadId={upload.id}
          impacts={currentExpandedImpacts}
        />
      )}
    </>
  )
}