import { FaTrash, FaBug, FaMarkdown } from 'react-icons/fa';
import { useUploadById, useTaskState, useLoadingState, useExpandedContent, useUploadStore } from '../store/uploadStore';
import { API_ENDPOINTS } from '../config/api';
import MarkdownExpandedRow from './MarkdownExpandedRow';
import ImpactsExpandedRow from './ImpactsExpandedRow';

interface FileTableRowProps {
  uploadId: string;
  onDelete: (uploadId: string, filename: string) => void;
}

export default function FileTableRow({ uploadId, onDelete }: FileTableRowProps) {
  // Direct store subscriptions - only re-renders when this upload's data changes
  const upload = useUploadById(uploadId)
  const taskState = useTaskState(uploadId) || {
    isConverting: false,
    isExtracting: false,
    convertingTaskId: null,
    extractingTaskId: null
  }
  const loadingState = useLoadingState(uploadId) || {
    loadingMarkdown: false,
    loadingImpacts: false
  }
  const expandedContent = useExpandedContent(uploadId) || {
    markdown: null,
    impacts: null
  }
  
  // Store actions
  const { convertToMarkdown, extractImpacts, toggleMarkdown, toggleImpacts } = useUploadStore()

  if (!upload) return null

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatTimestamp = (timestamp: string): { date: string; time: string } => {
    const dateObj = new Date(timestamp)
    const date = dateObj.toISOString().split('T')[0]
    const time = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    return { date, time }
  }

  return (
    <>
      <tr>
        <td>
          <div>
            <a href={API_ENDPOINTS.download(upload.id)} className="file-link" download>
              {upload.filename}
            </a>
          </div>
          <div className="file-details">
            <table className="w-full details-table">
              <tbody>
                <tr>
                  <td className="file-detail-label">Type:</td>
                  <td>{upload.content_type}</td>
                </tr>
                <tr>
                  <td className="file-detail-label">Size:</td>
                  <td>{formatFileSize(upload.size)}</td>
                </tr>
                <tr>
                  <td className="file-detail-label">Uploaded:</td>
                  <td>{formatTimestamp(upload.timestamp).date}, {formatTimestamp(upload.timestamp).time}</td>
                </tr>
                {upload.markdown_available && (
                  <tr>
                    <td className="file-detail-label">Markdown:</td>
                    <td>
                      {loadingState.loadingMarkdown ? (
                        <span className="loading-text">Loading...</span>
                      ) : (
                        <a className="toggle-link" onClick={() => toggleMarkdown(uploadId)}>
                          {expandedContent.markdown ? "Hide" : "Show"}
                        </a>
                      )}
                    </td>
                  </tr>
                )}
                {upload.impacts_available && (
                  <tr>
                    <td className="file-detail-label">Impacts:</td>
                    <td>
                      {loadingState.loadingImpacts ? (
                        <span className="loading-text">Loading...</span>
                      ) : (
                        <a className="toggle-link" onClick={() => toggleImpacts(uploadId)}>
                          {expandedContent.impacts ? "Hide" : "Show"}
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
          <div className="action-buttons">
            <button
              className={`action-button-convert ${upload.markdown_available || taskState.isConverting
                  ? 'action-button-convert-disabled'
                  : 'action-button-convert-enabled'
                }`}
              title={
                upload.markdown_available
                  ? "Markdown already available"
                  : taskState.isConverting
                    ? "Converting to markdown..."
                    : "Convert to Markdown"
              }
              onClick={() => convertToMarkdown(uploadId, upload.filename)}
              disabled={upload.markdown_available || taskState.isConverting}
            >
              {taskState.isConverting ? (
                <div className="spinner spinner-yellow"></div>
              ) : (
                <FaMarkdown className="action-icon" />
              )}
            </button>

            <button
              className={`action-button-extract ${upload.markdown_available && !taskState.isExtracting
                  ? 'action-button-extract-enabled'
                  : 'action-button-extract-disabled'
                }`}
              title={
                !upload.markdown_available
                  ? "Markdown conversion required before data extraction"
                  : taskState.isExtracting
                    ? "Extracting impacts..."
                    : upload.impacts_available
                      ? "Extract Data (Already Extracted)"
                      : "Extract Data"
              }
              onClick={() => extractImpacts(uploadId, upload.filename)}
              disabled={!upload.markdown_available || taskState.isExtracting}
            >
              {taskState.isExtracting ? (
                <div className="spinner spinner-indigo"></div>
              ) : (
                <FaBug className="action-icon" />
              )}
            </button>

            <button
              className="action-button-delete"
              title="Delete Upload"
              onClick={() => onDelete(uploadId, upload.filename)}
            >
              <FaTrash className="action-icon" />
            </button>
          </div>
        </td>
      </tr>

      {/* Expanded content rows */}
      {expandedContent.markdown && (
        <MarkdownExpandedRow uploadId={uploadId} paper={expandedContent.markdown} />
      )}
      {expandedContent.impacts && (
        <ImpactsExpandedRow uploadId={uploadId} impacts={expandedContent.impacts} />
      )}
    </>
  )
}