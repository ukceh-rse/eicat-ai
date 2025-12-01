import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { UploadMetadata, Paper, Impact, TaskStatus } from '../types'
import { API_ENDPOINTS } from '../config/api'

const SPECIES_NAMES = {
  "scientific_name": "Passer domesticus",
  "vernacular_names": ["house sparrow"]
}

interface TaskState {
  isConverting: boolean
  isExtracting: boolean
  convertingTaskId: string | null
  extractingTaskId: string | null
}

interface LoadingState {
  loadingMarkdown: boolean
  loadingImpacts: boolean
}

interface UploadStore {
  // Core data
  uploads: UploadMetadata[]
  loading: boolean
  error: string | null
  
  // Task states per upload
  taskStates: Record<string, TaskState>
  
  // Loading states per upload
  loadingStates: Record<string, LoadingState>
  
  // Expanded content per upload
  expandedMarkdown: Record<string, Paper | null>
  expandedImpacts: Record<string, Impact[] | null>
  
  // Upload form state
  uploadForm: {
    selectedFile: File | null
    uploading: boolean
    error: string | null
    uploadResult: UploadMetadata | null
  }
  
  // Actions
  setUploads: (uploads: UploadMetadata[]) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  
  // Task actions
  setTaskState: (uploadId: string, taskState: Partial<TaskState>) => void
  getTaskState: (uploadId: string) => TaskState
  
  // Loading actions
  setLoadingState: (uploadId: string, loadingState: Partial<LoadingState>) => void
  getLoadingState: (uploadId: string) => LoadingState
  
  // Expanded content actions
  setExpandedMarkdown: (uploadId: string, paper: Paper | null) => void
  setExpandedImpacts: (uploadId: string, impacts: Impact[] | null) => void
  
  // Upload form actions
  setUploadForm: (formState: Partial<UploadStore['uploadForm']>) => void
  resetUploadForm: () => void
  
  // Async actions
  fetchUploads: () => Promise<void>
  deleteUpload: (uploadId: string) => Promise<void>
  convertToMarkdown: (uploadId: string, filename: string) => Promise<void>
  extractImpacts: (uploadId: string, filename: string) => Promise<void>
  loadMarkdown: (uploadId: string) => Promise<void>
  loadImpacts: (uploadId: string) => Promise<void>
  uploadFile: (file: File) => Promise<void>
  
  // Task polling
  startTaskPolling: () => void
  stopTaskPolling: () => void
}

let pollInterval: number | null = null

export const useUploadStore = create<UploadStore>()(
  devtools(
    (set, get) => ({
      // Initial state
      uploads: [],
      loading: false,
      error: null,
      taskStates: {},
      loadingStates: {},
      expandedMarkdown: {},
      expandedImpacts: {},
      uploadForm: {
        selectedFile: null,
        uploading: false,
        error: null,
        uploadResult: null
      },
      
      // Basic setters
      setUploads: (uploads) => set({ uploads }),
      setLoading: (loading) => set({ loading }),
      setError: (error) => set({ error }),
      
      // Task state management
      setTaskState: (uploadId, taskState) => 
        set((state) => ({
          taskStates: {
            ...state.taskStates,
            [uploadId]: { ...get().getTaskState(uploadId), ...taskState }
          }
        })),
      
      getTaskState: (uploadId) => 
        get().taskStates[uploadId] || {
          isConverting: false,
          isExtracting: false,
          convertingTaskId: null,
          extractingTaskId: null
        },
      
      // Loading state management
      setLoadingState: (uploadId, loadingState) =>
        set((state) => ({
          loadingStates: {
            ...state.loadingStates,
            [uploadId]: { ...get().getLoadingState(uploadId), ...loadingState }
          }
        })),
      
      getLoadingState: (uploadId) =>
        get().loadingStates[uploadId] || {
          loadingMarkdown: false,
          loadingImpacts: false
        },
      
      // Expanded content management
      setExpandedMarkdown: (uploadId, paper) =>
        set((state) => ({
          expandedMarkdown: { ...state.expandedMarkdown, [uploadId]: paper }
        })),
      
      setExpandedImpacts: (uploadId, impacts) =>
        set((state) => ({
          expandedImpacts: { ...state.expandedImpacts, [uploadId]: impacts }
        })),
      
      // Upload form management
      setUploadForm: (formState) =>
        set((state) => ({
          uploadForm: { ...state.uploadForm, ...formState }
        })),
      
      resetUploadForm: () =>
        set({
          uploadForm: {
            selectedFile: null,
            uploading: false,
            error: null,
            uploadResult: null
          }
        }),
      
      // Async actions
      fetchUploads: async () => {
        set({ loading: true, error: null })
        try {
          const response = await fetch(API_ENDPOINTS.uploads)
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
          }
          const data = await response.json()
          set({ uploads: data, loading: false })
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to fetch uploads'
          set({ error: errorMessage, loading: false })
        }
      },
      
      deleteUpload: async (uploadId) => {
        try {
          const response = await fetch(API_ENDPOINTS.upload(uploadId), {
            method: 'DELETE',
          })
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
          }
          set((state) => ({
            uploads: state.uploads.filter(upload => upload.id !== uploadId)
          }))
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to delete upload'
          set({ error: errorMessage })
        }
      },
      
      convertToMarkdown: async (uploadId, filename) => {
        if (!confirm(`Convert "${filename}" to markdown? This may take a few minutes.`)) {
          return
        }
        
        try {
          const response = await fetch(API_ENDPOINTS.toMarkdown(uploadId), {
            method: 'POST',
          })
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
          }
          const result = await response.json()
          
          get().setTaskState(uploadId, {
            isConverting: true,
            convertingTaskId: result.task_id
          })
          
          get().startTaskPolling()
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to start conversion'
          alert(errorMessage)
        }
      },
      
      extractImpacts: async (uploadId, filename) => {
        if (!confirm(`Extract impacts from "${filename}"? This may take a few minutes.`)) {
          return
        }
        
        try {
          const response = await fetch(API_ENDPOINTS.extractImpacts(uploadId), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(SPECIES_NAMES),
          })
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
          }
          const result = await response.json()
          
          get().setTaskState(uploadId, {
            isExtracting: true,
            extractingTaskId: result.task_id
          })
          
          get().startTaskPolling()
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to start impact extraction'
          alert(errorMessage)
        }
      },
      
      loadMarkdown: async (uploadId) => {
        const currentPaper = get().expandedMarkdown[uploadId]
        if (currentPaper) {
          get().setExpandedMarkdown(uploadId, null)
          return
        }
        
        get().setLoadingState(uploadId, { loadingMarkdown: true })
        try {
          const response = await fetch(API_ENDPOINTS.getMarkdown(uploadId))
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
          }
          const paper: Paper = await response.json()
          get().setExpandedMarkdown(uploadId, paper)
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to load markdown'
          alert(errorMessage)
        } finally {
          get().setLoadingState(uploadId, { loadingMarkdown: false })
        }
      },
      
      loadImpacts: async (uploadId) => {
        const currentImpacts = get().expandedImpacts[uploadId]
        if (currentImpacts) {
          get().setExpandedImpacts(uploadId, null)
          return
        }
        
        get().setLoadingState(uploadId, { loadingImpacts: true })
        try {
          const response = await fetch(API_ENDPOINTS.getImpacts(uploadId))
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
          }
          const impacts: Impact[] = await response.json()
          get().setExpandedImpacts(uploadId, impacts)
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to load impacts'
          alert(errorMessage)
        } finally {
          get().setLoadingState(uploadId, { loadingImpacts: false })
        }
      },
      
      uploadFile: async (file) => {
        set((state) => ({
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
          set((state) => ({
            uploadForm: {
              ...state.uploadForm,
              uploading: false,
              uploadResult: result,
              selectedFile: null
            }
          }))
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Upload failed'
          set((state) => ({
            uploadForm: { ...state.uploadForm, uploading: false, error: errorMessage }
          }))
        }
      },
      
      // Task polling
      startTaskPolling: () => {
        if (pollInterval) return
        
        pollInterval = setInterval(async () => {
          const state = get()
          const activeTasks = Object.entries(state.taskStates).filter(([_, taskState]) => 
            taskState.isConverting || taskState.isExtracting
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
                    get().setTaskState(uploadId, { isConverting: false, convertingTaskId: null })
                    await get().fetchUploads() // Refresh uploads
                  } else if (taskStatus.status === 'failed') {
                    get().setTaskState(uploadId, { isConverting: false, convertingTaskId: null })
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
                    get().setTaskState(uploadId, { isExtracting: false, extractingTaskId: null })
                    await get().fetchUploads() // Refresh uploads
                  } else if (taskStatus.status === 'failed') {
                    get().setTaskState(uploadId, { isExtracting: false, extractingTaskId: null })
                    alert(`Impact extraction failed: ${taskStatus.error || 'Unknown error'}`)
                  }
                }
              }
            } catch (err) {
              console.error('Failed to poll task status:', err)
            }
          }
        }, 5000)
      },
      
      stopTaskPolling: () => {
        if (pollInterval) {
          clearInterval(pollInterval)
          pollInterval = null
        }
      }
    }),
    { name: 'upload-store' }
  )
)