export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const API_ENDPOINTS = {
  uploads: `${API_BASE_URL}/uploads/`,
  upload: (id: string) => `${API_BASE_URL}/uploads/${id}`,
  download: (id: string) => `${API_BASE_URL}/uploads/${id}/download`,
  toMarkdown: (id: string) => `${API_BASE_URL}/analysis/to-markdown/${id}`,
  extractImpacts: (id: string) => `${API_BASE_URL}/analysis/extract-impacts/${id}`,
  getMarkdown: (id: string) => `${API_BASE_URL}/analysis/get-markdown/${id}`,
  getImpacts: (id: string) => `${API_BASE_URL}/analysis/get-impacts/${id}`,
  taskStatus: (id: string) => `${API_BASE_URL}/analysis/tasks/${id}/status`,
} as const