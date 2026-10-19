import { create } from 'zustand'
import { api, ApiError, type ImpactPatch } from '../api/client'
import type { AnalysisResponse, EvidenceSpan, ImpactFields, SpeciesNames, VerifiedChoice } from '../types'

interface AnalysesState {
  analyses: AnalysisResponse[]
  loading: boolean
  fetch: () => Promise<void>
  create: (species: SpeciesNames) => Promise<AnalysisResponse>
  remove: (id: string) => Promise<void>
  addPaper: (aid: string, pid: string) => Promise<void>
  removePaper: (aid: string, pid: string) => Promise<void>
  run: (id: string, verified?: VerifiedChoice) => Promise<void>
  refresh: (id: string) => Promise<void>
  createImpact: (aid: string, paperId: string, fields: ImpactFields, evidence: EvidenceSpan[], note?: string) => Promise<void>
  patchImpact: (aid: string, iid: string, body: ImpactPatch) => Promise<void>
  removeImpact: (aid: string, iid: string, note?: string) => Promise<void>
  restoreImpact: (aid: string, iid: string, note?: string) => Promise<void>
}

// review actions replace the analysis with the response; on a conflict (running, or changed by another request)
// the analysis is refetched before the error is passed on, so the UI shows the current state
async function review(aid: string, action: () => Promise<AnalysisResponse>) {
  try {
    const updated = await action()
    useAnalysesStore.setState((s) => ({ analyses: s.analyses.map((a) => (a.id === aid ? updated : a)) }))
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) await useAnalysesStore.getState().refresh(aid)
    throw e
  }
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
  run: async (id, verified) => {
    const updated = await api.analyses.run(id, verified)
    set((s) => ({ analyses: s.analyses.map((a) => (a.id === id ? updated : a)) }))
  },
  refresh: async (id) => {
    const updated = await api.analyses.get(id)
    set((s) => ({ analyses: s.analyses.map((a) => (a.id === id ? updated : a)) }))
  },
  createImpact: (aid, paperId, fields, evidence, note) =>
    review(aid, () => api.impacts.create(aid, { paper_id: paperId, fields, evidence, note })),
  patchImpact: (aid, iid, body) => review(aid, () => api.impacts.patch(aid, iid, body)),
  removeImpact: (aid, iid, note) => review(aid, () => api.impacts.remove(aid, iid, note)),
  restoreImpact: (aid, iid, note) => review(aid, () => api.impacts.restore(aid, iid, note)),
}))
