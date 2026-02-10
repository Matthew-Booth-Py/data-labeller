/**
 * API client for Unstructured Unlocked backend
 */

// Base URL for API calls - configurable via environment variable
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

// ============================================================================
// Types
// ============================================================================

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  version: string;
  services: {
    vector_db: string;
    neo4j: string;
    openai: string;
  };
  stats: {
    documents: number;
    graph: GraphStats;
  };
}

export interface GraphStats {
  documents: number;
  persons: number;
  organizations: number;
  locations: number;
  events: number;
  relationships: number;
}

export interface DocumentMetadata {
  filename: string;
  file_type: string;
  file_size?: number;
  date_extracted?: string;
  page_count?: number;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  content: string;
  chunk_index: number;
  metadata: Record<string, unknown>;
}

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  content: string;
  date_extracted?: string;
  created_at: string;
  metadata: DocumentMetadata;
  chunks: DocumentChunk[];
}

export interface DocumentSummary {
  id: string;
  filename: string;
  file_type: string;
  date_extracted?: string;
  created_at: string;
  chunk_count: number;
}

export interface IngestResponse {
  status: 'success' | 'partial';
  documents_processed: number;
  chunks_created: number;
  processing_time_seconds: number;
  document_ids: string[];
  errors: string[];
}

export interface TimelineDocument {
  id: string;
  filename: string;
  file_type: string;
  title?: string;
  excerpt?: string;
}

export interface TimelineEntry {
  date: string;
  document_count: number;
  documents: TimelineDocument[];
}

export interface DateRange {
  earliest?: string;
  latest?: string;
}

export interface TimelineResponse {
  timeline: TimelineEntry[];
  date_range: DateRange;
  total_documents: number;
}

export type EntityType = 'Person' | 'Organization' | 'Location' | 'Event';

export interface Entity {
  id: string;
  name: string;
  type: EntityType;
  aliases: string[];
  properties: Record<string, unknown>;
  mention_count: number;
  first_mentioned?: string;
  last_mentioned?: string;
}

export interface Relationship {
  id: string;
  source_id: string;
  target_id: string;
  type: string;
  properties: Record<string, unknown>;
  weight: number;
  document_ids: string[];
}

export interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface EntityDetailResponse {
  entity: Entity;
  related_documents: Record<string, unknown>[];
  relationships: Relationship[];
}

// ============================================================================
// Taxonomy Types
// ============================================================================

export type FieldType = 'string' | 'number' | 'date' | 'boolean' | 'object' | 'array';

export interface SchemaField {
  name: string;
  type: FieldType;
  description?: string;
  required?: boolean;
  extraction_prompt?: string;
  properties?: Record<string, SchemaField>;
  items?: SchemaField;
}

export interface DocumentType {
  id: string;
  name: string;
  description?: string;
  schema_fields: SchemaField[];
  system_prompt?: string;
  post_processing?: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentTypeCreate {
  name: string;
  description?: string;
  schema_fields?: SchemaField[];
  system_prompt?: string;
  post_processing?: string;
}

export interface DocumentTypeUpdate {
  name?: string;
  description?: string;
  schema_fields?: SchemaField[];
  system_prompt?: string;
  post_processing?: string;
}

export interface Classification {
  document_id: string;
  document_type_id: string;
  document_type_name?: string;
  confidence?: number;
  labeled_by?: string;
  created_at: string;
}

export interface ClassificationCreate {
  document_type_id: string;
  confidence?: number;
  labeled_by?: string;
}

export interface AutoClassificationResult {
  document_type_id: string;
  document_type_name: string;
  confidence: number;
  reasoning: string;
  key_indicators?: string[];
  saved: boolean;
}

export interface ExtractedField {
  field_name: string;
  value: any;
  confidence: number;
  source_text?: string;
}

export interface ExtractionResult {
  document_id: string;
  document_type_id: string;
  fields: ExtractedField[];
  extracted_at: string;
}

// ============================================================================
// Annotation Types
// ============================================================================

export type AnnotationType = 'text_span' | 'bounding_box' | 'key_value' | 'entity' | 'classification';

export interface Label {
  id: string;
  name: string;
  color: string;
  description?: string;
  shortcut?: string;
  entity_type?: string;
  document_type_id?: string;
}

export interface LabelCreate {
  name: string;
  color?: string;
  description?: string;
  shortcut?: string;
  entity_type?: string;
  document_type_id?: string;
}

export interface Annotation {
  id: string;
  document_id: string;
  label_id: string;
  label_name?: string;
  label_color?: string;
  annotation_type: AnnotationType;
  // Text span fields
  start_offset?: number;
  end_offset?: number;
  text?: string;
  // Bounding box fields
  page?: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  // Key-value fields
  key_text?: string;
  key_start?: number;
  key_end?: number;
  value_text?: string;
  value_start?: number;
  value_end?: number;
  // Entity fields
  entity_type?: string;
  normalized_value?: string;
  // Table/Array grouping
  row_index?: number;
  group_id?: string;
  // Structured metadata
  metadata?: Record<string, any>;
  // Metadata
  created_by?: string;
  created_at: string;
}

export interface AnnotationCreate {
  label_id: string;
  annotation_type: AnnotationType;
  start_offset?: number;
  end_offset?: number;
  text?: string;
  page?: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  key_text?: string;
  key_start?: number;
  key_end?: number;
  value_text?: string;
  value_start?: number;
  value_end?: number;
  entity_type?: string;
  normalized_value?: string;
  row_index?: number;
  group_id?: string;
  metadata?: Record<string, any>;
  created_by?: string;
}

export interface AnnotationStats {
  document_id: string;
  total_annotations: number;
  by_type: Record<string, number>;
  by_label: Record<string, number>;
}

// ============================================================================
// Suggestion Types
// ============================================================================

export interface SuggestedAnnotation {
  label_id: string;
  label_name: string;
  text: string;
  start_offset: number;
  end_offset: number;
  confidence: number;
  reasoning?: string;
  metadata?: Record<string, any>;
}

export interface SuggestionRequest {
  label_ids?: string[];
  max_suggestions?: number;
  min_confidence?: number;
}

export interface SuggestionResponse {
  document_id: string;
  suggestions: SuggestedAnnotation[];
  examples_used: number;
  model: string;
  generated_at: string;
}

// ============================================================================
// Feedback / ML Types
// ============================================================================

export type FeedbackType = 'correct' | 'incorrect' | 'accepted' | 'rejected';
export type FeedbackSource = 'suggestion' | 'manual';

export interface Feedback {
  id: string;
  document_id: string;
  label_id: string;
  label_name?: string;
  text: string;
  start_offset: number;
  end_offset: number;
  feedback_type: FeedbackType;
  source: FeedbackSource;
  embedding?: number[];
  created_at: string;
}

export interface FeedbackCreate {
  document_id: string;
  label_id: string;
  text: string;
  start_offset: number;
  end_offset: number;
  feedback_type: FeedbackType;
  source?: FeedbackSource;
}

export interface FeedbackResponse {
  feedback: Feedback;
  should_retrain: boolean;
  feedback_count: number;
}

export interface TrainingStatus {
  is_trained: boolean;
  sample_count: number;
  positive_samples: number;
  negative_samples: number;
  labels_count: number;
  last_trained_at?: string;
  accuracy?: number;
  model_path?: string;
  min_samples_required: number;
  ready_to_train: boolean;
}

export interface TrainingResult {
  success: boolean;
  message: string;
  accuracy?: number;
  sample_count: number;
  trained_at?: string;
}

// ============================================================================
// Label Suggestion Types
// ============================================================================

export interface LabelSuggestion {
  id: string;
  name: string;
  description: string;
  reasoning: string;
  confidence: number;
  source_examples: string[];
  suggested_color: string;
  created_at: string;
}

export interface LabelSuggestionRequest {
  sample_size?: number;
  existing_labels?: boolean;
  document_ids?: string[];
}

export interface LabelSuggestionResponse {
  suggestions: LabelSuggestion[];
  documents_analyzed: number;
  model: string;
}

export interface AcceptSuggestionRequest {
  color?: string;
  name?: string;
  description?: string;
}

// ============================================================================
// Search & Q&A Types
// ============================================================================

export interface SearchResult {
  document_id: string;
  filename: string;
  chunk_index: number;
  content: string;
  similarity: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

export interface QuestionSource {
  document_id: string;
  filename: string;
  chunk_index: number;
  similarity: number;
  excerpt: string;
}

export interface QuestionResponse {
  question: string;
  answer: string;
  confidence: number;
  sources: QuestionSource[];
  referenced_sources: number[];
}

// ============================================================================
// Tutorial Types
// ============================================================================

export interface TutorialSetupResponse {
  success: boolean;
  document_ids: string[];
  document_type_ids: string[];
  label_ids: string[];
  message: string;
}

export interface TutorialStatusResponse {
  is_setup: boolean;
  document_count: number;
  document_type_count: number;
  label_count: number;
  sample_document_ids: string[];
}

export interface SampleDocument {
  id: string;
  filename: string;
  file_type: string;
  expected_type: string;
  is_sample: boolean;
}

// ============================================================================
// API Client
// ============================================================================

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API Error ${response.status}: ${errorText}`);
    }

    return response.json();
  }

  // Health
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  // Documents
  async listDocuments(): Promise<{ documents: DocumentSummary[]; total: number }> {
    return this.request(`${API_PREFIX}/documents`);
  }

  async getDocument(id: string): Promise<{ document: Document }> {
    return this.request(`${API_PREFIX}/documents/${id}`);
  }

  getDocumentFileUrl(id: string, download: boolean = false): string {
    const url = `${this.baseUrl}${API_PREFIX}/documents/${id}/file`;
    return download ? `${url}?download=true` : url;
  }

  async deleteDocument(id: string): Promise<{ status: string; document_id: string }> {
    return this.request(`${API_PREFIX}/documents/${id}`, { method: 'DELETE' });
  }

  // Ingestion
  async ingestDocuments(files: File[]): Promise<IngestResponse> {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    const response = await fetch(`${this.baseUrl}${API_PREFIX}/ingest`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Ingestion Error ${response.status}: ${errorText}`);
    }

    return response.json();
  }

  async getIngestStatus(): Promise<{
    documents: number;
    chunks: number;
    graph: GraphStats;
  }> {
    return this.request(`${API_PREFIX}/ingest/status`);
  }

  // Timeline
  async getTimeline(
    startDate?: string,
    endDate?: string
  ): Promise<TimelineResponse> {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request(`${API_PREFIX}/timeline${query}`);
  }

  // Graph
  async getGraph(
    entityTypes?: EntityType[],
    maxNodes: number = 100
  ): Promise<GraphData> {
    const params = new URLSearchParams();
    if (entityTypes) {
      entityTypes.forEach((t) => params.append('entity_types', t));
    }
    params.append('max_nodes', maxNodes.toString());
    
    return this.request(`${API_PREFIX}/graph?${params.toString()}`);
  }

  async listEntities(
    entityType?: EntityType,
    limit: number = 100
  ): Promise<{ entities: Entity[]; total: number }> {
    const params = new URLSearchParams();
    if (entityType) params.append('entity_type', entityType);
    params.append('limit', limit.toString());
    
    return this.request(`${API_PREFIX}/graph/entities?${params.toString()}`);
  }

  async getEntity(id: string): Promise<EntityDetailResponse> {
    return this.request(`${API_PREFIX}/graph/entities/${id}`);
  }

  async getGraphTimeline(
    startDate?: string,
    endDate?: string
  ): Promise<TimelineResponse> {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request(`${API_PREFIX}/graph/timeline${query}`);
  }

  async getGraphStats(): Promise<GraphStats> {
    return this.request(`${API_PREFIX}/graph/stats`);
  }

  // Taxonomy - Document Types
  async listDocumentTypes(): Promise<{ types: DocumentType[]; total: number }> {
    return this.request(`${API_PREFIX}/taxonomy/types`);
  }

  async getDocumentType(id: string): Promise<{ type: DocumentType }> {
    return this.request(`${API_PREFIX}/taxonomy/types/${id}`);
  }

  async createDocumentType(data: DocumentTypeCreate): Promise<{ type: DocumentType }> {
    return this.request(`${API_PREFIX}/taxonomy/types`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateDocumentType(id: string, data: DocumentTypeUpdate): Promise<{ type: DocumentType }> {
    return this.request(`${API_PREFIX}/taxonomy/types/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteDocumentType(id: string): Promise<{ status: string; documents_unclassified: number }> {
    return this.request(`${API_PREFIX}/taxonomy/types/${id}`, {
      method: 'DELETE',
    });
  }

  async getDocumentsByType(typeId: string): Promise<{ document_type: string; document_ids: string[]; total: number }> {
    return this.request(`${API_PREFIX}/taxonomy/types/${typeId}/documents`);
  }

  // Taxonomy - Document Classification
  async classifyDocument(documentId: string, typeId: string, confidence: number = 1.0): Promise<{ classification: Classification }> {
    return this.request(`${API_PREFIX}/documents/${documentId}/classify`, {
      method: 'POST',
      body: JSON.stringify({
        document_type_id: typeId,
        confidence: confidence,
        labeled_by: 'user',
      }),
    });
  }

  async getDocumentClassification(documentId: string): Promise<{ classification: Classification }> {
    return this.request(`${API_PREFIX}/documents/${documentId}/classification`);
  }

  async deleteDocumentClassification(documentId: string): Promise<{ status: string }> {
    return this.request(`${API_PREFIX}/documents/${documentId}/classification`, {
      method: 'DELETE',
    });
  }

  async autoClassifyDocument(documentId: string, save: boolean = false): Promise<AutoClassificationResult> {
    return this.request(`${API_PREFIX}/documents/${documentId}/auto-classify?save=${save}`, {
      method: 'POST',
    });
  }

  // Extraction
  async extractDocument(documentId: string, useLlm: boolean = true): Promise<ExtractionResult> {
    return this.request(`${API_PREFIX}/documents/${documentId}/extract?use_llm=${useLlm}`, {
      method: 'POST',
    });
  }

  async getDocumentExtraction(documentId: string): Promise<ExtractionResult> {
    return this.request(`${API_PREFIX}/documents/${documentId}/extraction`);
  }

  async deleteDocumentExtraction(documentId: string): Promise<{ status: string }> {
    return this.request(`${API_PREFIX}/documents/${documentId}/extraction`, {
      method: 'DELETE',
    });
  }

  // Labels
  async listLabels(documentTypeId?: string, includeGlobal: boolean = true): Promise<{ labels: Label[]; total: number }> {
    const params = new URLSearchParams();
    if (documentTypeId) params.append('document_type_id', documentTypeId);
    params.append('include_global', String(includeGlobal));
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request(`${API_PREFIX}/labels${query}`);
  }

  async createLabel(data: LabelCreate): Promise<Label> {
    return this.request(`${API_PREFIX}/labels`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getLabel(id: string): Promise<Label> {
    return this.request(`${API_PREFIX}/labels/${id}`);
  }

  async updateLabel(id: string, data: Partial<LabelCreate>): Promise<Label> {
    return this.request(`${API_PREFIX}/labels/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteLabel(id: string): Promise<{ status: string }> {
    return this.request(`${API_PREFIX}/labels/${id}`, {
      method: 'DELETE',
    });
  }

  // Label Suggestions
  async suggestLabels(request?: LabelSuggestionRequest): Promise<LabelSuggestionResponse> {
    return this.request(`${API_PREFIX}/labels/suggest`, {
      method: 'POST',
      body: JSON.stringify(request || {}),
    });
  }

  async acceptLabelSuggestion(
    suggestion: LabelSuggestion,
    overrides?: AcceptSuggestionRequest
  ): Promise<Label> {
    return this.request(`${API_PREFIX}/labels/suggestions/${suggestion.id}/accept`, {
      method: 'POST',
      body: JSON.stringify({
        ...suggestion,
        ...(overrides || {}),
      }),
    });
  }

  async rejectLabelSuggestion(suggestionId: string): Promise<{ status: string }> {
    return this.request(`${API_PREFIX}/labels/suggestions/${suggestionId}/reject`, {
      method: 'POST',
    });
  }

  // Annotations
  async listAnnotations(
    documentId: string,
    annotationType?: AnnotationType,
    labelId?: string
  ): Promise<{ annotations: Annotation[]; total: number }> {
    const params = new URLSearchParams();
    if (annotationType) params.append('annotation_type', annotationType);
    if (labelId) params.append('label_id', labelId);
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request(`${API_PREFIX}/documents/${documentId}/annotations${query}`);
  }

  async createAnnotation(documentId: string, data: AnnotationCreate): Promise<{ annotation: Annotation }> {
    return this.request(`${API_PREFIX}/documents/${documentId}/annotations`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getAnnotation(id: string): Promise<{ annotation: Annotation }> {
    return this.request(`${API_PREFIX}/annotations/${id}`);
  }

  async deleteAnnotation(id: string): Promise<{ status: string }> {
    return this.request(`${API_PREFIX}/annotations/${id}`, {
      method: 'DELETE',
    });
  }

  async deleteDocumentAnnotations(documentId: string): Promise<{ status: string; count: number }> {
    return this.request(`${API_PREFIX}/documents/${documentId}/annotations`, {
      method: 'DELETE',
    });
  }

  async getAnnotationStats(documentId: string): Promise<AnnotationStats> {
    return this.request(`${API_PREFIX}/documents/${documentId}/annotations/stats`);
  }

  // Export
  getExportAnnotationsUrl(format: 'json' | 'csv' = 'json', labelId?: string): string {
    const params = new URLSearchParams({ format });
    if (labelId) params.append('label_id', labelId);
    return `${this.baseUrl}${API_PREFIX}/annotations/export?${params.toString()}`;
  }

  getExportDocumentUrl(documentId: string, format: 'json' | 'csv' = 'json', includeContent: boolean = false): string {
    const params = new URLSearchParams({ format, include_content: String(includeContent) });
    return `${this.baseUrl}${API_PREFIX}/documents/${documentId}/export?${params.toString()}`;
  }

  // Suggestions
  async suggestAnnotations(
    documentId: string,
    request?: SuggestionRequest,
    forceLlm: boolean = false
  ): Promise<SuggestionResponse> {
    const query = forceLlm ? '?force_llm=true' : '';
    return this.request(`${API_PREFIX}/documents/${documentId}/suggest${query}`, {
      method: 'POST',
      body: JSON.stringify(request || {}),
    });
  }

  // Feedback
  async submitFeedback(data: FeedbackCreate): Promise<FeedbackResponse> {
    return this.request(`${API_PREFIX}/feedback`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async listFeedback(labelId?: string, limit: number = 100): Promise<Feedback[]> {
    const params = new URLSearchParams();
    if (labelId) params.append('label_id', labelId);
    params.append('limit', limit.toString());
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request(`${API_PREFIX}/feedback${query}`);
  }

  // Model Status
  async getModelStatus(): Promise<TrainingStatus> {
    return this.request(`${API_PREFIX}/model/status`);
  }

  async trainModel(): Promise<TrainingResult> {
    return this.request(`${API_PREFIX}/model/train`, {
      method: 'POST',
    });
  }

  // Search & Q&A
  async semanticSearch(query: string, nResults: number = 5, documentIds?: string[]): Promise<SearchResponse> {
    const params = new URLSearchParams({ q: query, n_results: String(nResults) });
    if (documentIds && documentIds.length > 0) {
      params.append('document_ids', documentIds.join(','));
    }
    return this.request(`${API_PREFIX}/search?${params.toString()}`);
  }

  async askQuestion(question: string, documentIds?: string[], nContext: number = 5): Promise<QuestionResponse> {
    return this.request(`${API_PREFIX}/ask`, {
      method: 'POST',
      body: JSON.stringify({
        question,
        document_ids: documentIds,
        n_context: nContext,
      }),
    });
  }

  // Tutorial
  async setupTutorial(): Promise<TutorialSetupResponse> {
    return this.request(`${API_PREFIX}/tutorial/setup`, {
      method: 'POST',
    });
  }

  async getTutorialStatus(): Promise<TutorialStatusResponse> {
    return this.request(`${API_PREFIX}/tutorial/status`);
  }

  async resetTutorial(): Promise<{ success: boolean; deleted_documents: number; message: string }> {
    return this.request(`${API_PREFIX}/tutorial/reset`, {
      method: 'POST',
    });
  }

  async getSampleDocuments(): Promise<{ documents: SampleDocument[]; total: number; expected_total: number }> {
    return this.request(`${API_PREFIX}/tutorial/sample-documents`);
  }

  // Evaluation
  async deleteEvaluation(evaluationId: string): Promise<{ message: string }> {
    return this.request(`${API_PREFIX}/evaluation/${evaluationId}`, {
      method: 'DELETE',
    });
  }
}

// Export singleton instance
export const api = new ApiClient();

// Export class for custom instances
export { ApiClient };
