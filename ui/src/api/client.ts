import type {
  AnalysisResponse, AuditEvent, EvidenceSpan, ImpactFields, PaperResponse, SpeciesNames, VerifiedChoice,
} from '../types'

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, text: string) {
    let body: unknown = text
    try { body = JSON.parse(text) } catch { /* not JSON */ }
    const detail = (body as { detail?: unknown })?.detail
    super(typeof detail === 'string' ? detail : text)
    this.status = status
    this.body = body
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) throw new ApiError(res.status, await res.text())
  if (res.status === 204) return undefined as T
  return res.json()
}

export interface ImpactPatch {
  fields?: ImpactFields
  evidence?: EvidenceSpan[]
  verified?: boolean
  note?: string
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

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
    // no paper ids runs every paper of the analysis
    run: (id: string, paperIds: string[] = [], verified?: VerifiedChoice) => {
      const params = new URLSearchParams(paperIds.map((p) => ['paper_id', p]))
      if (verified) params.set('verified', verified)
      const query = params.toString()
      return req<AnalysisResponse>(`/analyses/${id}/run${query ? `?${query}` : ''}`, { method: 'POST' })
    },
    cancelRun: (id: string, runId: string) =>
      req<AnalysisResponse>(`/analyses/${id}/runs/${runId}/cancel`, { method: 'POST' }),
    audit: (id: string, impactId?: string) =>
      req<AuditEvent[]>(`/analyses/${id}/audit${impactId ? `?impact_id=${encodeURIComponent(impactId)}` : ''}`),
  },
  impacts: {
    create: (aid: string, body: { paper_id: string; fields: ImpactFields; evidence: EvidenceSpan[]; note?: string }) =>
      req<AnalysisResponse>(`/analyses/${aid}/impacts`, json('POST', body)),
    patch: (aid: string, iid: string, body: ImpactPatch) =>
      req<AnalysisResponse>(`/analyses/${aid}/impacts/${iid}`, json('PATCH', body)),
    remove: (aid: string, iid: string, note?: string) =>
      req<AnalysisResponse>(`/analyses/${aid}/impacts/${iid}/remove`, json('POST', { note })),
    restore: (aid: string, iid: string, note?: string) =>
      req<AnalysisResponse>(`/analyses/${aid}/impacts/${iid}/restore`, json('POST', { note })),
  },
}
