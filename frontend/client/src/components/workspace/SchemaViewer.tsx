import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Code,
  Plus,
  Trash2,
  Settings2,
  GripVertical,
  Sparkles,
  MessageSquare,
  Search,
  Edit3,
  Save,
  X,
  Loader2,
  FileText,
  Edit,
  ImagePlus,
  Image,
  ChevronDown,
  ChevronRight,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  api,
  DocumentType,
  ExtractionMethod,
  SchemaField,
  FieldType,
  FieldAssistantResponse,
  FieldAssistantProperty,
  FieldPromptVersion,
  VisualAnalysisResponse,
  VisualContentType,
} from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tag } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface NestedProperty {
  name: string;
  type: FieldType;
  description?: string;
  items_type?: FieldType;
  properties?: NestedProperty[];
}

function nestedPropertiesToSchemaProperties(
  props: NestedProperty[],
): Record<string, SchemaField> {
  const result: Record<string, SchemaField> = {};
  props.forEach((prop, index) => {
    const field: SchemaField = {
      name: prop.name,
      type: prop.type,
      description: prop.description,
      order: index,
    };
    if (
      prop.type === "object" &&
      prop.properties &&
      prop.properties.length > 0
    ) {
      field.properties = nestedPropertiesToSchemaProperties(prop.properties);
    }
    if (
      prop.type === "array" &&
      prop.properties &&
      prop.properties.length > 0
    ) {
      field.items = {
        name: "item",
        type: "object",
        properties: nestedPropertiesToSchemaProperties(prop.properties),
      };
    } else if (prop.type === "array" && prop.items_type) {
      field.items = {
        name: "item",
        type: prop.items_type,
      };
    }
    result[prop.name] = field;
  });
  return result;
}

function schemaPropertiesToNestedProperties(
  props: Record<string, SchemaField>,
): NestedProperty[] {
  const entries = Object.entries(props);
  entries.sort(([, a], [, b]) => {
    const orderA = a.order ?? Number.MAX_SAFE_INTEGER;
    const orderB = b.order ?? Number.MAX_SAFE_INTEGER;
    return orderA - orderB;
  });

  return entries.map(([name, schema]) => {
    const nested: NestedProperty = {
      name,
      type: schema.type,
      description: schema.description,
    };

    if (schema.type === "object" && schema.properties) {
      nested.properties = schemaPropertiesToNestedProperties(schema.properties);
    }

    if (schema.type === "array" && schema.items) {
      if (schema.items.type === "object" && schema.items.properties) {
        nested.properties = schemaPropertiesToNestedProperties(
          schema.items.properties,
        );
      } else {
        nested.items_type = schema.items.type;
      }
    }

    return nested;
  });
}

function assistantPropertiesToNestedProperties(
  props: FieldAssistantProperty[],
): NestedProperty[] {
  return props.map((prop) => {
    const nested: NestedProperty = {
      name: prop.name,
      type: prop.type,
      description: prop.description,
    };

    if (
      prop.type === "object" &&
      prop.properties &&
      prop.properties.length > 0
    ) {
      nested.properties = assistantPropertiesToNestedProperties(
        prop.properties,
      );
    }

    if (prop.type === "array") {
      if (
        prop.items_type === "object" &&
        prop.properties &&
        prop.properties.length > 0
      ) {
        nested.properties = assistantPropertiesToNestedProperties(
          prop.properties,
        );
      } else if (prop.items_type && prop.items_type !== "object") {
        nested.items_type = prop.items_type;
      }
    }

    return nested;
  });
}

function generateExampleOutput(
  props: NestedProperty[],
  indent: number = 0,
): string {
  const pad = "  ".repeat(indent);
  const lines: string[] = [];

  props.forEach((prop, idx) => {
    const comma = idx < props.length - 1 ? "," : "";

    if (
      prop.type === "object" &&
      prop.properties &&
      prop.properties.length > 0
    ) {
      lines.push(`${pad}"${prop.name}": {`);
      lines.push(generateExampleOutput(prop.properties, indent + 1));
      lines.push(`${pad}}${comma}`);
    } else if (
      prop.type === "array" &&
      prop.properties &&
      prop.properties.length > 0
    ) {
      lines.push(`${pad}"${prop.name}": [`);
      lines.push(`${pad}  {`);
      lines.push(generateExampleOutput(prop.properties, indent + 2));
      lines.push(`${pad}  }`);
      lines.push(`${pad}]${comma}`);
    } else if (prop.type === "array") {
      const itemType = prop.items_type || "string";
      const exampleVal =
        itemType === "number"
          ? "0"
          : itemType === "boolean"
            ? "true"
            : '"value"';
      lines.push(`${pad}"${prop.name}": [${exampleVal}]${comma}`);
    } else {
      const exampleVal =
        prop.type === "number"
          ? "0"
          : prop.type === "boolean"
            ? "true"
            : prop.type === "date"
              ? '"2024-01-01"'
              : '"value"';
      lines.push(`${pad}"${prop.name}": ${exampleVal}${comma}`);
    }
  });

  return lines.join("\n");
}

interface PropertyEditorProps {
  properties: NestedProperty[];
  onChange: (properties: NestedProperty[]) => void;
  depth?: number;
  maxDepth?: number;
}

function PropertyEditor({
  properties,
  onChange,
  depth = 0,
  maxDepth = 3,
}: PropertyEditorProps) {
  const updateProperty = (idx: number, updates: Partial<NestedProperty>) => {
    const updated = [...properties];
    updated[idx] = { ...updated[idx], ...updates };
    onChange(updated);
  };

  const removeProperty = (idx: number) => {
    onChange(properties.filter((_, i) => i !== idx));
  };

  const moveProperty = (idx: number, direction: "up" | "down") => {
    const newIdx = direction === "up" ? idx - 1 : idx + 1;
    if (newIdx < 0 || newIdx >= properties.length) return;
    const updated = [...properties];
    [updated[idx], updated[newIdx]] = [updated[newIdx], updated[idx]];
    onChange(updated);
  };

  const addProperty = () => {
    onChange([...properties, { name: "", type: "string" }]);
  };

  const addNestedProperty = (idx: number) => {
    const updated = [...properties];
    updated[idx].properties = [
      ...(updated[idx].properties || []),
      { name: "", type: "string" },
    ];
    onChange(updated);
  };

  return (
    <div className="space-y-2">
      {properties.length === 0 && depth === 0 && (
        <div className="text-xs text-muted-foreground p-3 border border-dashed rounded">
          Add properties for each column in your table (e.g., item_name,
          description, cost)
        </div>
      )}

      {properties.map((prop, idx) => (
        <div
          key={idx}
          className={`border rounded bg-background ${depth > 0 ? "ml-4 border-l-2 border-l-primary/30" : ""}`}
        >
          <div className="flex gap-2 items-start p-3">
            <div className="flex-1 space-y-2">
              <Input
                placeholder={`Property name${depth > 0 ? " (nested)" : ""}`}
                value={prop.name}
                onChange={(e) => updateProperty(idx, { name: e.target.value })}
                className="h-8 text-sm"
              />
              <div className="flex items-center gap-2 flex-wrap">
                <div className="w-[140px]">
                  <Select
                    value={prop.type}
                    onValueChange={(v) => {
                      const newType = v as FieldType;
                      updateProperty(idx, {
                        type: newType,
                        properties:
                          newType === "object" || newType === "array"
                            ? prop.properties || []
                            : undefined,
                        items_type:
                          newType === "array"
                            ? prop.items_type || "string"
                            : undefined,
                      });
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
                      {depth < maxDepth && (
                        <>
                          <SelectItem value="object">Object</SelectItem>
                          <SelectItem value="array">Array</SelectItem>
                        </>
                      )}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex-1 min-w-[180px]">
                  <Input
                    placeholder="Description (optional)"
                    value={prop.description || ""}
                    onChange={(e) =>
                      updateProperty(idx, { description: e.target.value })
                    }
                    className="h-8 text-sm w-full text-foreground caret-primary"
                  />
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-0.5 flex-shrink-0">
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6 text-muted-foreground hover:text-foreground"
                onClick={() => moveProperty(idx, "up")}
                disabled={idx === 0}
                title="Move up"
              >
                <ArrowUp className="h-3 w-3" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6 text-muted-foreground hover:text-foreground"
                onClick={() => moveProperty(idx, "down")}
                disabled={idx === properties.length - 1}
                title="Move down"
              >
                <ArrowDown className="h-3 w-3" />
              </Button>
            </div>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-destructive flex-shrink-0"
              onClick={() => removeProperty(idx)}
              title="Remove property"
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>

          {/* Nested object properties */}
          {prop.type === "object" && depth < maxDepth && (
            <Collapsible defaultOpen={true}>
              <div className="px-3 pb-2">
                <CollapsibleTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-1 h-6 text-xs text-muted-foreground hover:text-foreground"
                  >
                    <ChevronDown className="h-3 w-3 collapsible-chevron" />
                    Nested Properties ({prop.properties?.length || 0})
                  </Button>
                </CollapsibleTrigger>
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1 h-6 text-xs ml-2"
                  onClick={() => addNestedProperty(idx)}
                >
                  <Plus className="h-3 w-3" /> Add
                </Button>
              </div>
              <CollapsibleContent>
                <div className="px-3 pb-3">
                  <PropertyEditor
                    properties={prop.properties || []}
                    onChange={(nested) =>
                      updateProperty(idx, { properties: nested })
                    }
                    depth={depth + 1}
                    maxDepth={maxDepth}
                  />
                </div>
              </CollapsibleContent>
            </Collapsible>
          )}

          {/* Array sub-property configuration */}
          {prop.type === "array" && depth < maxDepth && (
            <div className="px-3 pb-3 space-y-2 border-t mt-2 pt-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  Array items:
                </span>
                <Select
                  value={
                    prop.properties && prop.properties.length > 0
                      ? "object"
                      : prop.items_type || "string"
                  }
                  onValueChange={(v) => {
                    if (v === "object") {
                      updateProperty(idx, {
                        items_type: undefined,
                        properties: prop.properties || [],
                      });
                    } else {
                      updateProperty(idx, {
                        items_type: v as FieldType,
                        properties: undefined,
                      });
                    }
                  }}
                >
                  <SelectTrigger className="h-7 text-xs w-[120px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="string">String</SelectItem>
                    <SelectItem value="number">Number</SelectItem>
                    <SelectItem value="date">Date</SelectItem>
                    <SelectItem value="boolean">Boolean</SelectItem>
                    <SelectItem value="object">Object</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {(prop.properties && prop.properties.length > 0) ||
              !prop.items_type ||
              prop.items_type === ("object" as FieldType) ? (
                <Collapsible defaultOpen={true}>
                  <div className="flex items-center gap-2">
                    <CollapsibleTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="gap-1 h-6 text-xs text-muted-foreground hover:text-foreground"
                      >
                        <ChevronDown className="h-3 w-3 collapsible-chevron" />
                        Item Properties ({prop.properties?.length || 0})
                      </Button>
                    </CollapsibleTrigger>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="gap-1 h-6 text-xs"
                      onClick={() => addNestedProperty(idx)}
                    >
                      <Plus className="h-3 w-3" /> Add
                    </Button>
                  </div>
                  <CollapsibleContent>
                    <div className="pt-2">
                      <PropertyEditor
                        properties={prop.properties || []}
                        onChange={(nested) =>
                          updateProperty(idx, {
                            properties: nested,
                            items_type: undefined,
                          })
                        }
                        depth={depth + 1}
                        maxDepth={maxDepth}
                      />
                    </div>
                  </CollapsibleContent>
                </Collapsible>
              ) : null}
            </div>
          )}
        </div>
      ))}

      {depth === 0 && (
        <Button
          size="sm"
          variant="outline"
          onClick={addProperty}
          className="mt-2"
        >
          <Plus className="h-3 w-3 mr-1" /> Add Property
        </Button>
      )}
    </div>
  );
}

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
  const [fieldPromptVersionDescription, setFieldPromptVersionDescription] =
    useState("");
  const [selectedFieldPromptVersionId, setSelectedFieldPromptVersionId] =
    useState<string | null>(null);
  const [editingFieldProperties, setEditingFieldProperties] = useState<
    string | null
  >(null);
  const [editedProperties, setEditedProperties] = useState<NestedProperty[]>(
    [],
  );
  const [systemPrompt, setSystemPrompt] = useState("");
  const [postProcessing, setPostProcessing] = useState("");
  const [ocrEngine, setOcrEngine] = useState("native-text");
  const [promptOpen, setPromptOpen] = useState(false);
  const [postProcOpen, setPostProcOpen] = useState(false);

  // State for adding field
  const [isAddingField, setIsAddingField] = useState(false);
  const [editingSchemaFieldName, setEditingSchemaFieldName] = useState<
    string | null
  >(null);
  const [newFieldName, setNewFieldName] = useState("");
  const [newFieldType, setNewFieldType] = useState<FieldType>("string");
  const [newFieldDescription, setNewFieldDescription] = useState("");
  const [newFieldPrompt, setNewFieldPrompt] = useState("");
  const [newFieldArrayItemType, setNewFieldArrayItemType] =
    useState<FieldType>("string");
  const [newFieldObjectProperties, setNewFieldObjectProperties] = useState<
    NestedProperty[]
  >([]);
  const [aiFieldInput, setAiFieldInput] = useState("");
  const [aiScreenshot, setAiScreenshot] = useState<string | null>(null);
  const [extractionMethod, setExtractionMethod] = useState<ExtractionMethod>("llm");
  const [retrievalQuery, setRetrievalQuery] = useState("");

  // Visual analysis state
  const [visualAnalysis, setVisualAnalysis] =
    useState<VisualAnalysisResponse | null>(null);
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);

  // Fetch document types
  const { data: typesData, isLoading: typesLoading } = useQuery({
    queryKey: ["document-types"],
    queryFn: () => api.listDocumentTypes(),
  });

  // Fetch global fields
  const { data: labelsData, isLoading: labelsLoading } = useQuery({
    queryKey: ["labels", selectedTypeId],
    queryFn: () =>
      selectedTypeId
        ? api.listGlobalFields()
        : Promise.resolve({ fields: [], total: 0 }),
  });

  const { data: activeFieldPromptsData } = useQuery({
    queryKey: ["field-prompt-versions", "active", selectedTypeId],
    queryFn: () =>
      selectedTypeId
        ? api.listActiveFieldPromptsByDocumentType(selectedTypeId)
        : Promise.resolve({
            field_prompts: {} as Record<string, string>,
            field_versions: {} as Record<string, string>,
            field_version_updated_at: {} as Record<string, string>,
            total: 0,
          }),
    enabled: !!selectedTypeId,
  });

  const {
    data: fieldPromptVersionsData,
    isLoading: fieldPromptVersionsLoading,
  } = useQuery({
    queryKey: ["field-prompt-versions", selectedTypeId, editingField],
    queryFn: () =>
      selectedTypeId && editingField
        ? api.listFieldPromptVersions(selectedTypeId, editingField)
        : Promise.resolve({ field_prompt_versions: [], total: 0 }),
    enabled: !!selectedTypeId && !!editingField,
  });

  useEffect(() => {
    if (!editingField) return;
    const versions = fieldPromptVersionsData?.field_prompt_versions || [];
    const activeVersion = versions.find(
      (version: FieldPromptVersion) => version.is_active,
    );
    if (activeVersion) {
      setSelectedFieldPromptVersionId(activeVersion.id);
      setEditingPromptText(activeVersion.extraction_prompt);
    }
  }, [editingField, fieldPromptVersionsData]);

  // Get selected type
  const selectedType = typesData?.types.find((t) => t.id === selectedTypeId);

  const setSelectedType = (typeId: string | null) => {
    setSelectedTypeId(typeId);
    if (typeId) {
      localStorage.setItem(selectedTypeStorageKey, typeId);
    } else {
      localStorage.removeItem(selectedTypeStorageKey);
    }
  };

  // Track the schema version we last synced from to detect server updates
  const [lastSyncedSchemaVersionId, setLastSyncedSchemaVersionId] = useState<
    string | null
  >(null);

  useEffect(() => {
    const availableTypes = typesData?.types || [];
    if (availableTypes.length === 0) return;

    const availableIds = new Set(availableTypes.map((type) => type.id));

    if (selectedTypeId && availableIds.has(selectedTypeId)) {
      const currentType = availableTypes.find((t) => t.id === selectedTypeId);
      if (
        currentType &&
        currentType.schema_version_id !== lastSyncedSchemaVersionId
      ) {
        setSystemPrompt(currentType.system_prompt || "");
        setPostProcessing(currentType.post_processing || "");
        setOcrEngine(currentType.ocr_engine || "native-text");
        setLastSyncedSchemaVersionId(currentType.schema_version_id || null);
      }
      return;
    }

    const storedTypeId = localStorage.getItem(selectedTypeStorageKey);
    const nextTypeId =
      storedTypeId && availableIds.has(storedTypeId)
        ? storedTypeId
        : availableTypes[0].id;

    setSelectedType(nextTypeId);
    const nextType = availableTypes.find((type) => type.id === nextTypeId);
    setSystemPrompt(nextType?.system_prompt || "");
    setPostProcessing(nextType?.post_processing || "");
    setOcrEngine(nextType?.ocr_engine || "native-text");
    setLastSyncedSchemaVersionId(nextType?.schema_version_id || null);
  }, [
    typesData,
    selectedTypeId,
    selectedTypeStorageKey,
    lastSyncedSchemaVersionId,
  ]);

  // Update local state when selected type changes
  const selectType = (typeId: string) => {
    setSelectedType(typeId);
    const type = typesData?.types.find((t) => t.id === typeId);
    if (type) {
      setSystemPrompt(type.system_prompt || "");
      setPostProcessing(type.post_processing || "");
      setOcrEngine(type.ocr_engine || "native-text");
      setLastSyncedSchemaVersionId(type.schema_version_id || null);
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
      setOcrEngine(result.type.ocr_engine || "native-text");
      setLastSyncedSchemaVersionId(result.type.schema_version_id || null);
      setIsCreating(false);
      setNewTypeName("");
      setNewTypeDescription("");
      toast({
        title: "Document type created",
        description: `Created "${result.type.name}"`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to create",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Update document type mutation
  const updateTypeMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<DocumentType> }) =>
      api.updateDocumentType(id, data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["document-types"] });
      queryClient.invalidateQueries({ queryKey: ["labels"] });
      if (result.type && result.type.id === selectedTypeId) {
        setSystemPrompt(result.type.system_prompt || "");
        setPostProcessing(result.type.post_processing || "");
        setOcrEngine(result.type.ocr_engine || "native-text");
        setLastSyncedSchemaVersionId(result.type.schema_version_id || null);
      }
      toast({ title: "Schema saved" });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to save",
        description: error.message,
        variant: "destructive",
      });
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
      toast({
        title: "Failed to delete",
        description: error.message,
        variant: "destructive",
      });
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
        existing_field_names: (selectedType.schema_fields || []).map(
          (field) => field.name,
        ),
        screenshot_base64: aiScreenshot || undefined,
      });
    },
    onSuccess: (suggestion: FieldAssistantResponse) => {
      setNewFieldName(suggestion.name);
      setNewFieldType(suggestion.type);
      setNewFieldDescription(suggestion.description || "");
      setNewFieldPrompt(suggestion.extraction_prompt || "");
      if (suggestion.type === "array") {
        setNewFieldArrayItemType(
          (suggestion.items_type || "string") as FieldType,
        );
        if ((suggestion.items_type || "").toString() === "object") {
          setNewFieldObjectProperties(
            assistantPropertiesToNestedProperties(
              suggestion.object_properties || [],
            ),
          );
        } else {
          setNewFieldObjectProperties([]);
        }
      } else if (suggestion.type === "object") {
        setNewFieldArrayItemType("string");
        setNewFieldObjectProperties(
          assistantPropertiesToNestedProperties(
            suggestion.object_properties || [],
          ),
        );
      } else {
        setNewFieldArrayItemType("string");
        setNewFieldObjectProperties([]);
      }
      toast({ title: "Field suggestion generated" });
    },
    onError: (error: Error) => {
      toast({
        title: "AI suggestion failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Analyze image for visual structure
  const analyzeImageMutation = useMutation({
    mutationFn: (imageBase64: string) => {
      return api.analyzeImage({
        image_base64: imageBase64,
        field_name: newFieldName || undefined,
        field_description: newFieldDescription || undefined,
      });
    },
    onSuccess: (analysis: VisualAnalysisResponse) => {
      setVisualAnalysis(analysis);
      // Auto-populate extraction prompt with generated prompt
      if (analysis.generated_extraction_prompt && !newFieldPrompt) {
        setNewFieldPrompt(analysis.generated_extraction_prompt);
      }
      toast({
        title: "Image analyzed",
        description: `Detected ${analysis.visual_content_type} structure`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Image analysis failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Auto-analyze when screenshot is set
  const handleScreenshotChange = (base64: string | null) => {
    setAiScreenshot(base64);
    setVisualAnalysis(null);
    if (base64) {
      setIsAnalyzingImage(true);
      analyzeImageMutation.mutate(base64);
      setIsAnalyzingImage(false);
    }
  };

  // Save schema changes
  const saveSchema = () => {
    if (!selectedTypeId) return;
    updateTypeMutation.mutate({
      id: selectedTypeId,
      data: {
        system_prompt: systemPrompt,
        post_processing: postProcessing,
        ocr_engine: ocrEngine,
      },
    });
  };

  const resetFieldEditorForm = () => {
    setEditingSchemaFieldName(null);
    setIsAddingField(false);
    setNewFieldName("");
    setNewFieldType("string");
    setNewFieldDescription("");
    setNewFieldPrompt("");
    setNewFieldArrayItemType("string");
    setNewFieldObjectProperties([]);
    setAiFieldInput("");
    setAiScreenshot(null);
    setVisualAnalysis(null);
    setExtractionMethod("llm");
    setRetrievalQuery("");
  };

  const openNewFieldDialog = () => {
    setEditingSchemaFieldName(null);
    setNewFieldName("");
    setNewFieldType("string");
    setNewFieldDescription("");
    setNewFieldPrompt("");
    setNewFieldArrayItemType("string");
    setNewFieldObjectProperties([]);
    setAiFieldInput("");
    setAiScreenshot(null);
    setVisualAnalysis(null);
    setIsAddingField(true);
  };

  const openFieldEditDialog = (field: SchemaField) => {
    const activePrompts = activeFieldPromptsData?.field_prompts || {};
    const prompt =
      activePrompts[field.name] ||
      field.extraction_prompt ||
      `Extract the ${field.name.replace(/_/g, " ")} from the document.`;
    setEditingSchemaFieldName(field.name);
    setNewFieldName(field.name);
    setNewFieldType(field.type);
    setNewFieldDescription(field.description || "");
    setNewFieldPrompt(prompt);
    setAiFieldInput("");
    setAiScreenshot(null);
    setVisualAnalysis(null);
    setExtractionMethod((field.extraction_method as ExtractionMethod) || "llm");
    setRetrievalQuery(field.retrieval_query || "");

    if (field.type === "object" && field.properties) {
      setNewFieldObjectProperties(
        schemaPropertiesToNestedProperties(field.properties),
      );
      setNewFieldArrayItemType("string");
    } else if (field.type === "array") {
      if (field.items?.type === "object" && field.items.properties) {
        setNewFieldArrayItemType("object");
        setNewFieldObjectProperties(
          schemaPropertiesToNestedProperties(field.items.properties),
        );
      } else {
        setNewFieldArrayItemType((field.items?.type || "string") as FieldType);
        setNewFieldObjectProperties([]);
      }
    } else {
      setNewFieldArrayItemType("string");
      setNewFieldObjectProperties([]);
    }

    setIsAddingField(true);
  };

  // Add field to schema
  const addField = () => {
    if (!selectedTypeId || !selectedType || !newFieldName.trim()) return;
    const normalizedFieldName = newFieldName
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "_");
    const hasDuplicateName = (selectedType.schema_fields || []).some(
      (field) =>
        field.name === normalizedFieldName &&
        (!editingSchemaFieldName || field.name !== editingSchemaFieldName),
    );
    if (hasDuplicateName) {
      toast({
        title: "Duplicate field name",
        description: `Field "${normalizedFieldName}" already exists in this schema.`,
        variant: "destructive",
      });
      return;
    }

    const isRetrievalTable =
      newFieldType === "array" && extractionMethod === "retrieval_table";

    const newField: SchemaField = {
      name: normalizedFieldName,
      type: newFieldType,
      description: newFieldDescription || undefined,
      extraction_prompt: isRetrievalTable ? undefined : newFieldPrompt.trim() || undefined,
      extraction_method: isRetrievalTable ? "retrieval_table" : undefined,
      retrieval_query: isRetrievalTable ? retrievalQuery.trim() || undefined : undefined,
      visual_content_type: visualAnalysis?.visual_content_type,
      visual_guidance: visualAnalysis?.extraction_guidance,
      visual_features: visualAnalysis?.distinguishing_features,
    };

    if (newFieldType === "object" && newFieldObjectProperties.length > 0) {
      newField.properties = nestedPropertiesToSchemaProperties(
        newFieldObjectProperties,
      );
    }

    if (newFieldType === "array") {
      if (
        newFieldArrayItemType === "object" &&
        newFieldObjectProperties.length > 0
      ) {
        newField.items = {
          name: "item",
          type: "object",
          properties: nestedPropertiesToSchemaProperties(
            newFieldObjectProperties,
          ),
        };
      } else {
        newField.items = {
          name: "item",
          type: newFieldArrayItemType,
        };
      }
    }

    const updatedFields = editingSchemaFieldName
      ? (selectedType.schema_fields || []).map((field) =>
          field.name === editingSchemaFieldName ? newField : field,
        )
      : [...(selectedType.schema_fields || []), newField];

    updateTypeMutation.mutate(
      {
        id: selectedTypeId,
        data: { schema_fields: updatedFields },
      },
      {
        onSuccess: () => {
          resetFieldEditorForm();
        },
      },
    );
  };

  // Remove field from schema
  const removeField = (fieldName: string) => {
    if (!selectedTypeId || !selectedType) return;

    const updatedFields = selectedType.schema_fields.filter(
      (f) => f.name !== fieldName,
    );

    updateTypeMutation.mutate({
      id: selectedTypeId,
      data: { schema_fields: updatedFields },
    });
  };

  // Update field extraction prompt
  const updateFieldPrompt = (fieldName: string, prompt: string) => {
    if (!selectedTypeId || !selectedType) return;

    const updatedFields = selectedType.schema_fields.map((f) =>
      f.name === fieldName ? { ...f, extraction_prompt: prompt } : f,
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
      name: string;
      document_type_id: string;
      field_name: string;
      extraction_prompt: string;
      description?: string;
      is_active?: boolean;
    }) => api.createFieldPromptVersion(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["field-prompt-versions"],
      });
      await queryClient.refetchQueries({
        queryKey: ["field-prompt-versions", "active", selectedTypeId],
      });
      await queryClient.refetchQueries({
        queryKey: ["field-prompt-versions", selectedTypeId, editingField],
      });
      setFieldPromptVersionDescription("");
      toast({ title: "Field prompt version saved" });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to save version",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const updateFieldPromptVersionMutation = useMutation({
    mutationFn: ({
      versionId,
      data,
    }: {
      versionId: string;
      data: { is_active?: boolean };
    }) => api.updateFieldPromptVersion(versionId, data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["field-prompt-versions"],
      });
      await queryClient.refetchQueries({
        queryKey: ["field-prompt-versions", "active", selectedTypeId],
      });
      await queryClient.refetchQueries({
        queryKey: ["field-prompt-versions", selectedTypeId, editingField],
      });
      toast({ title: "Field prompt version updated" });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to update version",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const deleteFieldPromptVersionMutation = useMutation({
    mutationFn: (versionId: string) => api.deleteFieldPromptVersion(versionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["field-prompt-versions"],
      });
      await queryClient.refetchQueries({
        queryKey: ["field-prompt-versions", "active", selectedTypeId],
      });
      await queryClient.refetchQueries({
        queryKey: ["field-prompt-versions", selectedTypeId, editingField],
      });
      setSelectedFieldPromptVersionId(null);
      toast({ title: "Field prompt version deleted" });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to delete version",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Update field properties (for array of objects or object types, supports nested objects)
  const updateFieldProperties = (
    fieldName: string,
    properties: NestedProperty[],
  ) => {
    if (!selectedTypeId || !selectedType) return;

    const updatedFields = selectedType.schema_fields.map((f) => {
      if (f.name === fieldName) {
        if (f.type === "array" && f.items?.type === "object") {
          return {
            ...f,
            items: {
              ...f.items,
              properties: nestedPropertiesToSchemaProperties(properties),
            },
          };
        }
        if (f.type === "object") {
          return {
            ...f,
            properties: nestedPropertiesToSchemaProperties(properties),
          };
        }
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

  const labels = labelsData?.fields || [];
  const activeFieldPrompts = activeFieldPromptsData?.field_prompts || {};
  const activeFieldVersionByName = activeFieldPromptsData?.field_versions || {};
  const activeFieldVersionUpdatedAt =
    activeFieldPromptsData?.field_version_updated_at || {};
  const schemaFieldNames = new Set(
    (selectedType?.schema_fields || []).map((field) => field.name),
  );
  const labelsForSelectedType = selectedTypeId
    ? labels.filter((label: any) => schemaFieldNames.has(label.name))
    : [];

  return (
    <div className="h-full flex flex-col min-h-0">
      <Tabs defaultValue="document-types" className="flex-1 flex flex-col min-h-0">
        <div className="mb-2 shrink-0">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-secondary)]">
            Schema Workspace
          </p>
        </div>
        <TabsList className="mb-4 shrink-0">
          <TabsTrigger value="document-types" className="gap-2 h-9 px-4">
            <Code className="h-4 w-4" />
            Document Types
          </TabsTrigger>
          <TabsTrigger value="labels" className="gap-2 h-9 px-4">
            <Tag className="h-4 w-4" />
            Labels ({labelsForSelectedType.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="document-types" className="flex-1 min-h-0 data-[state=inactive]:hidden">
          <div className="grid grid-cols-1 lg:grid-cols-[220px_minmax(200px,280px)_1fr] gap-4 h-full min-h-0">
            {/* Col 1: Settings rail */}
            <div className="flex flex-col gap-3 overflow-y-auto no-scrollbar min-w-0 min-h-0">
              {/* Document Type */}
              <div className="rounded-lg border bg-[var(--surface-panel)] p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-primary">
                    Document Type
                  </span>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setIsCreating(true)}>
                      <Plus className="h-3.5 w-3.5" />
                    </Button>
                    {selectedType && (
                      <>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          onClick={() => {
                            setEditTypeName(selectedType.name);
                            setEditTypeDescription(selectedType.description || "");
                            setIsEditingType(true);
                          }}
                        >
                          <Edit className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-destructive/70 hover:text-destructive"
                          onClick={() => deleteTypeMutation.mutate(selectedTypeId!)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </>
                    )}
                  </div>
                </div>
                <Select value={selectedTypeId || ""} onValueChange={selectType}>
                  <SelectTrigger className="bg-background">
                    <SelectValue placeholder="Select document type…" />
                  </SelectTrigger>
                  <SelectContent>
                    {typesData?.types.map((type) => (
                      <SelectItem key={type.id} value={type.id}>
                        {type.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedType?.description && (
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {selectedType.description}
                  </p>
                )}
              </div>

              {selectedType ? (
                <>
                  {/* OCR Engine — compact inline row */}
                  <div className="rounded-lg border bg-[var(--surface-panel)] px-4 py-3 flex items-center justify-between gap-3">
                    <span className="text-xs font-medium text-muted-foreground whitespace-nowrap flex items-center gap-1.5">
                      <Settings2 className="h-3.5 w-3.5" /> OCR Engine
                    </span>
                    <Select value={ocrEngine} onValueChange={setOcrEngine}>
                      <SelectTrigger className="h-7 text-xs bg-background w-36">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="native-text">Native Text</SelectItem>
                        <SelectItem value="aws-textract">AWS Textract</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* System Prompt — collapsible */}
                  <Collapsible open={promptOpen} onOpenChange={setPromptOpen} className="rounded-lg border bg-[var(--surface-panel)]">
                    <CollapsibleTrigger className="flex w-full items-center justify-between px-4 py-3 text-xs font-bold uppercase tracking-wider text-primary hover:bg-muted/20 rounded-lg transition-colors">
                      <span className="flex items-center gap-2">
                        <MessageSquare className="h-3.5 w-3.5" /> System Prompt
                        {systemPrompt && (
                          <span className="text-[10px] font-normal normal-case text-muted-foreground">
                            ({systemPrompt.trim().split(/\s+/).length} words)
                          </span>
                        )}
                      </span>
                      <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", promptOpen && "rotate-180")} />
                    </CollapsibleTrigger>
                    <CollapsibleContent className="px-4 pb-4">
                      <Textarea
                        placeholder="Enter system instructions…"
                        className="bg-background text-sm min-h-[120px] border-muted focus-visible:ring-primary mt-1"
                        value={systemPrompt}
                        onChange={(e) => setSystemPrompt(e.target.value)}
                      />
                    </CollapsibleContent>
                  </Collapsible>

                  {/* Post-Processing — collapsible */}
                  <Collapsible open={postProcOpen} onOpenChange={setPostProcOpen} className="rounded-lg border bg-[var(--surface-panel)]">
                    <CollapsibleTrigger className="flex w-full items-center justify-between px-4 py-3 text-xs font-bold uppercase tracking-wider text-primary hover:bg-muted/20 rounded-lg transition-colors">
                      <span className="flex items-center gap-2">
                        <Code className="h-3.5 w-3.5" /> Post-Processing
                        {postProcessing && (
                          <span className="text-[10px] font-normal normal-case text-muted-foreground">set</span>
                        )}
                      </span>
                      <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", postProcOpen && "rotate-180")} />
                    </CollapsibleTrigger>
                    <CollapsibleContent className="px-4 pb-4">
                      <Textarea
                        placeholder="Enter JavaScript/Python for post-processing…"
                        className="bg-background text-sm font-mono min-h-[120px] border-muted focus-visible:ring-primary mt-1"
                        value={postProcessing}
                        onChange={(e) => setPostProcessing(e.target.value)}
                      />
                    </CollapsibleContent>
                  </Collapsible>

                  <Button
                    className="w-full gap-2"
                    onClick={saveSchema}
                    disabled={updateTypeMutation.isPending}
                  >
                    {updateTypeMutation.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Save className="h-3.5 w-3.5" />
                    )}
                    Save Schema
                  </Button>
                </>
              ) : (
                <div className="p-8 text-center text-muted-foreground border border-dashed rounded-lg text-sm">
                  Select or create a document type to begin.
                </div>
              )}
            </div>

            {/* Col 2: Compact field list */}
            <div className="flex flex-col rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-panel)] overflow-hidden min-w-0 min-h-0">
              <div className="px-4 py-3 border-b border-[var(--border-subtle)] flex items-center justify-between shrink-0">
                <span className="text-xs font-bold uppercase tracking-widest text-primary">
                  Fields
                </span>
                {selectedType && (
                  <span className="text-xs text-muted-foreground">
                    {selectedType.schema_fields?.length || 0}
                  </span>
                )}
              </div>

              <div className="flex-1 overflow-y-auto no-scrollbar">
                {!selectedType && (
                  <p className="p-4 text-xs text-muted-foreground text-center">
                    Select a document type first.
                  </p>
                )}
                {selectedType && !selectedType.schema_fields?.length && (
                  <p className="p-4 text-xs text-muted-foreground text-center">
                    No fields yet.
                  </p>
                )}
                {selectedType?.schema_fields?.map((field) => (
                  <button
                    key={field.name}
                    type="button"
                    className={cn(
                      "w-full flex items-center gap-2 px-3 py-2.5 text-left border-b border-[var(--border-subtle)] hover:bg-muted/40 transition-colors group/row",
                      isAddingField && editingSchemaFieldName === field.name
                        ? "bg-primary/5 border-l-2 border-l-primary"
                        : "border-l-2 border-l-transparent",
                    )}
                    onClick={() => openFieldEditDialog(field)}
                  >
                    <GripVertical className="h-4 w-4 text-muted-foreground/25 shrink-0" />
                    <span className="flex-1 font-mono text-sm text-primary min-w-0 break-all leading-snug">
                      {field.name}
                    </span>
                    <Badge
                      variant="outline"
                      className="text-[10px] h-4 px-1.5 font-mono uppercase shrink-0"
                    >
                      {field.type}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 shrink-0 opacity-0 group-hover/row:opacity-100 text-muted-foreground/50 hover:text-destructive transition-opacity"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeField(field.name);
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </button>
                ))}
              </div>

              {selectedType && (
                <div className="p-3 border-t border-[var(--border-subtle)] shrink-0">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full gap-2 border-dashed text-muted-foreground hover:text-primary"
                    onClick={openNewFieldDialog}
                  >
                    <Plus className="h-3.5 w-3.5" /> Add Field
                  </Button>
                </div>
              )}
            </div>

            {/* Col 3: Inline field editor or empty state */}
            {isAddingField ? (
              <div className="flex flex-col rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-panel)] overflow-hidden min-w-0 min-h-0">
                <div className="px-5 py-3.5 border-b border-[var(--border-subtle)] flex items-center justify-between shrink-0">
                  <h3 className="text-sm font-semibold">
                    {editingSchemaFieldName
                      ? `Edit: ${editingSchemaFieldName}`
                      : "Add Field"}
                  </h3>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={resetFieldEditorForm}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>

                <div className="flex-1 overflow-y-auto p-5 space-y-4">
                  <div className="space-y-3 p-3 border rounded-lg bg-muted/20">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <Sparkles className="h-4 w-4 text-primary" />
                      AI Field Assistant
                    </div>
                    <Textarea
                      placeholder="Describe the field you want (e.g., 'capture all claim line items with area, damage, and estimated cost')."
                      value={aiFieldInput}
                      onChange={(e) => setAiFieldInput(e.target.value)}
                      onPaste={(e) => {
                        const items = e.clipboardData?.items;
                        if (!items) return;
                        for (let i = 0; i < items.length; i++) {
                          const item = items[i];
                          if (item.type.startsWith("image/")) {
                            e.preventDefault();
                            const file = item.getAsFile();
                            if (file) {
                              const reader = new FileReader();
                              reader.onload = () => {
                                const base64 = (reader.result as string).split(
                                  ",",
                                )[1];
                                handleScreenshotChange(base64);
                              };
                              reader.readAsDataURL(file);
                            }
                            break;
                          }
                        }
                      }}
                      className="min-h-[80px]"
                    />

                    <div className="flex items-center gap-2">
                      <input
                        type="file"
                        accept="image/*"
                        id="screenshot-upload"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) {
                            const reader = new FileReader();
                            reader.onload = () => {
                              const base64 = (reader.result as string).split(
                                ",",
                              )[1];
                              handleScreenshotChange(base64);
                            };
                            reader.readAsDataURL(file);
                          }
                          e.target.value = "";
                        }}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          document.getElementById("screenshot-upload")?.click()
                        }
                        className="gap-2"
                      >
                        <ImagePlus className="h-4 w-4" />
                        {aiScreenshot ? "Replace Screenshot" : "Add Screenshot"}
                      </Button>
                      {aiScreenshot && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleScreenshotChange(null)}
                          className="gap-2 text-destructive hover:text-destructive"
                        >
                          <X className="h-4 w-4" />
                          Remove
                        </Button>
                      )}
                      <span className="text-xs text-muted-foreground">
                        Or paste a screenshot (Ctrl+V)
                      </span>
                    </div>

                    {aiScreenshot && (
                      <div className="relative border rounded-lg overflow-hidden bg-background">
                        <img
                          src={`data:image/png;base64,${aiScreenshot}`}
                          alt="Screenshot preview"
                          className="max-h-[200px] w-auto mx-auto"
                        />
                        <div className="absolute top-2 left-2 flex items-center gap-1 bg-background/80 rounded px-2 py-1">
                          <Image className="h-3 w-3 text-muted-foreground" />
                          <span className="text-xs text-muted-foreground">
                            Screenshot attached
                          </span>
                        </div>
                        {analyzeImageMutation.isPending && (
                          <div className="absolute inset-0 bg-background/50 flex items-center justify-center">
                            <Loader2 className="h-6 w-6 animate-spin text-primary" />
                            <span className="ml-2 text-sm">
                              Analyzing structure...
                            </span>
                          </div>
                        )}
                      </div>
                    )}

                    {visualAnalysis && (
                      <div className="p-3 border rounded-lg bg-accent/10 space-y-2">
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary" className="text-xs">
                            {visualAnalysis.visual_content_type.toUpperCase()}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            Structure detected
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {visualAnalysis.structure_description}
                        </p>
                        {visualAnalysis.column_headers &&
                          visualAnalysis.column_headers.length > 0 && (
                            <div className="text-xs">
                              <span className="font-medium">Columns: </span>
                              {visualAnalysis.column_headers.join(", ")}
                            </div>
                          )}
                        {visualAnalysis.data_types &&
                          visualAnalysis.data_types.length > 0 && (
                            <div className="flex gap-1 flex-wrap">
                              {visualAnalysis.data_types.map((dt, i) => (
                                <Badge
                                  key={i}
                                  variant="outline"
                                  className="text-[10px]"
                                >
                                  {dt}
                                </Badge>
                              ))}
                            </div>
                          )}
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="mt-2"
                          onClick={() => {
                            setNewFieldPrompt(
                              visualAnalysis.generated_extraction_prompt,
                            );
                            toast({
                              title:
                                "Extraction prompt updated with visual guidance",
                            });
                          }}
                        >
                          Apply Visual Guidance to Prompt
                        </Button>
                      </div>
                    )}

                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => suggestFieldDefinitionMutation.mutate()}
                      disabled={
                        !aiFieldInput.trim() ||
                        suggestFieldDefinitionMutation.isPending
                      }
                    >
                      {suggestFieldDefinitionMutation.isPending && (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      )}
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
                    <Select
                      value={newFieldType}
                      onValueChange={(v) => setNewFieldType(v as FieldType)}
                    >
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

                  {(newFieldType === "object" || newFieldType === "array") && (
                    <div className="space-y-4 p-4 border rounded-lg bg-muted/30">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <Code className="h-4 w-4" />
                        {newFieldType === "object"
                          ? "Object Properties"
                          : "Array Item Configuration"}
                      </div>
                      {newFieldType === "array" && (
                        <div className="space-y-2">
                          <label className="text-sm font-medium">
                            Item Type
                          </label>
                          <Select
                            value={newFieldArrayItemType}
                            onValueChange={(v) =>
                              setNewFieldArrayItemType(v as FieldType)
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="string">String</SelectItem>
                              <SelectItem value="number">Number</SelectItem>
                              <SelectItem value="date">Date</SelectItem>
                              <SelectItem value="boolean">Boolean</SelectItem>
                              <SelectItem value="object">
                                Object (for tables)
                              </SelectItem>
                            </SelectContent>
                          </Select>
                          <p className="text-xs text-muted-foreground">
                            {newFieldArrayItemType === "object"
                              ? "Perfect for extracting table rows with multiple columns"
                              : "Each item will be a simple value"}
                          </p>
                        </div>
                      )}

                      {(newFieldType === "object" ||
                        (newFieldType === "array" &&
                          newFieldArrayItemType === "object")) && (
                        <div className="space-y-3">
                          <label className="text-sm font-medium">
                            Object Properties
                          </label>
                          <p className="text-xs text-muted-foreground">
                            Properties can be nested up to 3 levels deep.
                            Select "Object" as a type to add nested properties.
                          </p>
                          <PropertyEditor
                            properties={newFieldObjectProperties}
                            onChange={setNewFieldObjectProperties}
                            maxDepth={3}
                          />
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
                  {newFieldType === "array" && (
                    <div className="space-y-3 p-3 border rounded-lg bg-muted/20">
                      <label className="text-sm font-medium">
                        Extraction Method
                      </label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setExtractionMethod("llm")}
                          className={`flex-1 rounded-md border px-3 py-2 text-sm text-left transition-colors ${
                            extractionMethod === "llm"
                              ? "border-primary bg-primary/10 text-primary font-medium"
                              : "border-[var(--border-subtle)] text-muted-foreground hover:border-primary/50"
                          }`}
                        >
                          <div className="font-medium">LLM Extraction</div>
                          <div className="text-xs opacity-70 mt-0.5">
                            Schema-driven, uses vision model
                          </div>
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setExtractionMethod("retrieval_table")
                          }
                          className={`flex-1 rounded-md border px-3 py-2 text-sm text-left transition-colors ${
                            extractionMethod === "retrieval_table"
                              ? "border-primary bg-primary/10 text-primary font-medium"
                              : "border-[var(--border-subtle)] text-muted-foreground hover:border-primary/50"
                          }`}
                        >
                          <div className="font-medium">Retrieval Table</div>
                          <div className="text-xs opacity-70 mt-0.5">
                            Deterministic — parses raw chunk
                          </div>
                        </button>
                      </div>
                      {extractionMethod === "retrieval_table" && (
                        <div className="space-y-1.5 pt-1">
                          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                            Retrieval Query
                          </label>
                          <Input
                            placeholder="e.g. financial highlights table"
                            value={retrievalQuery}
                            onChange={(e) =>
                              setRetrievalQuery(e.target.value)
                            }
                            className="text-sm"
                          />
                          <p className="text-xs text-muted-foreground">
                            Used to find the right chunk. Test it in the
                            Extraction tab → Test Retrieval before saving.
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {(newFieldType !== "array" ||
                    extractionMethod === "llm") && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium">
                        Extraction Prompt
                      </label>
                      <Textarea
                        placeholder="Extract this field exactly as it appears in the document."
                        value={newFieldPrompt}
                        onChange={(e) => setNewFieldPrompt(e.target.value)}
                        className="min-h-[120px]"
                      />
                    </div>
                  )}

                  {(newFieldType === "object" ||
                    (newFieldType === "array" &&
                      newFieldArrayItemType === "object")) &&
                    newFieldObjectProperties.length > 0 && (
                      <div className="p-3 bg-muted/50 rounded border text-xs space-y-2">
                        <div className="font-medium">Example Output:</div>
                        <pre className="text-[10px] overflow-x-auto">
                          {newFieldType === "object"
                            ? `{
  "${newFieldName || "field_name"}": {
${generateExampleOutput(newFieldObjectProperties, 2)}
  }
}`
                            : `{
  "${newFieldName || "field_name"}": [
    {
${generateExampleOutput(newFieldObjectProperties, 3)}
    }
  ]
}`}
                        </pre>
                      </div>
                    )}
                </div>

                <div className="px-5 py-4 border-t border-[var(--border-subtle)] flex justify-end gap-2 shrink-0">
                  <Button variant="outline" onClick={resetFieldEditorForm}>
                    Cancel
                  </Button>
                  <Button
                    onClick={addField}
                    disabled={
                      !newFieldName.trim() ||
                      updateTypeMutation.isPending ||
                      (newFieldType === "object" &&
                        newFieldObjectProperties.length === 0) ||
                      (newFieldType === "array" &&
                        newFieldArrayItemType === "object" &&
                        newFieldObjectProperties.length === 0)
                    }
                  >
                    {updateTypeMutation.isPending && (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    )}
                    {editingSchemaFieldName ? "Save Field" : "Add Field"}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center gap-3 text-muted-foreground border border-dashed border-[var(--border-subtle)] rounded-xl">
                <Edit3 className="h-8 w-8 opacity-20" />
                <span className="text-sm">
                  {selectedType
                    ? "Select a field to edit"
                    : "Select a document type first"}
                </span>
                {selectedType && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-1 gap-2"
                    onClick={openNewFieldDialog}
                  >
                    <Plus className="h-3.5 w-3.5" /> Add Field
                  </Button>
                )}
              </div>
            )}

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
                      This description will be used by the AI when classifying
                      documents.
                    </p>
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setIsCreating(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={() =>
                      createTypeMutation.mutate({
                        name: newTypeName,
                        description: newTypeDescription || undefined,
                      })
                    }
                    disabled={
                      !newTypeName.trim() || createTypeMutation.isPending
                    }
                  >
                    {createTypeMutation.isPending && (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    )}
                    Create
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

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
                      This description will be used by the AI when classifying
                      documents.
                    </p>
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setIsEditingType(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      if (!selectedTypeId) return;
                      updateTypeMutation.mutate({
                        id: selectedTypeId,
                        data: {
                          name: editTypeName,
                          description: editTypeDescription || undefined,
                        },
                      });
                      setIsEditingType(false);
                    }}
                    disabled={
                      !editTypeName.trim() || updateTypeMutation.isPending
                    }
                  >
                    {updateTypeMutation.isPending && (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    )}
                    Save
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>


            <Dialog
              open={!!editingField}
              onOpenChange={(open) => {
                if (!open) closeEditField();
              }}
            >
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Edit Extraction Prompt</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">
                      Active Version
                    </label>
                    <Select
                      value={selectedFieldPromptVersionId || "none"}
                      onValueChange={(value) => {
                        if (value === "none") {
                          setSelectedFieldPromptVersionId(null);
                          return;
                        }
                        setSelectedFieldPromptVersionId(value);
                        const selectedVersion = (
                          fieldPromptVersionsData?.field_prompt_versions || []
                        ).find(
                          (version: FieldPromptVersion) => version.id === value,
                        );
                        if (selectedVersion) {
                          setEditingPromptText(
                            selectedVersion.extraction_prompt,
                          );
                        }
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue
                          placeholder={
                            fieldPromptVersionsLoading
                              ? "Loading versions..."
                              : "Select a saved version"
                          }
                        />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Current prompt</SelectItem>
                        {(
                          fieldPromptVersionsData?.field_prompt_versions || []
                        ).map((version: FieldPromptVersion) => (
                          <SelectItem key={version.id} value={version.id}>
                            {version.name}
                            {version.is_active ? " (active)" : ""}
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
                          onClick={() =>
                            deleteFieldPromptVersionMutation.mutate(
                              selectedFieldPromptVersionId,
                            )
                          }
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
                    <label className="text-sm font-medium">
                      Save As New Version
                    </label>
                    <Input
                      placeholder="Description (optional)"
                      value={fieldPromptVersionDescription}
                      onChange={(e) =>
                        setFieldPromptVersionDescription(e.target.value)
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      Version number is automatic: first is 0.0, then 0.1, 0.2,
                      ...
                    </p>
                    <Button
                      variant="outline"
                      onClick={() => {
                        if (
                          !selectedTypeId ||
                          !editingField ||
                          !editingPromptText.trim()
                        ) {
                          return;
                        }
                        createFieldPromptVersionMutation.mutate({
                          name: `${editingField} prompt v${Date.now()}`,
                          document_type_id: selectedTypeId,
                          field_name: editingField,
                          extraction_prompt: editingPromptText,
                          description:
                            fieldPromptVersionDescription.trim() || undefined,
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
                  <Button variant="outline" onClick={closeEditField}>
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      if (editingField) {
                        updateFieldPrompt(editingField, editingPromptText);
                      }
                    }}
                    disabled={
                      updateTypeMutation.isPending || !editingPromptText.trim()
                    }
                  >
                    {updateTypeMutation.isPending && (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    )}
                    Save
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Dialog
              open={!!editingFieldProperties}
              onOpenChange={() => {
                setEditingFieldProperties(null);
                setEditedProperties([]);
              }}
            >
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Edit Object Properties</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div>
                    <label className="text-sm font-medium">
                      Properties for {editingFieldProperties}
                    </label>
                    <p className="text-xs text-muted-foreground mt-1">
                      Properties can be nested up to 3 levels deep. Select
                      "Object" as a type to add nested properties.
                    </p>
                  </div>

                  <PropertyEditor
                    properties={editedProperties}
                    onChange={setEditedProperties}
                    maxDepth={3}
                  />
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setEditingFieldProperties(null);
                      setEditedProperties([]);
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      if (editingFieldProperties) {
                        updateFieldProperties(
                          editingFieldProperties,
                          editedProperties,
                        );
                      }
                    }}
                    disabled={
                      updateTypeMutation.isPending ||
                      editedProperties.some((p) => !p.name.trim())
                    }
                  >
                    {updateTypeMutation.isPending && (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    )}
                    Save
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </TabsContent>

        <TabsContent
          value="labels"
          className="h-[calc(100%-3rem)] overflow-auto"
        >
          <div className="space-y-6">
            <Card className="border-none shadow-none bg-background">
              <CardHeader className="px-0 pt-0">
                <div>
                  <CardTitle className="text-lg text-primary flex items-center gap-2">
                    <Tag className="h-5 w-5" />
                    Annotation Labels
                  </CardTitle>
                  <p className="text-xs text-muted-foreground mt-1">
                    Labels are generated from the selected document type schema
                    fields and cannot be edited independently.
                  </p>
                </div>
              </CardHeader>
              <CardContent className="px-0">
                {!selectedTypeId ? (
                  <div className="p-8 text-center text-muted-foreground border border-dashed rounded-lg">
                    <Tag className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p className="text-sm">
                      Select a document type to view generated labels.
                    </p>
                  </div>
                ) : labelsForSelectedType.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground border border-dashed rounded-lg">
                    <Tag className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p className="text-sm">No labels generated yet.</p>
                    <p className="text-xs mt-2">
                      Add schema fields in the Document Types tab to generate
                      labels.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {labelsForSelectedType.map((label: any) => (
                      <Card
                        key={label.id}
                        className="border hover:shadow-md transition-shadow"
                      >
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
                                <h4 className="font-medium text-sm">
                                  {label.name}
                                </h4>
                                {label.description && (
                                  <p className="text-xs text-muted-foreground">
                                    {label.description}
                                  </p>
                                )}
                                {label.shortcut && (
                                  <Badge
                                    variant="outline"
                                    className="text-[10px] mt-1"
                                  >
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
