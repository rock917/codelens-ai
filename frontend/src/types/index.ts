export interface Repository {
  id: string
  name: string
  source_type: string
  source_url?: string
  status: 'UPLOADING' | 'PARSING' | 'INDEXING' | 'ANALYZING' | 'READY' | 'FAILED'
  total_files: number
  processed_files: number
  total_chunks: number
  total_loc: number
  languages: string
  error_message?: string
  created_at: string
  updated_at: string
}

export interface FileRecord {
  id: string
  repository_id: string
  path: string
  language: string
  extension: string
  size: number
  loc: number
  num_classes: number
  num_functions: number
  complexity_score: number
  importance_score: number
  importance_level: 'HIGH' | 'MEDIUM' | 'LOW'
  summary?: string
}

export interface Symbol {
  id: string
  file_id: string
  name: string
  type: 'class' | 'function' | 'method'
  start_line: number
  end_line: number
  parent_name?: string
  signature?: string
  docstring?: string
  complexity: number
  file_path?: string
}

export interface AnalysisIssue {
  id: string
  file_path: string
  issue_type: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  message: string
  line: number
  suggestion: string
}

export interface AnalysisSummary {
  repository_id: string
  total_issues: number
  by_severity: Record<string, number>
  by_type: Record<string, number>
  health_score: number
}

export interface RepositoryStats {
  total_files: number
  total_loc: number
  total_chunks: number
  languages: Record<string, number>
  total_classes: number
  total_functions: number
  avg_complexity: number
  issues_count: number
  importance_breakdown: Record<string, number>
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceReference[]
  created_at: string
}

export interface SourceReference {
  file_path: string
  symbol_name: string
  symbol_type: string
  start_line: number
  end_line: number
  score: number
}

export interface Conversation {
  id: string
  repository_id: string
  title: string
  created_at: string
}

export interface SearchResult {
  file_path: string
  symbol_name: string
  symbol_type: string
  language: string
  start_line: number
  end_line: number
  content: string
  score: number
}