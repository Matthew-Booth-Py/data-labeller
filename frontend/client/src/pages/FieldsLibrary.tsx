import { Shell } from "@/components/layout/Shell";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Plus, Search, Trash2, Edit2, BookOpen, Sparkles, MoreVertical, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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

export default function FieldsLibrary() {
  const { toast } = useToast();
  const [fields, setFields] = useState<GlobalField[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  
  // Dialog state
  const [isCreating, setIsCreating] = useState(false);
  const [editingField, setEditingField] = useState<GlobalField | null>(null);
  
  // Form state
  const [fieldName, setFieldName] = useState("");
  const [fieldType, setFieldType] = useState<FieldType>("string");
  const [fieldPrompt, setFieldPrompt] = useState("");
  
  const filteredFields = useMemo(() => fields.filter(field =>
    field.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    field.prompt.toLowerCase().includes(searchQuery.toLowerCase())
  ), [fields, searchQuery]);

  const loadFields = async () => {
    setIsLoading(true);
    try {
      const response = await api.listGlobalFields();
      setFields(response.fields || []);
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
  
  // Reset form
  const resetForm = () => {
    setFieldName("");
    setFieldType("string");
    setFieldPrompt("");
  };
  
  // Open create dialog
  const openCreateDialog = () => {
    resetForm();
    setEditingField(null);
    setIsCreating(true);
  };
  
  // Open edit dialog
  const openEditDialog = (field: GlobalField) => {
    setFieldName(field.name);
    setFieldType(field.type);
    setFieldPrompt(field.prompt);
    setEditingField(field);
    setIsCreating(true);
  };
  
  // Save field (create or update)
  const saveField = async () => {
    const name = fieldName.trim().toLowerCase().replace(/\s+/g, '_');
    
    if (!name) {
      toast({ title: "Field name is required", variant: "destructive" });
      return;
    }
    
    // Check for duplicate name (excluding current field if editing)
    const isDuplicate = fields.some(f => 
      f.name === name && f.id !== editingField?.id
    );
    
    if (isDuplicate) {
      toast({ title: "Field name already exists", variant: "destructive" });
      return;
    }
    
    setIsSaving(true);
    try {
      const payload = {
        name,
        type: fieldType,
        prompt: fieldPrompt || `Extract the ${name.replace(/_/g, ' ')} from the document.`,
      };

      if (editingField) {
        const updated = await api.updateGlobalField(editingField.id, payload);
        setFields(prev => prev.map(f => (f.id === editingField.id ? updated : f)));
        toast({ title: "Field updated", description: `Updated "${name}"` });
      } else {
        const created = await api.createGlobalField(payload);
        setFields(prev => [...prev, created]);
        toast({ title: "Field created", description: `Created "${name}"` });
      }

      setIsCreating(false);
      resetForm();
      setEditingField(null);
    } catch (error: any) {
      toast({
        title: editingField ? "Failed to update field" : "Failed to create field",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };
  
  // Delete field
  const deleteField = async (field: GlobalField) => {
    if (confirm(`Delete field "${field.name}"?`)) {
      try {
        await api.deleteGlobalField(field.id);
        setFields(prev => prev.filter(f => f.id !== field.id));
        toast({ title: "Field deleted" });
      } catch (error: any) {
        toast({
          title: "Failed to delete field",
          description: error.message,
          variant: "destructive",
        });
      }
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
              <h1 className="text-2xl font-semibold tracking-tight text-primary">Fields Library</h1>
              <p className="text-muted-foreground mt-1">Manage reusable extraction fields and their optimized prompts.</p>
            </div>
          </div>
          <Button className="gap-2 bg-accent hover:bg-accent/90" onClick={openCreateDialog}>
            <Plus className="h-4 w-4" />
            Create Global Field
          </Button>
        </div>

        <div className="flex items-center gap-2 mb-6 max-w-md">
           <div className="relative flex-1">
             <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input 
              placeholder="Search shared fields..." 
              className="pl-9"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
           </div>
        </div>

        <div className="rounded-md border bg-white">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/5 hover:bg-muted/5">
                <TableHead className="w-[250px]">Field Name</TableHead>
                <TableHead className="w-[100px]">Type</TableHead>
                <TableHead>Optimized Prompt</TableHead>
                <TableHead className="w-[100px] text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading fields...
                    </span>
                  </TableCell>
                </TableRow>
              ) : (
              <>
              {filteredFields.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                    {searchQuery ? "No fields match your search." : "No fields defined yet."}
                  </TableCell>
                </TableRow>
              ) : (
                filteredFields.map((field) => (
                  <TableRow key={field.id} className="group">
                    <TableCell className="font-medium font-mono text-xs">
                      {field.name}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-[10px] font-mono">{field.type}</Badge>
                    </TableCell>
                    <TableCell className="max-w-md truncate text-muted-foreground text-xs italic">
                      "{field.prompt}"
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuLabel>Actions</DropdownMenuLabel>
                          <DropdownMenuItem className="gap-2" onClick={() => openEditDialog(field)}>
                            <Edit2 className="h-4 w-4" /> Edit Field
                          </DropdownMenuItem>
                          <DropdownMenuItem className="gap-2">
                            <Sparkles className="h-4 w-4 text-accent" /> Enhance Prompt
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem className="text-destructive gap-2" onClick={() => deleteField(field)}>
                            <Trash2 className="h-4 w-4" /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
              </>
              )}
            </TableBody>
          </Table>
        </div>
        
        <div className="flex justify-center pt-4">
           <Button 
             variant="outline" 
             className="border-dashed border-muted-foreground/30 text-muted-foreground hover:border-accent hover:text-accent gap-2"
             onClick={openCreateDialog}
           >
              <Plus className="h-4 w-4" /> Add New Field Template
           </Button>
        </div>
        
        {/* Create/Edit Field Dialog */}
        <Dialog open={isCreating} onOpenChange={(open) => {
          setIsCreating(open);
          if (!open) {
            resetForm();
            setEditingField(null);
          }
        }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editingField ? "Edit Field" : "Create Global Field"}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Field Name</label>
                <Input 
                  placeholder="e.g., invoice_number, total_amount, due_date"
                  value={fieldName}
                  onChange={(e) => setFieldName(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Will be converted to lowercase with underscores (e.g., "Invoice Number" → "invoice_number")
                </p>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Field Type</label>
                <Select value={fieldType} onValueChange={(v) => setFieldType(v as FieldType)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="string">String</SelectItem>
                    <SelectItem value="number">Number</SelectItem>
                    <SelectItem value="date">Date</SelectItem>
                    <SelectItem value="boolean">Boolean</SelectItem>
                    <SelectItem value="array">Array</SelectItem>
                    <SelectItem value="object">Object</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Extraction Prompt</label>
                <Textarea 
                  placeholder="Describe what this field should extract from documents..."
                  value={fieldPrompt}
                  onChange={(e) => setFieldPrompt(e.target.value)}
                  className="min-h-[100px]"
                />
                <p className="text-xs text-muted-foreground">
                  This prompt will be used by the LLM to extract this field from documents.
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => {
                setIsCreating(false);
                resetForm();
                setEditingField(null);
              }}>
                Cancel
              </Button>
              <Button onClick={saveField} disabled={!fieldName.trim()}>
                {isSaving ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Saving...
                  </span>
                ) : (
                  editingField ? "Save Changes" : "Create Field"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Shell>
  );
}
