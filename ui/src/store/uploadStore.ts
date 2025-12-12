import { create } from 'zustand'
import { devtools, subscribeWithSelector } from 'zustand/middleware'
import type { UploadMetadata, Paper, Impact, TaskStatus, SpeciesNames } from '../types'
import { API_ENDPOINTS } from '../config/api'

interface UploadStore {
  // === CORE STATE ===
  uploads: UploadMetadata[]
  loading: boolean
  error: string | null
  
  // === UI STATE (per upload ID) ===
  taskStates: Record<string, {
    isConverting: boolean
    isExtracting: boolean
    convertingTaskId: string | null
    extractingTaskId: string | null
  }>
  
  loadingStates: Record<string, {
    loadingMarkdown: boolean
    loadingImpacts: boolean
  }>
  
  expandedContent: Record<string, {
    markdown: Paper | null
    impacts: Impact[] | null
  }>
  
  // === SPECIES STATE (per upload ID) ===
  speciesStates: Record<string, {
    selectedSpecies: SpeciesNames | null
    loadingSpecies: boolean
    hasAttemptedLoad: boolean
  }>
  
  // === UPLOAD FORM STATE ===
  uploadForm: {
    selectedFile: File | null
    uploading: boolean
    error: string | null
    uploadResult: UploadMetadata | null
  }
  
  // === BASIC ACTIONS ===
  setError: (error: string | null) => void
  resetUploadForm: () => void
  
  // === ASYNC ACTIONS ===
  fetchUploads: () => Promise<void>
  deleteUpload: (uploadId: string) => Promise<void>
  uploadFile: (file: File) => Promise<void>
  
  // === UPLOAD-SPECIFIC ACTIONS ===
  convertToMarkdown: (uploadId: string, filename: string) => Promise<void>
  extractImpacts: (uploadId: string, filename: string) => Promise<void>
  toggleMarkdown: (uploadId: string) => Promise<void>
  toggleImpacts: (uploadId: string) => Promise<void>
  
  // === SPECIES ACTIONS ===
  setSpeciesForUpload: (uploadId: string, species: SpeciesNames) => Promise<void>
  loadSpeciesForUpload: (uploadId: string) => Promise<void>
  
  // === FILE UPLOAD ACTIONS ===
  selectFile: (file: File | null) => void
  
  // === TASK POLLING ===
  startTaskPolling: () => void
  stopTaskPolling: () => void
}

let pollInterval: number | null = null

export const useUploadStore = create<UploadStore>()(
  devtools(
    subscribeWithSelector((set, get) => ({
      // === INITIAL STATE ===
      uploads: [],
      loading: false,
      error: null,
      taskStates: {},
      loadingStates: {},
      expandedContent: {},
      speciesStates: {},
      uploadForm: {
        selectedFile: null,
        uploading: false,
        error: null,
        uploadResult: null
      },
      
      // === BASIC ACTIONS ===
      setError: (error) => set({ error }),
      
      resetUploadForm: () => set({
        uploadForm: {
          selectedFile: null,
          uploading: false,
          error: null,
          uploadResult: null
        }
      }),
      
      selectFile: (file) => {
        if (!file) {
          get().resetUploadForm()
          return
        }
        
        const MAX_FILE_SIZE_MB = 3
        const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
        
        if (file.type !== 'application/pdf') {
          set(state => ({
            uploadForm: { ...state.uploadForm, error: 'Please select a PDF file.', selectedFile: null }
          }))
          return
        }
        
        if (file.size > MAX_FILE_SIZE_BYTES) {
          set(state => ({
            uploadForm: { 
              ...state.uploadForm, 
              error: `File size must be less than ${MAX_FILE_SIZE_MB}MB.`, 
              selectedFile: null 
            }
          }))
          return
        }
        
        set(state => ({
          uploadForm: { ...state.uploadForm, selectedFile: file, error: null }
        }))
      },
      
      // === ASYNC ACTIONS ===
      fetchUploads: async () => {
        set({ loading: true, error: null })
        try {
          const response = await fetch(API_ENDPOINTS.uploads)
          if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
          const data = await response.json()
          set({ uploads: data, loading: false })
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to fetch uploads'
          set({ error: errorMessage, loading: false })
        }
      },
      
      deleteUpload: async (uploadId) => {
        try {
          const response = await fetch(API_ENDPOINTS.upload(uploadId), { method: 'DELETE' })
          if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
          
          set(state => ({
            uploads: state.uploads.filter(upload => upload.id !== uploadId),
            // Clean up related state
            taskStates: Object.fromEntries(
              Object.entries(state.taskStates).filter(([id]) => id !== uploadId)
            ),
            loadingStates: Object.fromEntries(
              Object.entries(state.loadingStates).filter(([id]) => id !== uploadId)
            ),
            expandedContent: Object.fromEntries(
              Object.entries(state.expandedContent).filter(([id]) => id !== uploadId)
            ),
            speciesStates: Object.fromEntries(
              Object.entries(state.speciesStates).filter(([id]) => id !== uploadId)
            )
          }))
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to delete upload'
          set({ error: errorMessage })
        }
      },
      
      uploadFile: async (file) => {
        set(state => ({
          uploadForm: { ...state.uploadForm, uploading: true, error: null, uploadResult: null }
        }))
        
        try {
          const formData = new FormData()
          formData.append('file', file)
          
          const response = await fetch(API_ENDPOINTS.uploads, {
            method: 'POST',
            body: formData,
          })
          
          if (!response.ok) {
            const errorData = await response.json()
            throw new Error(errorData.detail || `Upload failed: ${response.statusText}`)
          }
          
          const result: UploadMetadata = await response.json()
          set(state => ({
            uploadForm: {
              ...state.uploadForm,
              uploading: false,
              uploadResult: result,
              selectedFile: null
            }
          }))
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Upload failed'
          set(state => ({
            uploadForm: { ...state.uploadForm, uploading: false, error: errorMessage }
          }))
        }
      },
      
      // === UPLOAD-SPECIFIC ACTIONS ===
      convertToMarkdown: async (uploadId, filename) => {
        if (!confirm(`Convert "${filename}" to markdown? This may take a few minutes.`)) return
        
        try {
          const response = await fetch(API_ENDPOINTS.toMarkdown(uploadId), { method: 'POST' })
          if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
          
          const result = await response.json()
          set(state => ({
            taskStates: {
              ...state.taskStates,
              [uploadId]: {
                ...state.taskStates[uploadId],
                isConverting: true,
                convertingTaskId: result.task_id
              }
            }
          }))
          
          get().startTaskPolling()
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to start conversion'
          alert(errorMessage)
        }
      },
      
      extractImpacts: async (uploadId, filename) => {
        // First check if species is selected
        const speciesState = get().speciesStates[uploadId]
        if (!speciesState?.selectedSpecies) {
          alert('Please select a species before extracting impacts.')
          return
        }

        if (!confirm(`Extract impacts from "${filename}"? This may take a few minutes.`)) return
        
        try {
          const response = await fetch(API_ENDPOINTS.extractImpacts(uploadId), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(speciesState.selectedSpecies),
          })
          if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
          
          const result = await response.json()
          set(state => ({
            taskStates: {
              ...state.taskStates,
              [uploadId]: {
                ...state.taskStates[uploadId],
                isExtracting: true,
                extractingTaskId: result.task_id
              }
            }
          }))
          
          get().startTaskPolling()
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to start impact extraction'
          alert(errorMessage)
        }
      },
      
      toggleMarkdown: async (uploadId) => {
        const current = get().expandedContent[uploadId]?.markdown
        if (current) {
          // Collapse
          set(state => ({
            expandedContent: {
              ...state.expandedContent,
              [uploadId]: { ...state.expandedContent[uploadId], markdown: null }
            }
          }))
          return
        }
        
        // Expand - load data
        set(state => ({
          loadingStates: {
            ...state.loadingStates,
            [uploadId]: { ...state.loadingStates[uploadId], loadingMarkdown: true }
          }
        }))
        
        try {
          const response = await fetch(API_ENDPOINTS.getMarkdown(uploadId))
          if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
          
          const paper: Paper = await response.json()
          set(state => ({
            expandedContent: {
              ...state.expandedContent,
              [uploadId]: { ...state.expandedContent[uploadId], markdown: paper }
            },
            loadingStates: {
              ...state.loadingStates,
              [uploadId]: { ...state.loadingStates[uploadId], loadingMarkdown: false }
            }
          }))
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to load markdown'
          alert(errorMessage)
          set(state => ({
            loadingStates: {
              ...state.loadingStates,
              [uploadId]: { ...state.loadingStates[uploadId], loadingMarkdown: false }
            }
          }))
        }
      },
      
      toggleImpacts: async (uploadId) => {
        const current = get().expandedContent[uploadId]?.impacts
        if (current) {
          // Collapse
          set(state => ({
            expandedContent: {
              ...state.expandedContent,
              [uploadId]: { ...state.expandedContent[uploadId], impacts: null }
            }
          }))
          return
        }
        
        // Expand - load data
        set(state => ({
          loadingStates: {
            ...state.loadingStates,
            [uploadId]: { ...state.loadingStates[uploadId], loadingImpacts: true }
          }
        }))
        
        try {
          const response = await fetch(API_ENDPOINTS.getImpacts(uploadId))
          if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
          
          const impacts: Impact[] = await response.json()
          set(state => ({
            expandedContent: {
              ...state.expandedContent,
              [uploadId]: { ...state.expandedContent[uploadId], impacts }
            },
            loadingStates: {
              ...state.loadingStates,
              [uploadId]: { ...state.loadingStates[uploadId], loadingImpacts: false }
            }
          }))
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to load impacts'
          alert(errorMessage)
          set(state => ({
            loadingStates: {
              ...state.loadingStates,
              [uploadId]: { ...state.loadingStates[uploadId], loadingImpacts: false }
            }
          }))
        }
      },

      // === SPECIES ACTIONS ===
      setSpeciesForUpload: async (uploadId, species) => {
        try {
          const response = await fetch(API_ENDPOINTS.setSpecies(uploadId), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(species)
          })
          
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
          }
          
          set(state => ({
            speciesStates: {
              ...state.speciesStates,
              [uploadId]: {
                ...state.speciesStates[uploadId],
                selectedSpecies: species,
                hasAttemptedLoad: true
              }
            }
          }))
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to set species'
          alert(errorMessage)
        }
      },

      loadSpeciesForUpload: async (uploadId) => {
        // Don't load if already attempted
        const currentState = get().speciesStates[uploadId]
        if (currentState?.hasAttemptedLoad) {
          return
        }

        set(state => ({
          speciesStates: {
            ...state.speciesStates,
            [uploadId]: {
              ...state.speciesStates[uploadId],
              loadingSpecies: true,
              hasAttemptedLoad: true
            }
          }
        }))

        try {
          const response = await fetch(API_ENDPOINTS.getSpecies(uploadId))
          
          if (response.ok) {
            const species: SpeciesNames = await response.json()
            set(state => ({
              speciesStates: {
                ...state.speciesStates,
                [uploadId]: {
                  ...state.speciesStates[uploadId],
                  selectedSpecies: species,
                  loadingSpecies: false
                }
              }
            }))
          } else if (response.status === 404) {
            // No species set yet - this is expected for new uploads
            set(state => ({
              speciesStates: {
                ...state.speciesStates,
                [uploadId]: {
                  ...state.speciesStates[uploadId],
                  selectedSpecies: null,
                  loadingSpecies: false
                }
              }
            }))
          } else {
            throw new Error(`HTTP error! status: ${response.status}`)
          }
        } catch (err) {
          console.error('Failed to load species:', err)
          set(state => ({
            speciesStates: {
              ...state.speciesStates,
              [uploadId]: {
                ...state.speciesStates[uploadId],
                loadingSpecies: false
              }
            }
          }))
        }
      },
      
      // === TASK POLLING ===
      startTaskPolling: () => {
        if (pollInterval) return
        
        pollInterval = setInterval(async () => {
          const state = get()
          const activeTasks = Object.entries(state.taskStates).filter(([_, taskState]) => 
            taskState?.isConverting || taskState?.isExtracting
          )
          
          if (activeTasks.length === 0) {
            get().stopTaskPolling()
            return
          }
          
          for (const [uploadId, taskState] of activeTasks) {
            try {
              // Check converting task
              if (taskState.convertingTaskId) {
                const response = await fetch(API_ENDPOINTS.taskStatus(taskState.convertingTaskId))
                if (response.ok) {
                  const taskStatus: TaskStatus = await response.json()
                  if (taskStatus.status === 'completed') {
                    set(state => ({
                      taskStates: {
                        ...state.taskStates,
                        [uploadId]: { ...taskState, isConverting: false, convertingTaskId: null }
                      }
                    }))
                    await get().fetchUploads()
                  } else if (taskStatus.status === 'failed') {
                    set(state => ({
                      taskStates: {
                        ...state.taskStates,
                        [uploadId]: { ...taskState, isConverting: false, convertingTaskId: null }
                      }
                    }))
                    alert(`Conversion failed: ${taskStatus.error || 'Unknown error'}`)
                  }
                }
              }
              
              // Check extracting task
              if (taskState.extractingTaskId) {
                const response = await fetch(API_ENDPOINTS.taskStatus(taskState.extractingTaskId))
                if (response.ok) {
                  const taskStatus: TaskStatus = await response.json()
                  if (taskStatus.status === 'completed') {
                    set(state => ({
                      taskStates: {
                        ...state.taskStates,
                        [uploadId]: { ...taskState, isExtracting: false, extractingTaskId: null }
                      }
                    }))
                    await get().fetchUploads()
                  } else if (taskStatus.status === 'failed') {
                    set(state => ({
                      taskStates: {
                        ...state.taskStates,
                        [uploadId]: { ...taskState, isExtracting: false, extractingTaskId: null }
                      }
                    }))
                    alert(`Impact extraction failed: ${taskStatus.error || 'Unknown error'}`)
                  }
                }
              }
            } catch (err) {
              console.error('Failed to poll task status:', err)
            }
          }
        }, 2000)
      },
      
      stopTaskPolling: () => {
        if (pollInterval) {
          clearInterval(pollInterval)
          pollInterval = null
        }
      }
    })),
    { name: 'upload-store' }
  )
)

// === SMART SELECTORS ===
// These can be used to subscribe to specific parts of state

export const useUploadById = (uploadId: string) => 
  useUploadStore(state => state.uploads.find(upload => upload.id === uploadId))

export const useTaskState = (uploadId: string) => 
  useUploadStore(state => state.taskStates[uploadId])

export const useLoadingState = (uploadId: string) => 
  useUploadStore(state => state.loadingStates[uploadId])

export const useExpandedContent = (uploadId: string) => 
  useUploadStore(state => state.expandedContent[uploadId])

export const useSpeciesState = (uploadId: string) => 
  useUploadStore(state => state.speciesStates[uploadId])