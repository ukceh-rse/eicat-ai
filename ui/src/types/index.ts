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

export type Reversibility = 'reversible' | 'irreversible' | 'unknown'

export interface Impact {
  alien_species: string
  mechanism: string
  category: string
  reversibility?: Reversibility | null
  evidence: string
  confidence?: string | null
  justification: string
  impacted_species: string[]
}

// a passage of the paper markdown; null offsets mean the AI's passage could not be found in the paper, and
// approximate means the AI's passage isn't in the paper word for word, so this is the closest passage to it
export interface EvidenceSpan {
  start: number | null
  end: number | null
  text: string
  approximate?: boolean
}

export interface Sighting {
  run_id: string
  at: string
  ai: Impact
  evidence: EvidenceSpan[]
}

export type VerifiedChoice = 'keep' | 'discard'

export interface AnalysisRun {
  id: string
  started_at: string
  completed_at?: string | null
  model: string
  usage: Record<string, number>
  verified_choice?: VerifiedChoice | null
  status: 'running' | 'completed' | 'failed'
}

export type ImpactOrigin = 'ai' | 'human'
export type ImpactState = 'active' | 'removed' | 'superseded' | 'suppressed'

export interface ReviewedImpact {
  id: string
  paper_id: string
  origin: ImpactOrigin
  run_id?: string | null
  ai?: Impact | null
  current: Impact
  evidence: EvidenceSpan[]
  // a reviewer changed the evidence spans; anchoring the AI's evidence to paper text is not a change
  evidence_edited: boolean
  verified: boolean
  state: ImpactState
  held_by?: string | null
  sightings: Sighting[]
}

// editable impact fields; evidence is set only as spans selected in the paper
export type ImpactFields = Partial<Omit<Impact, 'evidence'>>

export interface FieldChange {
  field: string
  old: unknown
  new: unknown
}

export interface AuditEvent {
  _id: string
  at: string
  analysis_id: string
  impact_id?: string | null
  run_id?: string | null
  actor: { kind: 'human' | 'ai' | 'system'; user_id: string | null }
  action: string
  changes: FieldChange[]
  note?: string | null
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
  runs: AnalysisRun[]
  impacts: ReviewedImpact[]
}
