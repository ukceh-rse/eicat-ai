import { FaTrash, FaBug, FaMarkdown } from 'react-icons/fa';
import type { UploadMetadata } from '../types';

interface FileTableRowProps {
  upload: UploadMetadata;
  onDelete: (uploadId: string, filename: string) => void;
  onConvertToMarkdown: (uploadId: string, filename: string) => void;
  onExtractImpacts: (uploadId: string, filename: string) => void;
  onToggleMarkdown: (upload: UploadMetadata) => void;
  onToggleImpacts: (upload: UploadMetadata) => void;
  isConverting: boolean;
  isExtracting: boolean;
  isMarkdownExpanded: boolean;
  isImpactsExpanded: boolean;
  loadingMarkdown: boolean;
  loadingImpacts: boolean;
  apiBaseUrl: string;
}

export default function FileTableRow({
  upload,
  onDelete,
  onConvertToMarkdown,
  onExtractImpacts,
  onToggleMarkdown,
  onToggleImpacts,
  isConverting,
  isExtracting,
  isMarkdownExpanded,
  isImpactsExpanded,
  loadingMarkdown,
  loadingImpacts,
  apiBaseUrl,
}: FileTableRowProps) {
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

  return (
    <tr key={upload.id}>
      <td>
        <div>
          <a
            href={`${apiBaseUrl}/uploads/${upload.id}/download`}
            className="file-link"
            download
          >
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
                    {loadingMarkdown ? (
                      <span className="loading-text">Loading...</span>
                    ) : (
                      <a
                        className="toggle-link"
                        onClick={() => onToggleMarkdown(upload)}
                      >
                        {isMarkdownExpanded ? "Hide" : "Show"}
                      </a>
                    )}
                  </td>
                </tr>
              )}
              {upload.impacts_available && (
                <tr>
                  <td className="file-detail-label">Impacts:</td>
                  <td>
                    {loadingImpacts ? (
                      <span className="loading-text">Loading...</span>
                    ) : (
                      <a
                        className="toggle-link"
                        onClick={() => onToggleImpacts(upload)}
                      >
                        {isImpactsExpanded ? "Hide" : "Show"}
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
          {/* Convert to markdown button - always visible, disabled if markdown available or converting */}
          <button
            className={`action-button-convert ${upload.markdown_available || isConverting
                ? 'action-button-convert-disabled'
                : 'action-button-convert-enabled'
              }`}
            title={
              upload.markdown_available
                ? "Markdown already available"
                : isConverting
                  ? "Converting to markdown..."
                  : "Convert to Markdown"
            }
            onClick={() => onConvertToMarkdown(upload.id, upload.filename)}
            disabled={upload.markdown_available || isConverting}
          >
            {isConverting ? (
              <div className="spinner spinner-yellow"></div>
            ) : (
              <FaMarkdown className="action-icon" />
            )}
          </button>

          <button
            className={`action-button-extract ${upload.markdown_available && !isExtracting
                ? 'action-button-extract-enabled'
                : 'action-button-extract-disabled'
              }`}
            title={
              !upload.markdown_available
                ? "Markdown conversion required before data extraction"
                : isExtracting
                  ? "Extracting impacts..."
                  : upload.impacts_available
                    ? "Extract Data (Already Extracted)"
                    : "Extract Data"
            }
            onClick={() => onExtractImpacts(upload.id, upload.filename)}
            disabled={!upload.markdown_available || isExtracting}
          >
            {isExtracting ? (
              <div className="spinner spinner-indigo"></div>
            ) : (
              <FaBug className="action-icon" />
            )}
          </button>
          <button
            className="action-button-delete"
            title="Delete Upload"
            onClick={() => onDelete(upload.id, upload.filename)}
          >
            <FaTrash className="action-icon" />
          </button>
        </div>
      </td>
    </tr>
  )
}