import type { AnalysisResponse, PaperResponse, SpeciesNames } from '../types'

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) throw new Error(await res.text())
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  papers: {
    list: () => req<PaperResponse[]>('/papers/'),
    upload: (file: File) => {
      const body = new FormData()
      body.append('file', file)
      return req<PaperResponse>('/papers/', { method: 'POST', body })
    },
    delete: (id: string) => req<void>(`/papers/${id}`, { method: 'DELETE' }),
    content: (id: string) => req<{ content: string }>(`/papers/${id}/content`),
    download: (id: string) => `${BASE}/papers/${id}/download`,
  },
  analyses: {
    list: () => req<AnalysisResponse[]>('/analyses/'),
    create: (species: SpeciesNames) =>
      req<AnalysisResponse>('/analyses/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(species),
      }),
    get: (id: string) => req<AnalysisResponse>(`/analyses/${id}`),
    delete: (id: string) => req<void>(`/analyses/${id}`, { method: 'DELETE' }),
    addPaper: (aid: string, pid: string) =>
      req<AnalysisResponse>(`/analyses/${aid}/papers/${pid}`, { method: 'POST' }),
    removePaper: (aid: string, pid: string) =>
      req<AnalysisResponse>(`/analyses/${aid}/papers/${pid}`, { method: 'DELETE' }),
    run: (id: string) =>
      req<AnalysisResponse>(`/analyses/${id}/run`, { method: 'POST' }),
  },
}
