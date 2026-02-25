import { Shell } from "@/components/layout/Shell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Plus,
  Search,
  Trash2,
  Edit3,
  BookOpen,
  Sparkles,
  Loader2,
  GripVertical,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { api, type FieldType, type GlobalField } from "@/lib/api";

const DEFAULT_MODEL = "OPENAI_MODEL";
const DEFAULT_OCR = "native-text";

export default function FieldsLibrary() {
  const { toast } = useToast();
  const [fields, setFields] = useState<GlobalField[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isSuggesting, setIsSuggesting] = useState(false);

  const [isCreating, setIsCreating] = useState(false);
  const [editingField, setEditingField] = useState<GlobalField | null>(null);

  const [fieldName, setFieldName] = useState("");
  const [fieldType, setFieldType] = useState<FieldType>("string");
  const [fieldDescription, setFieldDescription] = useState("");
  const [fieldPrompt, setFieldPrompt] = useState("");
  const [ocrEngine, setOcrEngine] = useState(DEFAULT_OCR);
  const [aiFieldInput, setAiFieldInput] = useState("");

  const filteredFields = useMemo(
    () =>
      fields.filter(
        (field) =>
          field.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          field.prompt.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (field.description || "")
            .toLowerCase()
            .includes(searchQuery.toLowerCase()),
      ),
    [fields, searchQuery],
  );

  const resetForm = () => {
    setFieldName("");
    setFieldType("string");
    setFieldDescription("");
    setFieldPrompt("");
    setOcrEngine(DEFAULT_OCR);
    setAiFieldInput("");
  };

  const loadFields = async () => {
    setIsLoading(true);
    try {
      const fieldsResponse = await api.listGlobalFields();
      setFields(fieldsResponse.fields || []);
    } catch (error: any) {
      toast({
        title: "Failed to load fields",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadFields();
  }, []);

  const openCreateDialog = () => {
    resetForm();
    setEditingField(null);
    setIsCreating(true);
  };

  const openEditDialog = (field: GlobalField) => {
    setFieldName(field.name);
    setFieldType(field.type);
    setFieldDescription(field.description || "");
    setFieldPrompt(field.prompt);
    setOcrEngine(field.ocr_engine || DEFAULT_OCR);
    setAiFieldInput("");
    setEditingField(field);
    setIsCreating(true);
  };

  const suggestField = async () => {
    if (!aiFieldInput.trim()) return;
    setIsSuggesting(true);
    try {
      const suggestion = await api.suggestFieldDefinition({
        user_input: aiFieldInput,
        existing_field_names: fields.map((field) => field.name),
      });
      setFieldName(suggestion.name || "");
      setFieldType((suggestion.type as FieldType) || "string");
      setFieldDescription(suggestion.description || "");
      setFieldPrompt(suggestion.extraction_prompt || "");
      toast({
        title: "Field suggestion ready",
        description: "Review and save the generated field.",
      });
    } catch (error: any) {
      toast({
        title: "Failed to suggest field",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setIsSuggesting(false);
    }
  };

  const saveField = async () => {
    const normalizedName = fieldName.trim().toLowerCase().replace(/\s+/g, "_");
    if (!normalizedName) {
      toast({ title: "Field name is required", variant: "destructive" });
      return;
    }

    const isDuplicate = fields.some(
      (field) => field.name === normalizedName && field.id !== editingField?.id,
    );
    if (isDuplicate) {
      toast({ title: "Field name already exists", variant: "destructive" });
      return;
    }

    setIsSaving(true);
    try {
      const payload = {
        name: normalizedName,
        type: fieldType,
        description: fieldDescription.trim() || undefined,
        prompt:
          fieldPrompt.trim() ||
          `Extract the ${normalizedName.replace(/_/g, " ")} from the document.`,
        ocr_engine: ocrEngine,
      };

      if (editingField) {
        const updated = await api.updateGlobalField(editingField.id, payload);
        setFields((prev) =>
          prev.map((field) => (field.id === editingField.id ? updated : field)),
        );
        toast({
          title: "Field updated",
          description: `Updated "${normalizedName}"`,
        });
      } else {
        const created = await api.createGlobalField(payload);
        setFields((prev) => [...prev, created]);
        toast({
          title: "Field created",
          description: `Created "${normalizedName}"`,
        });
      }

      setIsCreating(false);
      setEditingField(null);
      resetForm();
    } catch (error: any) {
      toast({
        title: editingField
          ? "Failed to update field"
          : "Failed to create field",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const deleteField = async (field: GlobalField) => {
    if (!confirm(`Delete global field "${field.name}"?`)) return;
    try {
      await api.deleteGlobalField(field.id);
      setFields((prev) => prev.filter((f) => f.id !== field.id));
      toast({ title: "Field deleted" });
    } catch (error: any) {
      toast({
        title: "Failed to delete field",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  return (
    <Shell>
      <div className="p-8 max-w-7xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center">
              <BookOpen className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-primary">
                Fields Library
              </h1>
              <p className="text-muted-foreground mt-1">
                Create reusable global fields. Projects can use these alongside
                project-specific fields.
              </p>
            </div>
          </div>
          <Button
            className="gap-2 bg-primary hover:bg-primary/90"
            onClick={openCreateDialog}
          >
            <Plus className="h-4 w-4" />
            Add Field
          </Button>
        </div>

        <div className="flex items-center gap-2 mb-2 max-w-md">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search global fields..."
              className="pl-9"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between mb-2 mt-1">
            <div className="space-y-1">
              <h3 className="text-sm font-bold uppercase tracking-widest text-primary">
                Fields Definition
              </h3>
              <p className="text-xs text-muted-foreground">
                {filteredFields.length} fields defined
              </p>
            </div>
            <Button
              size="sm"
              className="gap-2 bg-primary hover:bg-primary/90"
              onClick={openCreateDialog}
            >
              <Plus className="h-4 w-4" /> Add Field
            </Button>
          </div>

          <div className="space-y-4">
            {isLoading && (
              <div className="p-8 text-center text-muted-foreground border border-dashed rounded-lg">
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading fields...
                </span>
              </div>
            )}

            {!isLoading &&
              filteredFields.map((field) => (
                <div
                  key={field.id}
                  className="flex flex-col rounded-lg border bg-card shadow-sm hover:shadow-md hover:border-accent/40 transition-all overflow-hidden group"
                >
                  <div className="flex items-center gap-3 p-3 bg-card border-b">
                    <div className="cursor-grab text-muted-foreground/30 hover:text-muted-foreground">
                      <GripVertical className="h-4 w-4" />
                    </div>
                    <div className="flex-1 flex items-center gap-2 min-w-0">
                      <span className="font-mono text-sm font-medium truncate text-primary">
                        {field.name}
                      </span>
                      <Badge
                        variant="outline"
                        className="text-[10px] h-4 px-1.5 font-mono text-muted-foreground uppercase"
                      >
                        {field.type}
                      </Badge>
                      <Badge
                        variant="secondary"
                        className="text-[10px] h-4 px-1.5 font-mono"
                      >
                        {field.extraction_model || DEFAULT_MODEL}
                      </Badge>
                      <Badge
                        variant="secondary"
                        className="text-[10px] h-4 px-1.5 font-mono"
                      >
                        {field.ocr_engine || DEFAULT_OCR}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-primary hover:bg-primary/5"
                        title="Edit Field"
                        onClick={() => openEditDialog(field)}
                      >
                        <Edit3 className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/5"
                        title="Delete Field"
                        onClick={() => deleteField(field)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>

                  <div className="p-3 bg-background">
                    {field.description && (
                      <p className="text-xs text-muted-foreground mb-2">
                        {field.description}
                      </p>
                    )}
                    <div className="relative">
                      <label className="absolute -top-2 left-2 bg-background px-1 text-[9px] font-bold text-muted-foreground uppercase tracking-wider">
                        Extraction Prompt
                      </label>
                      <Textarea
                        className="min-h-[60px] text-xs resize-none border-muted bg-transparent"
                        value={field.prompt}
                        readOnly
                      />
                    </div>
                  </div>
                </div>
              ))}

            {!isLoading && filteredFields.length === 0 && (
              <div className="p-8 text-center text-muted-foreground border border-dashed rounded-lg">
                <p className="text-sm">
                  {searchQuery
                    ? "No fields match your search."
                    : "No global fields defined yet."}
                </p>
                <p className="text-xs mt-2">
                  Create reusable field templates for all projects.
                </p>
              </div>
            )}

            <Button
              variant="outline"
              className="w-full border-dashed border-muted-foreground/20 text-muted-foreground hover:border-accent hover:text-accent h-12"
              onClick={openCreateDialog}
            >
              <Plus className="h-4 w-4 mr-2" /> Add Another Field
            </Button>
          </div>
        </div>

        <Dialog
          open={isCreating}
          onOpenChange={(open) => {
            setIsCreating(open);
            if (!open) {
              setEditingField(null);
              resetForm();
            }
          }}
        >
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {editingField ? "Edit Field" : "Add Field"}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-3 p-3 border rounded-lg bg-muted/20">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Sparkles className="h-4 w-4 text-primary" />
                  AI Field Assistant
                </div>
                <Textarea
                  placeholder="Describe the field you want (e.g., 'capture policy number exactly as written')."
                  value={aiFieldInput}
                  onChange={(e) => setAiFieldInput(e.target.value)}
                  className="min-h-[80px]"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={suggestField}
                  disabled={!aiFieldInput.trim() || isSuggesting}
                >
                  {isSuggesting && (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  )}
                  Suggest Field with AI
                </Button>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Field Name</label>
                <Input
                  placeholder="e.g., claim_number, policy_number"
                  value={fieldName}
                  onChange={(e) => setFieldName(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Will be converted to lowercase with underscores.
                </p>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Type</label>
                <Select
                  value={fieldType}
                  onValueChange={(v) => setFieldType(v as FieldType)}
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
              <div className="space-y-2">
                <label className="text-sm font-medium">Description</label>
                <Input
                  placeholder="What this field represents..."
                  value={fieldDescription}
                  onChange={(e) => setFieldDescription(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Extraction Prompt</label>
                <Textarea
                  placeholder="Extract this field exactly as it appears in the document."
                  value={fieldPrompt}
                  onChange={(e) => setFieldPrompt(e.target.value)}
                  className="min-h-[100px]"
                />
              </div>
              <div className="rounded-lg border p-3 space-y-3 bg-muted/10">
                <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Extraction Engine Settings
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">OCR Engine</label>
                  <Select value={ocrEngine} onValueChange={setOcrEngine}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="native-text">Native Text</SelectItem>
                      <SelectItem value="aws-textract">AWS Textract</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setIsCreating(false);
                  setEditingField(null);
                  resetForm();
                }}
              >
                Cancel
              </Button>
              <Button
                onClick={saveField}
                disabled={!fieldName.trim() || isSaving}
              >
                {isSaving ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Saving...
                  </span>
                ) : editingField ? (
                  "Save Changes"
                ) : (
                  "Add Field"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Shell>
  );
}
