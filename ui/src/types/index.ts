export interface UploadMetadata {
  id: string;
  filename: string;
  content_type: string;
  size: number;
  timestamp: string;
  markdown_available: boolean;
  impacts_available: boolean;
}

export interface TaskStatus {
  status: 'started' | 'processing' | 'completed' | 'failed';
  progress?: string;
  timestamp: string;
  error?: string;
  upload_id?: string;
  result_available?: boolean;
}

export interface Paper {
  title: string;
  authors: string[];
  abstract: string;
  content: string;
  references: string[];
  metadata: Record<string, any>;
}

export interface SpeciesNames {
  scientific_name: string;
  vernacular_names: string[];
}

export interface Impact {
  alien_species: string;
  mechanism: string;
  category: string;
  evidence: string;
  confidence?: string;
  justification: string;
  impacted_species: string[];
}