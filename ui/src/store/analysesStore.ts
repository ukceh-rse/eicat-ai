import { create } from 'zustand'
import { api } from '../api/client'
import type { AnalysisResponse, SpeciesNames } from '../types'

interface AnalysesState {
  analyses: AnalysisResponse[]
  loading: boolean
  fetch: () => Promise<void>
  create: (species: SpeciesNames) => Promise<AnalysisResponse>
  remove: (id: string) => Promise<void>
  addPaper: (aid: string, pid: string) => Promise<void>
  removePaper: (aid: string, pid: string) => Promise<void>
  run: (id: string) => Promise<void>
  refresh: (id: string) => Promise<void>
}

export const useAnalysesStore = create<AnalysesState>((set) => ({
  analyses: [],
  loading: false,
  fetch: async () => {
    set({ loading: true })
    const analyses = await api.analyses.list()
    set({ analyses, loading: false })
  },
  create: async (species) => {
    const analysis = await api.analyses.create(species)
    set((s) => ({ analyses: [...s.analyses, analysis] }))
    return analysis
  },
  remove: async (id) => {
    await api.analyses.delete(id)
    set((s) => ({ analyses: s.analyses.filter((a) => a.id !== id) }))
  },
  addPaper: async (aid, pid) => {
    const updated = await api.analyses.addPaper(aid, pid)
    set((s) => ({ analyses: s.analyses.map((a) => (a.id === aid ? updated : a)) }))
  },
  removePaper: async (aid, pid) => {
    const updated = await api.analyses.removePaper(aid, pid)
    set((s) => ({ analyses: s.analyses.map((a) => (a.id === aid ? updated : a)) }))
  },
  run: async (id) => {
    const updated = await api.analyses.run(id)
    set((s) => ({ analyses: s.analyses.map((a) => (a.id === id ? updated : a)) }))
  },
  refresh: async (id) => {
    const updated = await api.analyses.get(id)
    set((s) => ({ analyses: s.analyses.map((a) => (a.id === id ? updated : a)) }))
  },
}))
