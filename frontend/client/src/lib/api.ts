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
  token_count?: number;
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

export interface DeploymentVersion {
  id: string;
  project_id: string;
  version: string;
  document_type_id: string;
  document_type_name: string;
  schema_version_id?: string | null;
  prompt_version_id?: string | null;
  system_prompt?: string | null;
  user_prompt_template?: string | null;
  schema_fields: Record<string, unknown>[];
  field_prompt_versions: Record<string, string>;
  model?: string | null;
  is_active: boolean;
  created_by?: string | null;
  created_at: string;
}

export interface DeploymentVersionCreate {
  project_id: string;
  document_type_id: string;
  prompt_version_id?: string | null;
  created_by?: string;
  set_active?: boolean;
}

export interface DeploymentExtractResponse {
  project_id: string;
  deployment_version_id: string;
  deployment_version: string;
  document_type_id: string;
  document_type_name: string;
  filename: string;
  extracted_data: Record<string, unknown>;
}

export interface DashboardEvaluationSummary {
  f1_score?: number;
}

export interface DashboardEvaluation {
  id: string;
  evaluated_at: string;
  metrics?: DashboardEvaluationSummary;
}

export interface OpenAIProviderStatus {
  provider: "openai";
  masked_api_key: string;
  source: "override" | "env" | "none";
  has_key: boolean;
  last_test_status: "unknown" | "connected" | "failed";
  last_tested_at?: string | null;
  connected: boolean;
  model: string;
}

export interface OpenAIProviderUpdateRequest {
  api_key?: string;
}

export interface OpenAIProviderTestRequest {
  api_key?: string;
}

export interface OpenAIProviderTestResponse {
  provider: "openai";
  connected: boolean;
  message: string;
  masked_api_key: string;
  tested_at: string;
}

export interface OpenAIProviderModel {
  provider: "openai";
  model_id: string;
  display_name?: string | null;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface OpenAIProviderModelTestResponse {
  provider: "openai";
  model_id: string;
  connected: boolean;
  message: string;
  tested_at: string;
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
  extraction_model?: string;
  ocr_engine?: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentTypeCreate {
  name: string;
  description?: string;
  schema_fields?: SchemaField[];
  system_prompt?: string;
  post_processing?: string;
  extraction_model?: string;
  ocr_engine?: string;
}

export interface DocumentTypeUpdate {
  name?: string;
  description?: string;
  schema_fields?: SchemaField[];
  system_prompt?: string;
  post_processing?: string;
  extraction_model?: string;
  ocr_engine?: string;
}

export interface GlobalField {
  id: string;
  name: string;
  type: FieldType;
  prompt: string;
  description?: string;
  extraction_model?: string;
  ocr_engine?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface GlobalFieldCreate {
  name: string;
  type: FieldType;
  prompt: string;
  description?: string;
  extraction_model?: string;
  ocr_engine?: string;
  created_by?: string;
}

export interface FieldAssistantProperty {
  name: string;
  type: FieldType;
  description?: string;
}

export interface FieldAssistantRequest {
  user_input: string;
  document_type_id?: string;
  existing_field_names?: string[];
}

export interface FieldAssistantResponse {
  name: string;
  type: FieldType;
  description?: string;
  extraction_prompt: string;
  items_type?: FieldType | null;
  object_properties: FieldAssistantProperty[];
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

export interface FieldPromptVersion {
  id: string;
  name: string;
  document_type_id: string;
  field_name: string;
  extraction_prompt: string;
  description?: string;
  is_active: boolean;
  created_by?: string;
  created_at: string;
}

export interface FieldPromptVersionCreate {
  name: string;
  document_type_id: string;
  field_name: string;
  extraction_prompt: string;
  description?: string;
  is_active?: boolean;
  created_by?: string;
}

export interface FieldPromptVersionUpdate {
  name?: string;
  extraction_prompt?: string;
  description?: string;
  is_active?: boolean;
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

export interface SchemaSuggestionResponse {
  document_id: string;
  document_type_id: string;
  suggestions: Array<{
    field_name: string;
    label_name: string;
    spans: Array<{
      text: string;
      start_char: number;
      end_char: number;
    }>;
    confidence: number;
    reasoning?: string;
    metadata?: Record<string, unknown>;
  }>;
  extraction_preview: Record<string, unknown>;
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

  async listGlobalFields(search?: string): Promise<{ fields: GlobalField[]; total: number }> {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request(`${API_PREFIX}/taxonomy/fields${query}`);
  }

  async createGlobalField(data: GlobalFieldCreate): Promise<GlobalField> {
    return this.request(`${API_PREFIX}/taxonomy/fields`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateGlobalField(id: string, data: Partial<GlobalFieldCreate>): Promise<GlobalField> {
    return this.request(`${API_PREFIX}/taxonomy/fields/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async suggestFieldDefinition(data: FieldAssistantRequest): Promise<FieldAssistantResponse> {
    return this.request(`${API_PREFIX}/taxonomy/field-assistant`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteGlobalField(id: string): Promise<{ status: string; message: string }> {
    return this.request(`${API_PREFIX}/taxonomy/fields/${id}`, {
      method: 'DELETE',
    });
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
  async extractDocument(
    documentId: string,
    useLlm: boolean = true,
    useStructuredOutput: boolean = false
  ): Promise<ExtractionResult> {
    return this.request(
      `${API_PREFIX}/documents/${documentId}/extract?use_llm=${useLlm}&use_structured_output=${useStructuredOutput}`,
      {
      method: 'POST',
      }
    );
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

  async suggestSchemaAnnotations(
    documentId: string,
    autoAccept: boolean = true
  ): Promise<SchemaSuggestionResponse> {
    const query = `?auto_accept=${String(autoAccept)}`;
    return this.request(`${API_PREFIX}/documents/${documentId}/suggest-annotations${query}`, {
      method: 'POST',
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
  async listEvaluations(params?: {
    document_id?: string;
    document_type_id?: string;
    prompt_version_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ evaluations: DashboardEvaluation[]; total: number }> {
    const query = new URLSearchParams();
    if (params?.document_id) query.append("document_id", params.document_id);
    if (params?.document_type_id) query.append("document_type_id", params.document_type_id);
    if (params?.prompt_version_id) query.append("prompt_version_id", params.prompt_version_id);
    if (typeof params?.limit === "number") query.append("limit", String(params.limit));
    if (typeof params?.offset === "number") query.append("offset", String(params.offset));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return this.request(`${API_PREFIX}/evaluation${suffix}`);
  }

  async getOpenAIProviderStatus(): Promise<OpenAIProviderStatus> {
    return this.request(`${API_PREFIX}/providers/openai`);
  }

  async updateOpenAIProvider(data: OpenAIProviderUpdateRequest): Promise<OpenAIProviderStatus> {
    return this.request(`${API_PREFIX}/providers/openai`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async testOpenAIProvider(data?: OpenAIProviderTestRequest): Promise<OpenAIProviderTestResponse> {
    return this.request(`${API_PREFIX}/providers/openai/test`, {
      method: "POST",
      body: JSON.stringify(data || {}),
    });
  }

  async listOpenAIProviderModels(enabledOnly: boolean = false): Promise<{ models: OpenAIProviderModel[]; total: number }> {
    const query = enabledOnly ? "?enabled_only=true" : "";
    return this.request(`${API_PREFIX}/providers/openai/models${query}`);
  }

  async createOpenAIProviderModel(data: { model_id: string; display_name?: string; is_enabled?: boolean }): Promise<OpenAIProviderModel> {
    return this.request(`${API_PREFIX}/providers/openai/models`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateOpenAIProviderModel(
    modelId: string,
    data: { display_name?: string; is_enabled?: boolean }
  ): Promise<OpenAIProviderModel> {
    return this.request(`${API_PREFIX}/providers/openai/models/${encodeURIComponent(modelId)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async deleteOpenAIProviderModel(modelId: string): Promise<{ status: string }> {
    return this.request(`${API_PREFIX}/providers/openai/models/${encodeURIComponent(modelId)}`, {
      method: "DELETE",
    });
  }

  async testOpenAIProviderModel(modelId: string): Promise<OpenAIProviderModelTestResponse> {
    return this.request(`${API_PREFIX}/providers/openai/models/${encodeURIComponent(modelId)}/test`, {
      method: "POST",
    });
  }

  async deleteEvaluation(evaluationId: string): Promise<{ message: string }> {
    return this.request(`${API_PREFIX}/evaluation/results/${evaluationId}`, {
      method: 'DELETE',
    });
  }

  async listFieldPromptVersions(
    documentTypeId: string,
    fieldName?: string,
    isActive?: boolean
  ): Promise<{ field_prompt_versions: FieldPromptVersion[]; total: number }> {
    const params = new URLSearchParams();
    params.append('document_type_id', documentTypeId);
    if (fieldName) params.append('field_name', fieldName);
    if (typeof isActive === 'boolean') params.append('is_active', String(isActive));
    return this.request(`${API_PREFIX}/evaluation/field-prompts/list?${params.toString()}`);
  }

  async createFieldPromptVersion(
    data: FieldPromptVersionCreate
  ): Promise<{ id: string; message: string }> {
    return this.request(`${API_PREFIX}/evaluation/field-prompts`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateFieldPromptVersion(
    versionId: string,
    data: FieldPromptVersionUpdate
  ): Promise<{ message: string }> {
    return this.request(`${API_PREFIX}/evaluation/field-prompts/version/${versionId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteFieldPromptVersion(versionId: string): Promise<{ message: string }> {
    return this.request(`${API_PREFIX}/evaluation/field-prompts/version/${versionId}`, {
      method: 'DELETE',
    });
  }

  async listActiveFieldPromptsByDocumentType(
    documentTypeId: string
  ): Promise<{
    field_prompts: Record<string, string>;
    field_versions: Record<string, string>;
    field_version_updated_at: Record<string, string>;
    total: number;
  }> {
    return this.request(
      `${API_PREFIX}/evaluation/field-prompts/active/by-document-type?document_type_id=${encodeURIComponent(documentTypeId)}`
    );
  }

  // Deployments
  async createDeploymentVersion(data: DeploymentVersionCreate): Promise<{ version: DeploymentVersion }> {
    return this.request(`${API_PREFIX}/deployments/versions`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async listDeploymentVersions(projectId: string): Promise<{ versions: DeploymentVersion[]; total: number }> {
    return this.request(`${API_PREFIX}/deployments/projects/${encodeURIComponent(projectId)}/versions`);
  }

  async getActiveDeploymentVersion(projectId: string): Promise<{ version: DeploymentVersion }> {
    return this.request(`${API_PREFIX}/deployments/projects/${encodeURIComponent(projectId)}/active`);
  }

  async activateDeploymentVersion(projectId: string, versionId: string): Promise<{ status: string; active_version: DeploymentVersion }> {
    return this.request(`${API_PREFIX}/deployments/projects/${encodeURIComponent(projectId)}/versions/${encodeURIComponent(versionId)}/activate`, {
      method: 'POST',
    });
  }

  async extractWithDeploymentVersion(projectId: string, versionId: string, file: File): Promise<DeploymentExtractResponse> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(
      `${this.baseUrl}${API_PREFIX}/deployments/projects/${encodeURIComponent(projectId)}/versions/${encodeURIComponent(versionId)}/extract`,
      {
        method: 'POST',
        body: formData,
      }
    );
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API Error ${response.status}: ${errorText}`);
    }
    return response.json();
  }

  async extractWithActiveDeployment(projectId: string, file: File): Promise<DeploymentExtractResponse> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(
      `${this.baseUrl}${API_PREFIX}/deployments/projects/${encodeURIComponent(projectId)}/extract`,
      {
        method: 'POST',
        body: formData,
      }
    );
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API Error ${response.status}: ${errorText}`);
    }
    return response.json();
  }
}

// Export singleton instance
export const api = new ApiClient();

// Export class for custom instances
export { ApiClient };
