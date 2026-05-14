import { create } from 'zustand'
import { api } from '../api/client'
import type { PaperResponse } from '../types'

interface PapersState {
  papers: PaperResponse[]
  loading: boolean
  fetch: () => Promise<void>
  upload: (file: File) => Promise<void>
  remove: (id: string) => Promise<void>
}

export const usePapersStore = create<PapersState>((set) => ({
  papers: [],
  loading: false,
  fetch: async () => {
    set({ loading: true })
    const papers = await api.papers.list()
    set({ papers, loading: false })
  },
  upload: async (file) => {
    const paper = await api.papers.upload(file)
    set((s) => ({ papers: [...s.papers, paper] }))
  },
  remove: async (id) => {
    await api.papers.delete(id)
    set((s) => ({ papers: s.papers.filter((p) => p.id !== id) }))
  },
}))
