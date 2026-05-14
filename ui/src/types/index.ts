export type PaperStatus = 'converting' | 'ready' | 'failed'
export type AnalysisStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface PaperResponse {
  id: string
  filename: string
  content_type: string
  size: number
  uploaded_at: string
  status: PaperStatus
  error?: string
}

export interface SpeciesNames {
  scientific_name: string
  vernacular_names: string[]
}

export interface Impact {
  alien_species: string
  mechanism: string
  category: string
  evidence: string
  confidence?: string
  justification: string
  impacted_species: string[]
}

export interface AnalysisResponse {
  id: string
  species: SpeciesNames
  created_at: string
  status: AnalysisStatus
  paper_ids: string[]
  results: Record<string, Impact[]>
  error?: string
  completed_at?: string
}
