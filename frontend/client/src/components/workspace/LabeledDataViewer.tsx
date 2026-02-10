import { useState, useMemo, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, Annotation, Label, Document } from "@/lib/api";
import {
  Database,
  FileJson,
  TableIcon,
  Download,
  Filter,
  Search,
  Tag,
  FileText,
  Copy,
  Check,
  Trash2,
  Loader2,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface LabeledDataViewerProps {
  projectId?: string;
}

interface AnnotationWithDocument extends Annotation {
  document_name?: string;
}

export function LabeledDataViewer({ projectId }: LabeledDataViewerProps) {
  const [viewMode, setViewMode] = useState<"structured" | "raw">("structured");
  const [filterLabel, setFilterLabel] = useState<string>("all");
  const [filterDocument, setFilterDocument] = useState<string>("all");
  const [searchText, setSearchText] = useState("");
  const [copied, setCopied] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Get document IDs from localStorage for this project
  const projectDocumentIds = useMemo(() => {
    try {
      const stored = localStorage.getItem("uu-projects");
      if (stored) {
        const projects = JSON.parse(stored);
        const project = projects.find((p: { id: string }) => p.id === projectId);
        return project?.documentIds || [];
      }
    } catch {
      // Ignore
    }
    return [];
  }, [projectId]);

  // Fetch labels
  const { data: labelsData } = useQuery({
    queryKey: ["labels"],
    queryFn: () => api.listLabels(),
  });

  // Fetch documents
  const { data: documentsData, isLoading: docsLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
  });

  // Filter documents to this project
  const projectDocuments = useMemo(() => {
    if (!documentsData?.documents) return [];
    if (projectDocumentIds.length === 0) return documentsData.documents;
    return documentsData.documents.filter((d: Document) => 
      projectDocumentIds.includes(d.id)
    );
  }, [documentsData?.documents, projectDocumentIds]);

  // Fetch annotations for all project documents
  const { data: allAnnotations, isLoading: annotationsLoading } = useQuery({
    queryKey: ["all-annotations", projectId, projectDocuments.map((d: Document) => d.id)],
    queryFn: async () => {
      const annotationPromises = projectDocuments.map((doc: Document) =>
        api.listAnnotations(doc.id).then(result => 
          result.annotations.map(ann => ({
            ...ann,
            document_name: doc.name,
          }))
        ).catch(() => [])
      );
      const results = await Promise.all(annotationPromises);
      return results.flat() as AnnotationWithDocument[];
    },
    enabled: projectDocuments.length > 0,
  });

  const labels = labelsData?.labels || [];
  const annotations = allAnnotations || [];

  // Filter annotations
  const filteredAnnotations = useMemo(() => {
    return annotations.filter(ann => {
      if (filterLabel !== "all" && ann.label_id !== filterLabel) return false;
      if (filterDocument !== "all" && ann.document_id !== filterDocument) return false;
      if (searchText && !ann.text?.toLowerCase().includes(searchText.toLowerCase())) return false;
      return true;
    });
  }, [annotations, filterLabel, filterDocument, searchText]);

  // Flatten annotations - each key-value pair is its own row
  const flattenedAnnotations = useMemo(() => {
    return filteredAnnotations.map(ann => ({
      id: ann.id,
      document_id: ann.document_id,
      document_name: ann.document_name,
      label_id: ann.label_id,
      label_name: ann.label_name,
      label_color: ann.label_color,
      key: ann.metadata?.key || '-',
      value: ann.text || '',
      start_offset: ann.start_offset,
      end_offset: ann.end_offset,
      created_at: ann.created_at,
    })).sort((a, b) => {
      // Sort by document, then by position
      if (a.document_id !== b.document_id) return a.document_id.localeCompare(b.document_id);
      return (a.start_offset || 0) - (b.start_offset || 0);
    });
  }, [filteredAnnotations]);

  // Delete mutation
  const deleteAnnotationsMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      // Delete each annotation by its ID
      const deletePromises = ids.map(id => api.deleteAnnotation(id));
      await Promise.all(deletePromises);
      return ids;
    },
    onSuccess: (deletedIds) => {
      // Invalidate annotations queries
      queryClient.invalidateQueries({ queryKey: ["all-annotations"] });
      projectDocuments.forEach((doc: Document) => {
        queryClient.invalidateQueries({ queryKey: ["annotations", doc.id] });
      });
      setSelectedIds(new Set());
      toast({
        title: "Deleted",
        description: `${deletedIds.length} annotation${deletedIds.length > 1 ? 's' : ''} deleted`,
      });
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: "Failed to delete annotations",
        variant: "destructive",
      });
      console.error("Delete error:", error);
    },
  });

  // Selection handlers
  const handleSelectAll = useCallback((checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(filteredAnnotations.map(a => a.id)));
    } else {
      setSelectedIds(new Set());
    }
  }, [filteredAnnotations]);

  const handleSelectOne = useCallback((id: string, checked: boolean) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (checked) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  }, []);

  const handleDeleteSelected = useCallback(() => {
    if (selectedIds.size === 0) return;
    deleteAnnotationsMutation.mutate(Array.from(selectedIds));
  }, [selectedIds, deleteAnnotationsMutation]);

  const allSelected = filteredAnnotations.length > 0 && filteredAnnotations.every(a => selectedIds.has(a.id));
  const someSelected = filteredAnnotations.some(a => selectedIds.has(a.id)) && !allSelected;

  // Group annotations by label for summary
  const labelSummary = useMemo(() => {
    const summary: Record<string, { count: number; label: Label }> = {};
    annotations.forEach(ann => {
      const label = labels.find(l => l.id === ann.label_id);
      if (label) {
        if (!summary[label.id]) {
          summary[label.id] = { count: 0, label };
        }
        summary[label.id].count++;
      }
    });
    return Object.values(summary).sort((a, b) => b.count - a.count);
  }, [annotations, labels]);

  // Generate export data
  const exportData = useMemo(() => {
    return filteredAnnotations.map(ann => ({
      id: ann.id,
      document_id: ann.document_id,
      document_name: ann.document_name,
      label: ann.label_name,
      key: ann.metadata?.key || null,
      type: ann.annotation_type,
      text: ann.text,
      value: ann.metadata?.value || ann.text,
      start_offset: ann.start_offset,
      end_offset: ann.end_offset,
      created_at: ann.created_at,
    }));
  }, [filteredAnnotations]);

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(exportData, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast({ title: "Copied to clipboard" });
  };

  const handleDownloadJson = () => {
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `labeled-data-${projectId || "all"}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast({ title: "Downloaded labeled-data.json" });
  };

  const handleDownloadCsv = () => {
    const headers = ["id", "document_id", "document_name", "label", "key", "type", "text", "value", "start_offset", "end_offset", "created_at"];
    const rows = exportData.map(row => 
      headers.map(h => {
        const val = row[h as keyof typeof row];
        // Escape quotes and wrap in quotes if contains comma
        const str = String(val ?? "");
        if (str.includes(",") || str.includes('"') || str.includes("\n")) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(",")
    );
    const csv = [headers.join(","), ...rows].join("\n");
    
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `labeled-data-${projectId || "all"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast({ title: "Downloaded labeled-data.csv" });
  };

  const isLoading = docsLoading || annotationsLoading;

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Database className="h-4 w-4" />
              Total Annotations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{annotations.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Documents Labeled
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {new Set(annotations.map(a => a.document_id)).size}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Tag className="h-4 w-4" />
              Labels Used
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{labelSummary.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Filtered Results
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{filteredAnnotations.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* Label Distribution */}
      {labelSummary.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Label Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {labelSummary.map(({ label, count }) => (
                <Badge
                  key={label.id}
                  variant="secondary"
                  className="gap-1 cursor-pointer hover:opacity-80"
                  style={{ backgroundColor: label.color, color: "white" }}
                  onClick={() => setFilterLabel(filterLabel === label.id ? "all" : label.id)}
                >
                  {label.name}
                  <span className="ml-1 bg-white/20 px-1.5 rounded text-xs">{count}</span>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters and View Toggle */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search annotations..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={filterLabel} onValueChange={setFilterLabel}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Filter by label" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Labels</SelectItem>
              {labels.map(label => (
                <SelectItem key={label.id} value={label.id}>
                  <div className="flex items-center gap-2">
                    <div 
                      className="w-3 h-3 rounded-full" 
                      style={{ backgroundColor: label.color }}
                    />
                    {label.name}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={filterDocument} onValueChange={setFilterDocument}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Filter by document" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Documents</SelectItem>
              {projectDocuments.map((doc: Document) => (
                <SelectItem key={doc.id} value={doc.id}>
                  {doc.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          {selectedIds.size > 0 && (
            <Button 
              variant="destructive" 
              size="sm" 
              onClick={handleDeleteSelected}
              disabled={deleteAnnotationsMutation.isPending}
              className="gap-2"
            >
              {deleteAnnotationsMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Delete ({selectedIds.size})
            </Button>
          )}
          <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as "structured" | "raw")}>
            <TabsList>
              <TabsTrigger value="structured" className="gap-2">
                <TableIcon className="h-4 w-4" />
                Table
              </TabsTrigger>
              <TabsTrigger value="raw" className="gap-2">
                <FileJson className="h-4 w-4" />
                JSON
              </TabsTrigger>
            </TabsList>
          </Tabs>
          <Button variant="outline" size="sm" onClick={handleDownloadCsv} className="gap-2">
            <Download className="h-4 w-4" />
            CSV
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownloadJson} className="gap-2">
            <Download className="h-4 w-4" />
            JSON
          </Button>
          <Button 
            variant="default" 
            size="sm" 
            onClick={() => window.open(api.getExportAnnotationsUrl('json'), '_blank')}
            className="gap-2"
          >
            <Download className="h-4 w-4" />
            Export All (API)
          </Button>
        </div>
      </div>

      {/* Data View */}
      {viewMode === "structured" ? (
        <Card>
          <CardContent className="p-0">
            <ScrollArea className="h-[500px]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[40px]">
                      <Checkbox
                        checked={allSelected}
                        onCheckedChange={handleSelectAll}
                        aria-label="Select all"
                        className={someSelected ? "opacity-50" : ""}
                      />
                    </TableHead>
                    <TableHead>Document</TableHead>
                    <TableHead>Label</TableHead>
                    <TableHead>Key</TableHead>
                    <TableHead className="w-[35%]">Value</TableHead>
                    <TableHead>Offsets</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {flattenedAnnotations.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                        No annotations found
                      </TableCell>
                    </TableRow>
                  ) : (
                    flattenedAnnotations.map(item => (
                      <TableRow 
                        key={item.id}
                        className={selectedIds.has(item.id) ? "bg-muted/50" : ""}
                      >
                        <TableCell>
                          <Checkbox
                            checked={selectedIds.has(item.id)}
                            onCheckedChange={(checked) => handleSelectOne(item.id, checked as boolean)}
                            aria-label={`Select ${item.key}: ${item.value.slice(0, 20)}`}
                          />
                        </TableCell>
                        <TableCell className="font-medium max-w-[150px] truncate" title={item.document_name}>
                          {item.document_name || item.document_id.slice(0, 8)}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="secondary"
                            style={{ backgroundColor: item.label_color, color: "white" }}
                          >
                            {item.label_name}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-mono text-xs">
                            {item.key}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-[300px]">
                          <span className="line-clamp-2" title={item.value}>
                            {item.value}
                          </span>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {item.start_offset !== undefined && item.end_offset !== undefined
                            ? `${item.start_offset}-${item.end_offset}`
                            : "-"}
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {item.created_at 
                            ? new Date(item.created_at).toLocaleDateString()
                            : "-"}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </ScrollArea>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-medium">Raw JSON Data</CardTitle>
            <Button variant="ghost" size="sm" onClick={handleCopyJson} className="gap-2">
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[500px]">
              <pre className="text-xs font-mono bg-muted p-4 rounded-lg overflow-x-auto">
                {JSON.stringify(exportData, null, 2)}
              </pre>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
