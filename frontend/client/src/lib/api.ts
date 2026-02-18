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
    openai: string;
  };
  stats: {
    documents: number;
  };
}


export interface GraphIndexDocumentsResult {
  requested_documents: number;
  valid_documents: number;
  missing_documents: number;
  already_indexed_documents: number;
  enqueued_documents: number;
  enqueued_task_ids: string[];
  missing_document_ids: string[];
  already_indexed_document_ids: string[];
}

export interface GraphDeleteDbResult {
  deleted: boolean;
  stats_before: GraphStats;
  stats_after: GraphStats;
  total_documents: number;
  indexed_documents: number;
  pending_documents: number;
}

export interface GraphRemoveResult {
  requested_id: string;
  resolved_document_id: string;
  resolved_document_ids: string[];
  removed: boolean;
  removed_documents: number;
  removed_document_ids: string[];
  total_documents: number;
  indexed_documents: number;
  pending_documents: number;
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
  document_type?: DocumentType;
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
  order?: number;
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
  schema_version_id?: string;
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
  items_type?: FieldType | null;
  properties?: FieldAssistantProperty[];
}

export interface FieldAssistantRequest {
  user_input: string;
  document_type_id?: string;
  existing_field_names?: string[];
  screenshot_base64?: string;
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

// ============================================================================
// Annotation Types
// ============================================================================

export type AnnotationType = 'text_span' | 'bbox' | 'table_row';

export interface TextSpanData {
  start: number;
  end: number;
  text: string;
}

export interface BoundingBoxData {
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
  text?: string;
}

export interface TableRowFieldData {
  name: string;
  bbox?: BoundingBoxData;
  text_span?: TextSpanData;
}

export interface TableRowData {
  row_index: number;
  fields: TableRowFieldData[];
}

export interface GroundTruthAnnotation {
  id: string;
  document_id: string;
  field_name: string;
  value: any;
  annotation_type: AnnotationType;
  annotation_data: TextSpanData | BoundingBoxData | TableRowData;
  confidence: number;
  labeled_by: string;
  is_approved: boolean;
  created_at: string;
  updated_at: string;
}

export interface GroundTruthAnnotationCreate {
  document_id: string;
  field_name: string;
  value: any;
  annotation_type: AnnotationType;
  annotation_data: any;
  confidence?: number;
  labeled_by?: string;
}

export interface AnnotationSuggestion {
  id: string;
  document_id: string;
  field_name: string;
  value: any;
  annotation_type: AnnotationType;
  annotation_data: any;
  confidence: number;
  text_snippet?: string;
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

// Evaluation interfaces
export type MatchType = 'exact' | 'normalized' | 'fuzzy' | 'semantic' | 'no_match';

export interface MatchResult {
  is_match: boolean;
  match_type: MatchType;
  confidence: number;
  reason?: string;
}

export interface FieldComparison {
  field_name: string;
  ground_truth_value: any;
  predicted_value: any;
  match_result: MatchResult;
  instance_num?: number;
}

export interface InstanceComparison {
  parent_field: string;
  instance_num: number;
  gt_instance_num?: number;
  pred_instance_num?: number;
  field_comparisons: FieldComparison[];
  is_matched: boolean;
  match_score: number;
}

export interface FlattenedMetrics {
  total_fields: number;
  correct_fields: number;
  incorrect_fields: number;
  missing_fields: number;
  extra_fields: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  match_type_distribution: Record<string, number>;
}

export interface InstanceMetrics {
  total_instances: number;
  matched_instances: number;
  missing_instances: number;
  extra_instances: number;
  instance_match_rate: number;
  avg_field_accuracy_in_matched: number;
  instance_precision: number;
  instance_recall: number;
  instance_f1_score: number;
}

export interface FieldMetrics {
  field_name: string;
  total_occurrences: number;
  correct_predictions: number;
  incorrect_predictions: number;
  missing_predictions: number;
  accuracy: number;
  precision: number;
  recall: number;
  avg_confidence: number;
  match_type_distribution: Record<string, number>;
}

export interface EvaluationMetrics {
  flattened: FlattenedMetrics;
  instance_metrics: Record<string, InstanceMetrics>;
  field_metrics: Record<string, FieldMetrics>;
}

export interface EvaluationResult {
  document_id: string;
  metrics: EvaluationMetrics;
  field_comparisons: FieldComparison[];
  instance_comparisons: Record<string, InstanceComparison[]>;
  extraction_time_ms?: number;
  evaluation_time_ms?: number;
}

export interface EvaluationRun {
  id: string;
  document_id: string;
  project_id?: string;
  result: EvaluationResult;
  notes?: string;
  evaluated_at: string;
}

export interface EvaluationSummary {
  project_id?: string;
  total_evaluations: number;
  total_documents: number;
  avg_accuracy: number;
  avg_precision: number;
  avg_recall: number;
  avg_f1_score: number;
  field_performance: Record<string, FieldMetrics>;
  match_type_distribution: Record<string, number>;
}

// ============================================================================
// API Client
// ============================================================================

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  // Public getter for base URL (needed for constructing file URLs)
  get baseURL(): string {
    return this.baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    console.log('[API] request() called:', { url, method: options.method || 'GET' });
    
    // Add timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      console.log('[API] Request timeout after 60s');
      controller.abort();
    }, 60000);
    
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      console.log('[API] Response received:', { status: response.status, ok: response.ok });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API Error ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      console.log('[API] Response data:', data);
      return data;
    } catch (error) {
      clearTimeout(timeoutId);
      console.error('[API] Request failed:', error);
      throw error;
    }
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

  getDocumentFileUrl(id: string, options: { download?: boolean; ocr?: boolean } = {}): string {
    const url = `${this.baseUrl}${API_PREFIX}/documents/${id}/file`;
    const params = new URLSearchParams();
    if (options.download) params.append('download', 'true');
    if (options.ocr) params.append('ocr', 'true');
    const queryString = params.toString();
    return queryString ? `${url}?${queryString}` : url;
  }

  async deleteDocument(id: string): Promise<{ status: string; document_id: string }> {
    return this.request(`${API_PREFIX}/documents/${id}`, { method: 'DELETE' });
  }

  async reindexDocumentAzureDI(id: string): Promise<{ status: string; document_id: string; message: string }> {
    return this.request(`${API_PREFIX}/documents/${id}/reindex-azure-di`, { method: 'POST' });
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
    classified_documents?: number;
  }> {
    return this.request(`${API_PREFIX}/ingest/status`);
  }

  // Graph integration removed - Neo4j disabled
  // async getGraph(
  //   entityTypes?: EntityType[],
  //   maxNodes: number = 100
  // ): Promise<GraphData> {
  //   const params = new URLSearchParams();
  //   if (entityTypes) {
  //     entityTypes.forEach((t) => params.append('entity_types', t));
  //   }
  //   params.append('max_nodes', maxNodes.toString());
  //   
  //   return this.request(`${API_PREFIX}/graph?${params.toString()}`);
  // }

  // async listEntities(
  //   entityType?: EntityType,
  //   limit: number = 100
  // ): Promise<{ entities: Entity[]; total: number }> {
  //   const params = new URLSearchParams();
  //   if (entityType) params.append('entity_type', entityType);
  //   params.append('limit', limit.toString());
  //   
  //   return this.request(`${API_PREFIX}/graph/entities?${params.toString()}`);
  // }

  // async getEntity(id: string): Promise<EntityDetailResponse> {
  //   return this.request(`${API_PREFIX}/graph/entities/${id}`);
  // }

  // async getGraphTimeline(
  //   startDate?: string,
  //   endDate?: string
  // ): Promise<TimelineResponse> {
  //   const params = new URLSearchParams();
  //   if (startDate) params.append('start_date', startDate);
  //   if (endDate) params.append('end_date', endDate);
  //   
  //   const query = params.toString() ? `?${params.toString()}` : '';
  //   return this.request(`${API_PREFIX}/graph/timeline${query}`);
  // }

  // async getGraphStats(): Promise<GraphStats> {
  //   return this.request(`${API_PREFIX}/graph/stats`);
  // }

  // async getGraphIndexingStatus(): Promise<GraphIndexingStatus> {
  //   return this.request(`${API_PREFIX}/graph/indexing/status`);
  // }

  // async indexMissingGraphDocuments(): Promise<GraphIndexingEnqueueResult> {
  //   return this.request(`${API_PREFIX}/graph/indexing/index-missing`, {
  //     method: 'POST',
  //   });
  // }

  // async indexGraphDocuments(documentIds: string[]): Promise<GraphIndexDocumentsResult> {
  //   return this.request(`${API_PREFIX}/graph/indexing/index-documents`, {
  //     method: 'POST',
  //     body: JSON.stringify({ document_ids: documentIds }),
  //   });
  // }

  // async deleteGraphDatabase(): Promise<GraphDeleteDbResult> {
  //   return this.request(`${API_PREFIX}/graph/indexing/delete-db`, {
  //     method: 'DELETE',
  //   });
  // }

  // async removeGraphDocument(documentOrChunkId: string): Promise<GraphRemoveResult> {
  //   const params = new URLSearchParams({
  //     document_or_chunk_id: documentOrChunkId,
  //   });
  //   return this.request(`${API_PREFIX}/graph/indexing/remove?${params.toString()}`, {
  //     method: 'DELETE',
  //   });
  // }

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

  // Ground Truth Annotations
  async getGroundTruthAnnotations(documentId: string): Promise<{ annotations: GroundTruthAnnotation[]; total: number }> {
    return this.request(`${API_PREFIX}/documents/${documentId}/ground-truth`);
  }

  async createGroundTruthAnnotation(documentId: string, data: GroundTruthAnnotationCreate): Promise<{ annotation: GroundTruthAnnotation }> {
    return this.request(`${API_PREFIX}/documents/${documentId}/ground-truth`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateGroundTruthAnnotation(annotationId: string, data: Partial<GroundTruthAnnotationCreate>): Promise<{ annotation: GroundTruthAnnotation }> {
    return this.request(`${API_PREFIX}/annotations/${annotationId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteGroundTruthAnnotation(documentId: string, annotationId: string): Promise<{ status: string; annotation_id: string }> {
    return this.request(`${API_PREFIX}/annotations/${annotationId}`, {
      method: 'DELETE',
    });
  }

  async suggestAnnotations(documentId: string): Promise<{ suggestions: AnnotationSuggestion[]; total: number }> {
    return this.request(`${API_PREFIX}/documents/${documentId}/suggest-annotations`, {
      method: 'POST',
    });
  }

  async approveAnnotation(annotationId: string, editedValue?: any): Promise<{ annotation: GroundTruthAnnotation }> {
    return this.request(`${API_PREFIX}/annotations/${annotationId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ annotation_id: annotationId, edited_value: editedValue }),
    });
  }

  async rejectAnnotation(annotationId: string): Promise<{ status: string; annotation_id: string }> {
    return this.request(`${API_PREFIX}/annotations/${annotationId}/reject`, {
      method: 'POST',
    });
  }

  // Evaluation endpoints
  async runEvaluation(documentId: string, projectId?: string, runExtraction: boolean = true, notes?: string): Promise<{ run: EvaluationRun }> {
    console.log('[API] runEvaluation called:', { documentId, projectId, runExtraction });
    
    // Queue the evaluation task
    const queueResult = await this.request<{ status: string; task_id: string; message: string }>(`${API_PREFIX}/evaluation/run`, {
      method: 'POST',
      body: JSON.stringify({
        document_id: documentId,
        project_id: projectId,
        run_extraction: runExtraction,
        notes,
      }),
    });
    
    console.log('[API] Evaluation queued:', queueResult);
    
    // Poll for task completion
    const taskId = queueResult.task_id;
    let attempts = 0;
    const maxAttempts = 600; // 10 minutes with 1 second intervals
    
    while (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second
      
      const taskStatus = await this.request<{ status: string; task_id: string; evaluation_id?: string; error?: string }>(`${API_PREFIX}/evaluation/task/${taskId}`);
      console.log('[API] Task status:', taskStatus);
      
      if (taskStatus.status === 'completed' && taskStatus.evaluation_id) {
        // Fetch the evaluation details
        return this.getEvaluationDetails(taskStatus.evaluation_id);
      } else if (taskStatus.status === 'failed') {
        throw new Error(taskStatus.error || 'Evaluation failed');
      }
      
      attempts++;
    }
    
    throw new Error('Evaluation timed out after 2 minutes');
  }

  async listEvaluations(projectId?: string, documentId?: string, limit: number = 50, offset: number = 0): Promise<{ runs: EvaluationRun[]; total: number }> {
    const params = new URLSearchParams();
    if (projectId) params.append('project_id', projectId);
    if (documentId) params.append('document_id', documentId);
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());
    
    return this.request(`${API_PREFIX}/evaluation/results?${params}`);
  }

  async getEvaluationDetails(evaluationId: string): Promise<{ run: EvaluationRun }> {
    return this.request(`${API_PREFIX}/evaluation/results/${evaluationId}`);
  }

  async getEvaluationSummary(projectId?: string): Promise<EvaluationSummary> {
    const params = new URLSearchParams();
    if (projectId) params.append('project_id', projectId);
    
    return this.request(`${API_PREFIX}/evaluation/summary?${params}`);
  }

  async deleteEvaluation(evaluationId: string): Promise<{ status: string; id: string }> {
    return this.request(`${API_PREFIX}/evaluation/results/${evaluationId}/delete`, {
      method: 'DELETE',
    });
  }

}

// Export singleton instance
export const api = new ApiClient();

// Export class for custom instances
export { ApiClient };
