export interface UploadMetadata {
  id: string;
  filename: string;
  content_type: string;
  size: number;
  timestamp: string;
  markdown_available: boolean;
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