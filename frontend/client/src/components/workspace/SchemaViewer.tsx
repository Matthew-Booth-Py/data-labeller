import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Code, Plus, Trash2, Settings2, GripVertical, Sparkles, MessageSquare, Search, Edit3, Save, X, Loader2, ThumbsDown, FileText, Edit } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import {
  api,
  DocumentType,
  SchemaField,
  FieldType,
  FieldAssistantResponse,
  LabelSuggestion,
  LabelSuggestionResponse,
  FieldPromptVersion,
} from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tag } from "lucide-react";

interface SchemaViewerProps {
  projectId?: string;
}

export function SchemaViewer({ projectId }: SchemaViewerProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const selectedTypeStorageKey = `uu-schema-selected-type:${projectId || "global"}`;
  
  // State for selected document type
  const [selectedTypeId, setSelectedTypeId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newTypeName, setNewTypeName] = useState("");
  const [newTypeDescription, setNewTypeDescription] = useState("");
  const [isEditingType, setIsEditingType] = useState(false);
  const [editTypeName, setEditTypeName] = useState("");
  const [editTypeDescription, setEditTypeDescription] = useState("");
  
  // State for editing
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editingPromptText, setEditingPromptText] = useState("");
  const [fieldPromptVersionDescription, setFieldPromptVersionDescription] = useState("");
  const [selectedFieldPromptVersionId, setSelectedFieldPromptVersionId] = useState<string | null>(null);
  const [editingFieldProperties, setEditingFieldProperties] = useState<string | null>(null);
  const [editedProperties, setEditedProperties] = useState<Array<{name: string, type: FieldType, description?: string}>>([]);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [postProcessing, setPostProcessing] = useState("");
  const [extractionModel, setExtractionModel] = useState("gpt-5-mini");
  const [ocrEngine, setOcrEngine] = useState("azure-di-prebuilt");
  
  // State for adding field
  const [isAddingField, setIsAddingField] = useState(false);
  const [newFieldName, setNewFieldName] = useState("");
  const [newFieldType, setNewFieldType] = useState<FieldType>("string");
  const [newFieldDescription, setNewFieldDescription] = useState("");
  const [newFieldPrompt, setNewFieldPrompt] = useState("");
  const [newFieldArrayItemType, setNewFieldArrayItemType] = useState<FieldType>("string");
  const [newFieldObjectProperties, setNewFieldObjectProperties] = useState<Array<{name: string, type: FieldType, description?: string}>>([]);
  const [aiFieldInput, setAiFieldInput] = useState("");
  
  // State for label suggestions
  const [labelSuggestions, setLabelSuggestions] = useState<LabelSuggestion[]>([]);
  const [suggestionMeta, setSuggestionMeta] = useState<{ documents_analyzed: number; model: string } | null>(null);
  
  // Fetch document types
  const { data: typesData, isLoading: typesLoading } = useQuery({
    queryKey: ["document-types"],
    queryFn: () => api.listDocumentTypes(),
  });
  
  // Fetch labels
  const { data: labelsData, isLoading: labelsLoading } = useQuery({
    queryKey: ["labels", selectedTypeId],
    queryFn: () => (
      selectedTypeId
        ? api.listLabels(selectedTypeId, true)
        : Promise.resolve({ labels: [], total: 0 })
    ),
  });

  const { data: activeFieldPromptsData } = useQuery({
    queryKey: ["field-prompt-versions", "active", selectedTypeId],
    queryFn: () =>
      selectedTypeId
        ? api.listActiveFieldPromptsByDocumentType(selectedTypeId)
        : Promise.resolve({ field_prompts: {}, total: 0 }),
    enabled: !!selectedTypeId,
  });

  const { data: fieldPromptVersionsData, isLoading: fieldPromptVersionsLoading } = useQuery({
    queryKey: ["field-prompt-versions", selectedTypeId, editingField],
    queryFn: () =>
      selectedTypeId && editingField
        ? api.listFieldPromptVersions(selectedTypeId, editingField)
        : Promise.resolve({ field_prompt_versions: [], total: 0 }),
    enabled: !!selectedTypeId && !!editingField,
  });

  const { data: providerModelsData } = useQuery({
    queryKey: ["provider-models", "openai", "enabled"],
    queryFn: () => api.listOpenAIProviderModels(true),
  });

  useEffect(() => {
    if (!editingField) return;
    const versions = fieldPromptVersionsData?.field_prompt_versions || [];
    const activeVersion = versions.find((version: FieldPromptVersion) => version.is_active);
    if (activeVersion) {
      setSelectedFieldPromptVersionId(activeVersion.id);
      setEditingPromptText(activeVersion.extraction_prompt);
    }
  }, [editingField, fieldPromptVersionsData]);
  
  // Get selected type
  const selectedType = typesData?.types.find(t => t.id === selectedTypeId);

  const setSelectedType = (typeId: string | null) => {
    setSelectedTypeId(typeId);
    try {
      if (typeId) {
        localStorage.setItem(selectedTypeStorageKey, typeId);
      } else {
        localStorage.removeItem(selectedTypeStorageKey);
      }
    } catch {
      // Ignore localStorage errors in restricted environments
    }
  };

  useEffect(() => {
    const availableTypes = typesData?.types || [];
    if (availableTypes.length === 0) return;

    const availableIds = new Set(availableTypes.map((type) => type.id));
    if (selectedTypeId && availableIds.has(selectedTypeId)) return;

    let storedTypeId: string | null = null;
    try {
      storedTypeId = localStorage.getItem(selectedTypeStorageKey);
    } catch {
      storedTypeId = null;
    }

    const nextTypeId =
      storedTypeId && availableIds.has(storedTypeId)
        ? storedTypeId
        : availableTypes[0].id;

    setSelectedType(nextTypeId);
    const nextType = availableTypes.find((type) => type.id === nextTypeId);
    setSystemPrompt(nextType?.system_prompt || "");
    setPostProcessing(nextType?.post_processing || "");
    setExtractionModel(nextType?.extraction_model || "gpt-5-mini");
    setOcrEngine(nextType?.ocr_engine || "azure-di-prebuilt");
  }, [typesData, selectedTypeId, selectedTypeStorageKey]);
  
  // Update local state when selected type changes
  const selectType = (typeId: string) => {
    setSelectedType(typeId);
    const type = typesData?.types.find(t => t.id === typeId);
    if (type) {
      setSystemPrompt(type.system_prompt || "");
      setPostProcessing(type.post_processing || "");
      setExtractionModel(type.extraction_model || "gpt-5-mini");
      setOcrEngine(type.ocr_engine || "azure-di-prebuilt");
    }
  };
  
  // Create document type mutation
  const createTypeMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) => 
      api.createDocumentType(data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["document-types"] });
      setSelectedType(result.type.id);
      setSystemPrompt(result.type.system_prompt || "");
      setPostProcessing(result.type.post_processing || "");
      setExtractionModel(result.type.extraction_model || "gpt-5-mini");
      setOcrEngine(result.type.ocr_engine || "azure-di-prebuilt");
      setIsCreating(false);
      setNewTypeName("");
      setNewTypeDescription("");
      toast({ title: "Document type created", description: `Created "${result.type.name}"` });
    },
    onError: (error: Error) => {
      toast({ title: "Failed to create", description: error.message, variant: "destructive" });
    },
  });
  
  // Update document type mutation
  const updateTypeMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<DocumentType> }) =>
      api.updateDocumentType(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["document-types"] });
      queryClient.invalidateQueries({ queryKey: ["labels"] });
      toast({ title: "Schema saved" });
    },
    onError: (error: Error) => {
      toast({ title: "Failed to save", description: error.message, variant: "destructive" });
    },
  });
  
  // Delete document type mutation
  const deleteTypeMutation = useMutation({
    mutationFn: (id: string) => api.deleteDocumentType(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["document-types"] });
      setSelectedType(null);
      toast({ title: "Document type deleted" });
    },
    onError: (error: Error) => {
      toast({ title: "Failed to delete", description: error.message, variant: "destructive" });
    },
  });
  
  // Suggest labels mutation
  const suggestLabelsMutation = useMutation({
    mutationFn: () => {
      // Get document IDs for this project from localStorage
      let documentIds: string[] = [];
      if (projectId) {
        try {
          const stored = localStorage.getItem("uu-projects");
          if (stored) {
            const projects = JSON.parse(stored);
            const project = projects.find((p: { id: string }) => p.id === projectId);
            documentIds = project?.documentIds || [];
            console.log(`📋 Project: ${projectId}`);
            console.log(`📄 Document IDs for this project:`, documentIds);
          }
        } catch {
          documentIds = [];
        }
      }
      
      const request = { 
        sample_size: 5, 
        existing_labels: true,
        ...(documentIds.length > 0 && { document_ids: documentIds }),
      };
      console.log(`🚀 Sending label suggestion request:`, request);
      console.log(`📦 Request will include document_ids:`, documentIds.length > 0);
      
      return api.suggestLabels(request);
    },
    onSuccess: (response: LabelSuggestionResponse) => {
      setLabelSuggestions(response.suggestions);
      setSuggestionMeta({ documents_analyzed: response.documents_analyzed, model: response.model });
      if (response.suggestions.length === 0) {
        toast({ title: "No suggestions", description: "No new labels could be suggested from documents." });
      } else {
        toast({ title: "Labels suggested", description: `Found ${response.suggestions.length} potential labels from ${response.documents_analyzed} documents.` });
      }
    },
    onError: (error: Error) => {
      toast({ title: "Failed to suggest labels", description: error.message, variant: "destructive" });
    },
  });
  
  // Reject label suggestion mutation
  const rejectSuggestionMutation = useMutation({
    mutationFn: (suggestionId: string) => api.rejectLabelSuggestion(suggestionId),
    onSuccess: (_, suggestionId: string) => {
      setLabelSuggestions(prev => prev.filter(s => s.id !== suggestionId));
      toast({ title: "Suggestion dismissed" });
    },
    onError: (error: Error) => {
      toast({ title: "Failed to reject suggestion", description: error.message, variant: "destructive" });
    },
  });

  const suggestFieldDefinitionMutation = useMutation({
    mutationFn: () => {
      if (!selectedTypeId || !selectedType || !aiFieldInput.trim()) {
        throw new Error("Select a document type and describe the field first.");
      }
      return api.suggestFieldDefinition({
        user_input: aiFieldInput.trim(),
        document_type_id: selectedTypeId,
        existing_field_names: (selectedType.schema_fields || []).map((field) => field.name),
      });
    },
    onSuccess: (suggestion: FieldAssistantResponse) => {
      setNewFieldName(suggestion.name);
      setNewFieldType(suggestion.type);
      setNewFieldDescription(suggestion.description || "");
      setNewFieldPrompt(suggestion.extraction_prompt || "");
      if (suggestion.type === "array") {
        setNewFieldArrayItemType((suggestion.items_type || "string") as FieldType);
        if ((suggestion.items_type || "").toString() === "object") {
          setNewFieldObjectProperties(
            (suggestion.object_properties || []).map((property) => ({
              name: property.name,
              type: property.type,
              description: property.description,
            }))
          );
        } else {
          setNewFieldObjectProperties([]);
        }
      } else if (suggestion.type === "object") {
        setNewFieldArrayItemType("string");
        setNewFieldObjectProperties(
          (suggestion.object_properties || []).map((property) => ({
            name: property.name,
            type: property.type,
            description: property.description,
          }))
        );
      } else {
        setNewFieldArrayItemType("string");
        setNewFieldObjectProperties([]);
      }
      toast({ title: "Field suggestion generated" });
    },
    onError: (error: Error) => {
      toast({ title: "AI suggestion failed", description: error.message, variant: "destructive" });
    },
  });
  
  // Save schema changes
  const saveSchema = () => {
    if (!selectedTypeId) return;
    updateTypeMutation.mutate({
      id: selectedTypeId,
      data: {
        system_prompt: systemPrompt,
        post_processing: postProcessing,
        extraction_model: extractionModel,
        ocr_engine: ocrEngine,
      },
    });
  };
  
  // Add field to schema
  const addField = () => {
    if (!selectedTypeId || !selectedType || !newFieldName.trim()) return;
    
    const newField: SchemaField = {
      name: newFieldName.trim().toLowerCase().replace(/\s+/g, '_'),
      type: newFieldType,
      description: newFieldDescription || undefined,
      extraction_prompt: newFieldPrompt.trim() || undefined,
    };

    // Handle object type with properties
    if (newFieldType === "object" && newFieldObjectProperties.length > 0) {
      const properties: Record<string, SchemaField> = {};
      newFieldObjectProperties.forEach(prop => {
        properties[prop.name] = {
          name: prop.name,
          type: prop.type,
          description: prop.description,
        };
      });
      newField.properties = properties;
    }
    
    // Handle array type with items
    if (newFieldType === "array") {
      if (newFieldArrayItemType === "object" && newFieldObjectProperties.length > 0) {
        // Array of objects
        const properties: Record<string, SchemaField> = {};
        newFieldObjectProperties.forEach(prop => {
          properties[prop.name] = {
            name: prop.name,
            type: prop.type,
            description: prop.description,
          };
        });
        newField.items = {
          name: "item",
          type: "object",
          properties: properties,
        };
      } else {
        // Array of simple types
        newField.items = {
          name: "item",
          type: newFieldArrayItemType,
        };
      }
    }
    
    const updatedFields = [...(selectedType.schema_fields || []), newField];
    
    updateTypeMutation.mutate({
      id: selectedTypeId,
      data: { schema_fields: updatedFields },
    });
    
    setIsAddingField(false);
    setNewFieldName("");
    setNewFieldType("string");
    setNewFieldDescription("");
    setNewFieldPrompt("");
    setNewFieldArrayItemType("string");
    setNewFieldObjectProperties([]);
    setAiFieldInput("");
  };
  
  // Remove field from schema
  const removeField = (fieldName: string) => {
    if (!selectedTypeId || !selectedType) return;
    
    const updatedFields = selectedType.schema_fields.filter(f => f.name !== fieldName);
    
    updateTypeMutation.mutate({
      id: selectedTypeId,
      data: { schema_fields: updatedFields },
    });
  };
  
  // Update field extraction prompt
  const updateFieldPrompt = (fieldName: string, prompt: string) => {
    if (!selectedTypeId || !selectedType) return;
    
    const updatedFields = selectedType.schema_fields.map(f => 
      f.name === fieldName ? { ...f, extraction_prompt: prompt } : f
    );
    
    updateTypeMutation.mutate({
      id: selectedTypeId,
      data: { schema_fields: updatedFields },
    });
    
    closeEditField();
  };

  const openEditField = (fieldName: string) => {
    const activePrompts = activeFieldPromptsData?.field_prompts || {};
    const field = selectedType?.schema_fields.find((f) => f.name === fieldName);
    const prompt =
      activePrompts[fieldName] ||
      field?.extraction_prompt ||
      `Extract the ${fieldName.replace(/_/g, " ")} from the document.`;
    setEditingField(fieldName);
    setEditingPromptText(prompt);
    setFieldPromptVersionDescription("");
    setSelectedFieldPromptVersionId(null);
  };

  const closeEditField = () => {
    setEditingField(null);
    setEditingPromptText("");
    setFieldPromptVersionDescription("");
    setSelectedFieldPromptVersionId(null);
  };

  const createFieldPromptVersionMutation = useMutation({
    mutationFn: (data: {
      name?: string;
      document_type_id: string;
      field_name: string;
      extraction_prompt: string;
      description?: string;
      is_active?: boolean;
    }) => api.createFieldPromptVersion(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["field-prompt-versions"] });
      await queryClient.refetchQueries({ queryKey: ["field-prompt-versions", "active", selectedTypeId] });
      await queryClient.refetchQueries({ queryKey: ["field-prompt-versions", selectedTypeId, editingField] });
      setFieldPromptVersionDescription("");
      toast({ title: "Field prompt version saved" });
    },
    onError: (error: Error) => {
      toast({ title: "Failed to save version", description: error.message, variant: "destructive" });
    },
  });

  const updateFieldPromptVersionMutation = useMutation({
    mutationFn: ({ versionId, data }: { versionId: string; data: { is_active?: boolean } }) =>
      api.updateFieldPromptVersion(versionId, data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["field-prompt-versions"] });
      await queryClient.refetchQueries({ queryKey: ["field-prompt-versions", "active", selectedTypeId] });
      await queryClient.refetchQueries({ queryKey: ["field-prompt-versions", selectedTypeId, editingField] });
      toast({ title: "Field prompt version updated" });
    },
    onError: (error: Error) => {
      toast({ title: "Failed to update version", description: error.message, variant: "destructive" });
    },
  });

  const deleteFieldPromptVersionMutation = useMutation({
    mutationFn: (versionId: string) => api.deleteFieldPromptVersion(versionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["field-prompt-versions"] });
      await queryClient.refetchQueries({ queryKey: ["field-prompt-versions", "active", selectedTypeId] });
      await queryClient.refetchQueries({ queryKey: ["field-prompt-versions", selectedTypeId, editingField] });
      setSelectedFieldPromptVersionId(null);
      toast({ title: "Field prompt version deleted" });
    },
    onError: (error: Error) => {
      toast({ title: "Failed to delete version", description: error.message, variant: "destructive" });
    },
  });

  // Update field properties (for array of objects)
  const updateFieldProperties = (fieldName: string, properties: Array<{name: string, type: FieldType, description?: string}>) => {
    if (!selectedTypeId || !selectedType) return;
    
    const updatedFields = selectedType.schema_fields.map(f => {
      if (f.name === fieldName && f.type === "array" && f.items?.type === "object") {
        const propertiesObj: Record<string, SchemaField> = {};
        properties.forEach(prop => {
          propertiesObj[prop.name] = {
            name: prop.name,
            type: prop.type,
            description: prop.description,
          };
        });
        return {
          ...f,
          items: {
            ...f.items,
            properties: propertiesObj,
          },
        };
      }
      if (f.name === fieldName && f.type === "object") {
        const propertiesObj: Record<string, SchemaField> = {};
        properties.forEach(prop => {
          propertiesObj[prop.name] = {
            name: prop.name,
            type: prop.type,
            description: prop.description,
          };
        });
        return {
          ...f,
          properties: propertiesObj,
        };
      }
      return f;
    });
    
    updateTypeMutation.mutate({
      id: selectedTypeId,
      data: { schema_fields: updatedFields },
    });
    
    setEditingFieldProperties(null);
    setEditedProperties([]);
  };

  if (typesLoading || labelsLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }
  
  const labels = labelsData?.labels || [];
  const activeFieldPrompts = activeFieldPromptsData?.field_prompts || {};
  const activeFieldVersionByName = activeFieldPromptsData?.field_versions || {};
  const activeFieldVersionUpdatedAt = activeFieldPromptsData?.field_version_updated_at || {};
  const schemaFieldNames = new Set((selectedType?.schema_fields || []).map((field) => field.name));
  const labelsForSelectedType = selectedTypeId
    ? labels.filter((label) => schemaFieldNames.has(label.name))
    : [];

  return (
    <div className="h-full p-4">
      <Tabs defaultValue="document-types" className="h-full">
        <TabsList className="mb-4">
          <TabsTrigger value="document-types" className="gap-2">
            <Code className="h-4 w-4" />
            Document Types
          </TabsTrigger>
          <TabsTrigger value="labels" className="gap-2">
            <Tag className="h-4 w-4" />
            Labels ({labelsForSelectedType.length})
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="document-types" className="h-[calc(100%-3rem)]">
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
      {/* Visual Schema Builder - Left Side */}
      <div className="space-y-6">
        <Card className="h-full border-none shadow-none bg-background">
          <CardHeader className="px-0 pt-0">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg text-primary">Schema Configuration</CardTitle>
                <p className="text-xs text-muted-foreground mt-1">Define extraction logic and post-processing.</p>
              </div>
              <div className="flex gap-2">
                {selectedType && (
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="gap-2"
                    onClick={saveSchema}
                    disabled={updateTypeMutation.isPending}
                  >
                    {updateTypeMutation.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Save className="h-3.5 w-3.5" />
                    )}
                    Save
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent className="px-0 space-y-4">
            {/* Document Type Selector */}
            <div className="space-y-2 p-4 rounded-lg bg-muted/20 border">
              <label className="text-xs font-bold uppercase tracking-wider text-primary">
                Document Type
              </label>
              <div className="flex gap-2">
                <Select 
                  value={selectedTypeId || ""} 
                  onValueChange={selectType}
                >
                  <SelectTrigger className="flex-1 bg-background">
                    <SelectValue placeholder="Select document type..." />
                  </SelectTrigger>
                  <SelectContent>
                    {typesData?.types.map(type => (
                      <SelectItem key={type.id} value={type.id}>
                        {type.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button 
                  variant="outline" 
                  size="icon"
                  onClick={() => setIsCreating(true)}
                >
                  <Plus className="h-4 w-4" />
                </Button>
                {selectedType && (
                  <>
                    <Button 
                      variant="outline" 
                      size="icon"
                      onClick={() => {
                        setEditTypeName(selectedType.name);
                        setEditTypeDescription(selectedType.description || "");
                        setIsEditingType(true);
                      }}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button 
                      variant="outline" 
                      size="icon"
                      className="text-destructive hover:bg-destructive/10"
                      onClick={() => deleteTypeMutation.mutate(selectedTypeId!)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </>
                )}
              </div>
              {selectedType?.description && (
                <p className="text-xs text-muted-foreground">{selectedType.description}</p>
              )}
            </div>
            
            {selectedType ? (
              <>
                <div className="space-y-2 p-4 rounded-lg bg-muted/20 border">
                  <label className="text-xs font-bold uppercase tracking-wider flex items-center gap-2 text-primary">
                    <MessageSquare className="h-3.5 w-3.5" /> System Prompt
                  </label>
                  <Textarea 
                    placeholder="Enter system instructions..." 
                    className="bg-background text-sm min-h-[120px] border-muted focus-visible:ring-primary"
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                  />
                </div>
                <div className="space-y-2 p-4 rounded-lg bg-muted/20 border">
                  <label className="text-xs font-bold uppercase tracking-wider flex items-center gap-2 text-primary">
                    <Code className="h-3.5 w-3.5" /> Post-Processing Logic
                  </label>
                  <Textarea 
                    placeholder="Enter JavaScript/Python for post-processing..." 
                    className="bg-background text-sm font-mono min-h-[120px] border-muted focus-visible:ring-primary"
                    value={postProcessing}
                    onChange={(e) => setPostProcessing(e.target.value)}
                  />
                </div>
              </>
            ) : (
              <div className="p-8 text-center text-muted-foreground border border-dashed rounded-lg">
                <p className="text-sm">Select or create a document type to configure its schema.</p>
              </div>
            )}

            <Card className="border-accent/20 bg-accent/5">
              <CardHeader className="py-4">
                <CardTitle className="text-sm flex items-center gap-2 text-primary">
                  <Settings2 className="h-4 w-4" />
                  Extraction Engine Settings
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] uppercase font-bold text-muted-foreground">Model Choice</label>
                    <Select value={extractionModel} onValueChange={setExtractionModel}>
                      <SelectTrigger className="h-8 text-xs bg-background">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {!providerModelsData?.models?.length && (
                          <SelectItem value={extractionModel}>{extractionModel}</SelectItem>
                        )}
                        {providerModelsData?.models?.length &&
                          !providerModelsData.models.some((model) => model.model_id === extractionModel) && (
                            <SelectItem value={extractionModel}>{extractionModel}</SelectItem>
                          )}
                        {(providerModelsData?.models || []).map((model) => (
                          <SelectItem key={model.model_id} value={model.model_id}>
                            {model.display_name || model.model_id}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] uppercase font-bold text-muted-foreground">OCR Engine</label>
                    <Select value={ocrEngine} onValueChange={setOcrEngine}>
                      <SelectTrigger className="h-8 text-xs bg-background">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="azure-di-prebuilt">Azure DI Prebuilt</SelectItem>
                        <SelectItem value="aws-textract">AWS Textract</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </CardContent>
            </Card>
          </CardContent>
        </Card>
      </div>

      {/* Field List - Right Side */}
      <div className="space-y-4 border-l pl-6 border-dashed">
        <div className="flex items-center justify-between mb-4 mt-1">
           <div className="space-y-1">
             <h3 className="text-sm font-bold uppercase tracking-widest text-primary">Fields Definition</h3>
             <p className="text-xs text-muted-foreground">
               {selectedType 
                 ? `${selectedType.schema_fields?.length || 0} fields defined`
                 : "Select a document type first"}
             </p>
           </div>
           
           {selectedType && (
             <Button 
               size="sm" 
               className="gap-2 bg-primary hover:bg-primary/90"
               onClick={() => setIsAddingField(true)}
             >
               <Plus className="h-4 w-4" /> Add Field
             </Button>
           )}
        </div>

        <div className="space-y-4 overflow-auto max-h-[calc(100vh-12rem)] pr-2">
          {selectedType?.schema_fields?.map((field) => (
            <div key={field.name} className="flex flex-col rounded-lg border bg-card shadow-sm hover:shadow-md hover:border-accent/40 transition-all overflow-hidden group">
              <div className="flex items-center gap-3 p-3 bg-card border-b">
                <div className="cursor-grab text-muted-foreground/30 hover:text-muted-foreground">
                  <GripVertical className="h-4 w-4" />
                </div>
                <div className="flex-1 flex items-center gap-2 min-w-0">
                  <span className="font-mono text-sm font-medium truncate text-primary">{field.name}</span>
                  <Badge variant="outline" className="text-[10px] h-4 px-1.5 font-mono text-muted-foreground uppercase">{field.type}</Badge>
                  <Badge variant="secondary" className="text-[10px] h-4 px-1.5 font-mono">
                    v{activeFieldVersionByName[field.name] || "0.0"}
                  </Badge>
                  {activeFieldVersionUpdatedAt[field.name] && (
                    <span className="text-[10px] text-muted-foreground">
                      updated {new Date(activeFieldVersionUpdatedAt[field.name]).toLocaleString()}
                    </span>
                  )}
                  {field.type === "array" && field.items && (
                    <Badge variant="secondary" className="text-[10px] h-4 px-1.5 font-mono">
                      {field.items.type}[]
                    </Badge>
                  )}
                  {field.required && (
                    <Badge variant="secondary" className="text-[10px] h-4 px-1.5">Required</Badge>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-7 w-7 text-muted-foreground hover:text-primary hover:bg-primary/5" 
                    title="Edit Prompt"
                    onClick={() => openEditField(field.name)}
                  >
                    <Edit3 className="h-3.5 w-3.5" />
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/5" 
                    title="Remove Field"
                    onClick={() => removeField(field.name)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              
              <div className="p-3 bg-background">
                {field.description && (
                  <p className="text-xs text-muted-foreground mb-2">{field.description}</p>
                )}
                
                {/* Show nested structure for object and array of objects */}
                {(field.type === "object" && field.properties) ||
                (field.type === "array" && field.items?.type === "object" && field.items.properties) ? (
                  <div className="mb-3 p-2 bg-muted/30 rounded border text-xs space-y-1">
                    <div className="flex items-center justify-between mb-1">
                      <div className="font-medium text-muted-foreground">Object Properties:</div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5 text-muted-foreground hover:text-primary"
                        onClick={() => {
                          const sourceProps =
                            field.type === "object" ? field.properties! : field.items!.properties!;
                          const props = Object.entries(sourceProps).map(([name, schema]) => ({
                            name,
                            type: schema.type as FieldType,
                            description: schema.description,
                          }));
                          setEditedProperties(props);
                          setEditingFieldProperties(field.name);
                        }}
                      >
                        <Edit3 className="h-3 w-3" />
                      </Button>
                    </div>
                    {Object.entries(field.type === "object" ? field.properties! : field.items!.properties!).map(([propName, propSchema]) => (
                      <div key={propName} className="flex items-center gap-2 pl-2">
                        <span className="font-mono text-[10px]">{propName}</span>
                        <Badge variant="outline" className="text-[9px] h-3 px-1 font-mono">{propSchema.type}</Badge>
                        {propSchema.description && (
                          <span className="text-[10px] text-muted-foreground">- {propSchema.description}</span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : null}
                
                <div className="relative">
                  <label className="absolute -top-2 left-2 bg-background px-1 text-[9px] font-bold text-muted-foreground uppercase tracking-wider">Extraction Prompt</label>
                  <Textarea 
                    className="min-h-[60px] text-xs resize-none border-muted focus-visible:ring-accent bg-transparent"
                    value={
                      activeFieldPrompts[field.name] ||
                      field.extraction_prompt ||
                      `Extract the ${field.name.replace(/_/g, ' ')} from the document.`
                    }
                    readOnly
                  />
                </div>
              </div>
            </div>
          ))}
          
          {selectedType && (
            <Button 
              variant="outline" 
              className="w-full border-dashed border-muted-foreground/20 text-muted-foreground hover:border-accent hover:text-accent h-12"
              onClick={() => setIsAddingField(true)}
            >
              <Plus className="h-4 w-4 mr-2" /> Add Another Field
            </Button>
          )}
          
          {!selectedType && (
            <div className="p-8 text-center text-muted-foreground border border-dashed rounded-lg">
              <p className="text-sm">Select a document type to define extraction fields.</p>
              <p className="text-xs mt-1">Fields are specific to each document type (e.g., invoice_number for Invoices).</p>
              <p className="text-xs mt-3">For annotation labels (Person, Date, etc.), use the <strong>Labels</strong> tab.</p>
            </div>
          )}
        </div>
      </div>
      
      {/* Create Document Type Dialog */}
      <Dialog open={isCreating} onOpenChange={setIsCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Document Type</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input 
                placeholder="e.g., Invoice, Contract, Claim Form"
                value={newTypeName}
                onChange={(e) => setNewTypeName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <Textarea 
                placeholder="Describe this document type..."
                value={newTypeDescription}
                onChange={(e) => setNewTypeDescription(e.target.value)}
                className="min-h-[100px]"
              />
              <p className="text-xs text-muted-foreground">
                This description will be used by the AI when classifying documents.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreating(false)}>Cancel</Button>
            <Button 
              onClick={() => createTypeMutation.mutate({ 
                name: newTypeName, 
                description: newTypeDescription || undefined 
              })}
              disabled={!newTypeName.trim() || createTypeMutation.isPending}
            >
              {createTypeMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Document Type Dialog */}
      <Dialog open={isEditingType} onOpenChange={setIsEditingType}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Document Type</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input 
                placeholder="e.g., Invoice, Contract, Claim Form"
                value={editTypeName}
                onChange={(e) => setEditTypeName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <Textarea 
                placeholder="Describe this document type..."
                value={editTypeDescription}
                onChange={(e) => setEditTypeDescription(e.target.value)}
                className="min-h-[100px]"
              />
              <p className="text-xs text-muted-foreground">
                This description will be used by the AI when classifying documents.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditingType(false)}>Cancel</Button>
            <Button 
              onClick={() => {
                if (!selectedTypeId) return;
                updateTypeMutation.mutate({
                  id: selectedTypeId,
                  data: { 
                    name: editTypeName, 
                    description: editTypeDescription || undefined 
                  }
                });
                setIsEditingType(false);
              }}
              disabled={!editTypeName.trim() || updateTypeMutation.isPending}
            >
              {updateTypeMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* Add Field Dialog */}
      <Dialog open={isAddingField} onOpenChange={setIsAddingField}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Add Field</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-3 p-3 border rounded-lg bg-muted/20">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Sparkles className="h-4 w-4 text-primary" />
                AI Field Assistant
              </div>
              <Textarea
                placeholder="Describe the field you want (e.g., 'capture all claim line items with area, damage, and estimated cost')."
                value={aiFieldInput}
                onChange={(e) => setAiFieldInput(e.target.value)}
                className="min-h-[80px]"
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => suggestFieldDefinitionMutation.mutate()}
                disabled={!aiFieldInput.trim() || suggestFieldDefinitionMutation.isPending}
              >
                {suggestFieldDefinitionMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Suggest Field with AI
              </Button>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Field Name</label>
              <Input 
                placeholder="e.g., invoice_number, claim_items"
                value={newFieldName}
                onChange={(e) => setNewFieldName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Type</label>
              <Select value={newFieldType} onValueChange={(v) => setNewFieldType(v as FieldType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="string">String</SelectItem>
                  <SelectItem value="number">Number</SelectItem>
                  <SelectItem value="date">Date</SelectItem>
                  <SelectItem value="boolean">Boolean</SelectItem>
                  <SelectItem value="object">Object</SelectItem>
                  <SelectItem value="array">Array</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {/* Object / Array Configuration */}
            {(newFieldType === "object" || newFieldType === "array") && (
              <div className="space-y-4 p-4 border rounded-lg bg-muted/30">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Code className="h-4 w-4" />
                  {newFieldType === "object" ? "Object Properties" : "Array Item Configuration"}
                </div>
                {newFieldType === "array" && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Item Type</label>
                    <Select value={newFieldArrayItemType} onValueChange={(v) => setNewFieldArrayItemType(v as FieldType)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="string">String</SelectItem>
                        <SelectItem value="number">Number</SelectItem>
                        <SelectItem value="date">Date</SelectItem>
                        <SelectItem value="boolean">Boolean</SelectItem>
                        <SelectItem value="object">Object (for tables)</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {newFieldArrayItemType === "object" 
                        ? "Perfect for extracting table rows with multiple columns" 
                        : "Each item will be a simple value"}
                    </p>
                  </div>
                )}
                
                {/* Object Properties for object and array<object> */}
                {(newFieldType === "object" || (newFieldType === "array" && newFieldArrayItemType === "object")) && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium">Object Properties</label>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setNewFieldObjectProperties([...newFieldObjectProperties, { name: "", type: "string" }])}
                      >
                        <Plus className="h-3 w-3 mr-1" /> Add Property
                      </Button>
                    </div>
                    
                    {newFieldObjectProperties.length === 0 && (
                      <div className="text-xs text-muted-foreground p-3 border border-dashed rounded">
                        Add properties for each column in your table (e.g., item_name, description, cost)
                      </div>
                    )}
                    
                    {newFieldObjectProperties.map((prop, idx) => (
                      <div key={idx} className="flex gap-2 items-start p-3 border rounded bg-background">
                        <div className="flex-1 space-y-2">
                          <Input
                            placeholder="Property name (e.g., item_name)"
                            value={prop.name}
                            onChange={(e) => {
                              const updated = [...newFieldObjectProperties];
                              updated[idx].name = e.target.value;
                              setNewFieldObjectProperties(updated);
                            }}
                            className="h-8 text-sm"
                          />
                          <div className="flex items-center gap-2">
                            <div className="w-[140px]">
                              <Select 
                                value={prop.type} 
                                onValueChange={(v) => {
                                  const updated = [...newFieldObjectProperties];
                                  updated[idx].type = v as FieldType;
                                  setNewFieldObjectProperties(updated);
                                }}
                              >
                                <SelectTrigger className="h-8 text-sm w-full">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="string">String</SelectItem>
                                  <SelectItem value="number">Number</SelectItem>
                                  <SelectItem value="date">Date</SelectItem>
                                  <SelectItem value="boolean">Boolean</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div className="flex-1 min-w-0">
                              <Input
                                placeholder="Description (optional)"
                                value={prop.description || ""}
                                onChange={(e) => {
                                  const updated = [...newFieldObjectProperties];
                                  updated[idx].description = e.target.value;
                                  setNewFieldObjectProperties(updated);
                                }}
                                className="h-8 text-sm w-full min-w-[180px] text-foreground caret-primary"
                              />
                            </div>
                          </div>
                        </div>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 text-destructive"
                          onClick={() => {
                            setNewFieldObjectProperties(newFieldObjectProperties.filter((_, i) => i !== idx));
                          }}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            
            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <Input 
                placeholder="What this field represents..."
                value={newFieldDescription}
                onChange={(e) => setNewFieldDescription(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Extraction Prompt</label>
              <Textarea
                placeholder="Extract this field exactly as it appears in the document."
                value={newFieldPrompt}
                onChange={(e) => setNewFieldPrompt(e.target.value)}
                className="min-h-[100px]"
              />
            </div>
            
            {/* Example Preview */}
            {(newFieldType === "object" || (newFieldType === "array" && newFieldArrayItemType === "object")) && newFieldObjectProperties.length > 0 && (
              <div className="p-3 bg-muted/50 rounded border text-xs space-y-2">
                <div className="font-medium">Example Output:</div>
                <pre className="text-[10px] overflow-x-auto">
{newFieldType === "object" ? `{
  "${newFieldName || 'field_name'}": {
${newFieldObjectProperties.map(p => `    "${p.name || 'property'}": ${p.type === 'number' ? '0' : p.type === 'boolean' ? 'true' : '"value"'}`).join(',\n')}
  }
}` : `{
  "${newFieldName || 'field_name'}": [
    {
${newFieldObjectProperties.map(p => `      "${p.name || 'property'}": ${p.type === 'number' ? '0' : p.type === 'boolean' ? 'true' : '"value"'}`).join(',\n')}
    }
  ]
}`}
                </pre>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setIsAddingField(false);
              setNewFieldObjectProperties([]);
              setNewFieldArrayItemType("string");
              setNewFieldPrompt("");
              setAiFieldInput("");
            }}>Cancel</Button>
            <Button 
              onClick={addField}
              disabled={
                !newFieldName.trim() ||
                updateTypeMutation.isPending ||
                (newFieldType === "object" && newFieldObjectProperties.length === 0) ||
                (newFieldType === "array" && newFieldArrayItemType === "object" && newFieldObjectProperties.length === 0)
              }
            >
              {updateTypeMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Add Field
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* Edit Field Prompt Dialog */}
      <Dialog open={!!editingField} onOpenChange={(open) => {
        if (!open) closeEditField();
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Extraction Prompt</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Active Version</label>
              <Select
                value={selectedFieldPromptVersionId || "none"}
                onValueChange={(value) => {
                  if (value === "none") {
                    setSelectedFieldPromptVersionId(null);
                    return;
                  }
                  setSelectedFieldPromptVersionId(value);
                  const selectedVersion = (fieldPromptVersionsData?.field_prompt_versions || []).find(
                    (version: FieldPromptVersion) => version.id === value
                  );
                  if (selectedVersion) {
                    setEditingPromptText(selectedVersion.extraction_prompt);
                  }
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder={fieldPromptVersionsLoading ? "Loading versions..." : "Select a saved version"} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Current prompt</SelectItem>
                  {(fieldPromptVersionsData?.field_prompt_versions || []).map((version: FieldPromptVersion) => (
                    <SelectItem key={version.id} value={version.id}>
                      {version.name}{version.is_active ? " (active)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedFieldPromptVersionId && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      updateFieldPromptVersionMutation.mutate({
                        versionId: selectedFieldPromptVersionId,
                        data: { is_active: true },
                      });
                    }}
                    disabled={updateFieldPromptVersionMutation.isPending}
                  >
                    Set Active
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => deleteFieldPromptVersionMutation.mutate(selectedFieldPromptVersionId)}
                    disabled={deleteFieldPromptVersionMutation.isPending}
                  >
                    Delete
                  </Button>
                </div>
              )}
            </div>

            <Textarea 
              className="min-h-[150px]"
              placeholder="Enter extraction prompt..."
              value={editingPromptText}
              onChange={(e) => setEditingPromptText(e.target.value)}
            />

            <div className="space-y-2 border-t pt-4">
              <label className="text-sm font-medium">Save As New Version</label>
              <Input
                placeholder="Description (optional)"
                value={fieldPromptVersionDescription}
                onChange={(e) => setFieldPromptVersionDescription(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Version number is automatic: first is 0.0, then 0.1, 0.2, ...
              </p>
              <Button
                variant="outline"
                onClick={() => {
                  if (!selectedTypeId || !editingField || !editingPromptText.trim()) {
                    return;
                  }
                  createFieldPromptVersionMutation.mutate({
                    document_type_id: selectedTypeId,
                    field_name: editingField,
                    extraction_prompt: editingPromptText,
                    description: fieldPromptVersionDescription.trim() || undefined,
                    is_active: true,
                  });
                }}
                disabled={
                  createFieldPromptVersionMutation.isPending ||
                  !editingPromptText.trim()
                }
              >
                Save Version + Set Active
              </Button>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeEditField}>Cancel</Button>
            <Button 
              onClick={() => {
                if (editingField) {
                  updateFieldPrompt(editingField, editingPromptText);
                }
              }}
              disabled={updateTypeMutation.isPending || !editingPromptText.trim()}
            >
              {updateTypeMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Field Properties Dialog */}
      <Dialog open={!!editingFieldProperties} onOpenChange={() => {
        setEditingFieldProperties(null);
        setEditedProperties([]);
      }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Object Properties</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Properties for {editingFieldProperties}</label>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setEditedProperties([...editedProperties, { name: "", type: "string" }])}
              >
                <Plus className="h-3 w-3 mr-1" /> Add Property
              </Button>
            </div>
            
            {editedProperties.length === 0 && (
              <div className="text-xs text-muted-foreground p-3 border border-dashed rounded">
                Add properties for each column in your table (e.g., item_name, description, cost)
              </div>
            )}
            
            {editedProperties.map((prop, idx) => (
              <div key={idx} className="flex gap-2 items-start p-3 border rounded bg-background">
                <div className="flex-1 space-y-2">
                  <Input
                    placeholder="Property name (e.g., item_name)"
                    value={prop.name}
                    onChange={(e) => {
                      const updated = [...editedProperties];
                      updated[idx].name = e.target.value;
                      setEditedProperties(updated);
                    }}
                    className="h-8 text-sm"
                  />
                  <div className="flex items-center gap-2">
                    <div className="w-[140px]">
                      <Select 
                        value={prop.type} 
                        onValueChange={(v) => {
                          const updated = [...editedProperties];
                          updated[idx].type = v as FieldType;
                          setEditedProperties(updated);
                        }}
                      >
                        <SelectTrigger className="h-8 text-sm w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="string">String</SelectItem>
                          <SelectItem value="number">Number</SelectItem>
                          <SelectItem value="date">Date</SelectItem>
                          <SelectItem value="boolean">Boolean</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex-1 min-w-0">
                      <Input
                        placeholder="Description (optional)"
                        value={prop.description || ""}
                        onChange={(e) => {
                          const updated = [...editedProperties];
                          updated[idx].description = e.target.value;
                          setEditedProperties(updated);
                        }}
                        className="h-8 text-sm w-full min-w-[180px] text-foreground caret-primary"
                      />
                    </div>
                  </div>
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 text-destructive"
                  onClick={() => {
                    setEditedProperties(editedProperties.filter((_, i) => i !== idx));
                  }}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setEditingFieldProperties(null);
              setEditedProperties([]);
            }}>Cancel</Button>
            <Button 
              onClick={() => {
                if (editingFieldProperties) {
                  updateFieldProperties(editingFieldProperties, editedProperties);
                }
              }}
              disabled={updateTypeMutation.isPending || editedProperties.some(p => !p.name.trim())}
            >
              {updateTypeMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
        </TabsContent>
        
        {/* Labels Tab */}
        <TabsContent value="labels" className="h-[calc(100%-3rem)] overflow-auto">
          <div className="space-y-6">
            {/* Label Suggestions Section */}
            <Card className="border-accent/30 bg-accent/5">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base text-primary flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      Suggest Labels from Documents
                    </CardTitle>
                    <p className="text-xs text-muted-foreground mt-1">
                      Analyze your uploaded documents to suggest potential schema fields.
                    </p>
                  </div>
                  <Button 
                    size="sm" 
                    variant="outline"
                    className="gap-2"
                    onClick={() => suggestLabelsMutation.mutate()}
                    disabled={suggestLabelsMutation.isPending}
                  >
                    {suggestLabelsMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <FileText className="h-4 w-4" />
                    )}
                    {suggestLabelsMutation.isPending ? "Analyzing..." : "Suggest from Documents"}
                  </Button>
                </div>
              </CardHeader>
              
              {labelSuggestions.length > 0 && (
                <CardContent className="pt-0">
                  {suggestionMeta && (
                    <p className="text-xs text-muted-foreground mb-3">
                      Analyzed {suggestionMeta.documents_analyzed} documents using {suggestionMeta.model}
                    </p>
                  )}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {labelSuggestions.map((suggestion) => (
                      <Card key={suggestion.id} className="border bg-background hover:shadow-md transition-shadow">
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-3 flex-1 min-w-0">
                              <div 
                                className="w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0"
                                style={{ backgroundColor: suggestion.suggested_color }}
                              >
                                {suggestion.name.charAt(0).toUpperCase()}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <h4 className="font-medium text-sm truncate">{suggestion.name}</h4>
                                  <Badge variant="secondary" className="text-[10px]">
                                    {Math.round(suggestion.confidence * 100)}% confidence
                                  </Badge>
                                </div>
                                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                  {suggestion.description}
                                </p>
                                {suggestion.source_examples.length > 0 && (
                                  <div className="mt-2">
                                    <p className="text-[10px] font-medium text-muted-foreground mb-1">Examples found:</p>
                                    <div className="flex flex-wrap gap-1">
                                      {suggestion.source_examples.slice(0, 3).map((ex, i) => (
                                        <Badge key={i} variant="outline" className="text-[10px] max-w-[150px] truncate">
                                          {ex}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                            <div className="flex flex-col gap-1 flex-shrink-0">
                              <Button 
                                size="icon"
                                variant="ghost"
                                className="h-8 w-8 text-red-600 hover:bg-red-100 hover:text-red-700"
                                onClick={() => rejectSuggestionMutation.mutate(suggestion.id)}
                                disabled={rejectSuggestionMutation.isPending}
                                title="Dismiss suggestion"
                              >
                                {rejectSuggestionMutation.isPending ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <ThumbsDown className="h-4 w-4" />
                                )}
                              </Button>
                            </div>
                          </div>
                          <p className="text-[10px] text-muted-foreground mt-2 italic">
                            {suggestion.reasoning}
                          </p>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
            
            <Card className="border-none shadow-none bg-background">
              <CardHeader className="px-0 pt-0">
                <div>
                  <CardTitle className="text-lg text-primary flex items-center gap-2">
                    <Tag className="h-5 w-5" />
                    Annotation Labels
                  </CardTitle>
                  <p className="text-xs text-muted-foreground mt-1">
                    Labels are generated from the selected document type schema fields and cannot be edited independently.
                  </p>
                </div>
              </CardHeader>
              <CardContent className="px-0">
                {!selectedTypeId ? (
                  <div className="p-8 text-center text-muted-foreground border border-dashed rounded-lg">
                    <Tag className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p className="text-sm">Select a document type to view generated labels.</p>
                  </div>
                ) : labelsForSelectedType.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground border border-dashed rounded-lg">
                    <Tag className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p className="text-sm">No labels generated yet.</p>
                    <p className="text-xs mt-2">Add schema fields in the Document Types tab to generate labels.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {labelsForSelectedType.map((label) => (
                      <Card key={label.id} className="border hover:shadow-md transition-shadow">
                        <CardContent className="p-4">
                          <div className="flex items-start">
                            <div className="flex items-center gap-3">
                              <div 
                                className="w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm"
                                style={{ backgroundColor: label.color }}
                              >
                                {label.name.charAt(0).toUpperCase()}
                              </div>
                              <div>
                                <h4 className="font-medium text-sm">{label.name}</h4>
                                {label.description && (
                                  <p className="text-xs text-muted-foreground">{label.description}</p>
                                )}
                                {label.shortcut && (
                                  <Badge variant="outline" className="text-[10px] mt-1">
                                    Shortcut: {label.shortcut}
                                  </Badge>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="mt-3 flex items-center gap-2">
                            <div 
                              className="h-2 flex-1 rounded-full"
                              style={{ backgroundColor: label.color }}
                            />
                            <span className="text-[10px] text-muted-foreground font-mono">
                              {label.color}
                            </span>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
