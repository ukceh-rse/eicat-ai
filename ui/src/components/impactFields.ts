import type { EvidenceSpan, Impact, ReviewedImpact } from '../types'

// allowed values, as in the API's Mechanism and Category enums
export const MECHANISMS = [
  'Competition',
  'Predation',
  'Hybridisation',
  'Transmission of diseases to native species',
  'Parasitism',
  'Poisoning/toxicity',
  'Bio-fouling',
  'Grazing/herbivory/browsing',
  'Chemical Impact on ecosystem',
  'Physical Impact on ecosystem',
  'Structural Impact on ecosystem',
  'Indirect impacts through interactions with other species',
]
export const CATEGORIES = ['MV', 'MR', 'MO', 'MN', 'MC', 'DD']
export const REVERSIBILITIES = ['reversible', 'irreversible', 'unknown'] as const
export const CONFIDENCES = ['Low', 'Medium', 'High'] as const
// reversibility applies only to categories that record a local extinction
export const needsReversibility = (category: string) => category === 'MR' || category === 'MV'

export const FIELD_LABELS: Record<string, string> = {
  alien_species: 'Alien species',
  mechanism: 'Mechanism',
  category: 'Category',
  reversibility: 'Reversibility',
  evidence: 'Evidence',
  confidence: 'Confidence',
  justification: 'Justification',
  impacted_species: 'Impacted species',
  verified: 'Verified',
  state: 'State',
  held_by: 'Held by',
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) {
    // evidence spans are recorded as span objects
    if (value.length > 0 && typeof value[0] === 'object') return (value as EvidenceSpan[]).map((s) => s.text).join(' … ')
    return value.join(', ') || '—'
  }
  return String(value)
}

// fields whose current value differs from the AI's original, with the AI value
export function changedFromAi(impact: ReviewedImpact): Partial<Record<keyof Impact, string>> {
  const changed: Partial<Record<keyof Impact, string>> = {}
  if (impact.origin !== 'ai' || !impact.ai) return changed
  for (const key of Object.keys(FIELD_LABELS) as (keyof Impact)[]) {
    if (!(key in impact.ai)) continue
    if (JSON.stringify(impact.ai[key] ?? null) !== JSON.stringify(impact.current[key] ?? null)) {
      changed[key] = formatValue(impact.ai[key])
    }
  }
  return changed
}
