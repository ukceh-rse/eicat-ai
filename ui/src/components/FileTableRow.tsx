import { FaTrash, FaBug, FaMarkdown, FaSearch } from 'react-icons/fa';
import { useState, useEffect } from 'react';
import { useUploadById, useTaskState, useLoadingState, useExpandedContent, useSpeciesState, useUploadStore } from '../store/uploadStore';
import { API_ENDPOINTS } from '../config/api';
import MarkdownExpandedRow from './MarkdownExpandedRow';
import ImpactsExpandedRow from './ImpactsExpandedRow';
import SpeciesSearchModal from './SpeciesSearchModal';
import type { SpeciesNames } from '../types';

interface FileTableRowProps {
  uploadId: string;
  onDelete: (uploadId: string, filename: string) => void;
}

export default function FileTableRow({ uploadId, onDelete }: FileTableRowProps) {
  // Local state for species modal
  const [showSpeciesModal, setShowSpeciesModal] = useState(false);
  
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
  const speciesState = useSpeciesState(uploadId) || {
    selectedSpecies: null,
    loadingSpecies: false,
    hasAttemptedLoad: false
  }
  
  // Store actions
  const { convertToMarkdown, extractImpacts, toggleMarkdown, toggleImpacts, setSpeciesForUpload, loadSpeciesForUpload } = useUploadStore()

  // Load species data when component mounts - only attempt once
  useEffect(() => {
    if (upload && !speciesState.hasAttemptedLoad) {
      loadSpeciesForUpload(uploadId);
    }
  }, [upload, uploadId, loadSpeciesForUpload, speciesState.hasAttemptedLoad]);

  const handleSpeciesSelected = async (species: SpeciesNames) => {
    await setSpeciesForUpload(uploadId, species);
    setShowSpeciesModal(false);
  };

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
                {speciesState.selectedSpecies && (
                  <tr>
                    <td className="file-detail-label">Species:</td>
                    <td>
                      <div className="species-info">
                        <span className="scientific-name">{speciesState.selectedSpecies.scientific_name}</span>
                        {speciesState.selectedSpecies.vernacular_names.length > 0 && (
                          <span className="vernacular-names">
                            ({speciesState.selectedSpecies.vernacular_names.join(', ')})
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
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
                <div className="spinner"></div>
              ) : (
                <FaMarkdown className="action-icon" />
              )}
            </button>

            <button
              className={`action-button-species ${speciesState.selectedSpecies 
                  ? 'action-button-species-selected'
                  : 'action-button-species-enabled'
                }`}
              title={
                speciesState.loadingSpecies
                  ? "Loading species information..."
                  : speciesState.selectedSpecies
                    ? `Species selected: ${speciesState.selectedSpecies.scientific_name}`
                    : "Select Species for Analysis"
              }
              onClick={() => setShowSpeciesModal(true)}
              disabled={speciesState.loadingSpecies}
            >
              {speciesState.loadingSpecies ? (
                <div className="spinner"></div>
              ) : (
                <FaSearch className="action-icon" />
              )}
            </button>

            <button
              className={`action-button-extract ${
                upload.markdown_available && speciesState.selectedSpecies && !taskState.isExtracting
                  ? 'action-button-extract-enabled'
                  : 'action-button-extract-disabled'
                }`}
              title={
                !upload.markdown_available
                  ? "Markdown conversion required before data extraction"
                  : !speciesState.selectedSpecies
                    ? "Species selection required before data extraction"
                    : taskState.isExtracting
                      ? "Extracting impacts..."
                      : upload.impacts_available
                        ? "Extract Data (Already Extracted)"
                        : "Extract Data"
              }
              onClick={() => extractImpacts(uploadId, upload.filename)}
              disabled={!upload.markdown_available || !speciesState.selectedSpecies || taskState.isExtracting}
            >
              {taskState.isExtracting ? (
                <div className="spinner"></div>
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
      
      {/* Species Search Modal */}
      <SpeciesSearchModal
        isOpen={showSpeciesModal}
        onClose={() => setShowSpeciesModal(false)}
        onSpeciesSelected={handleSpeciesSelected}
        currentSpecies={speciesState.selectedSpecies}
      />
    </>
  )
}