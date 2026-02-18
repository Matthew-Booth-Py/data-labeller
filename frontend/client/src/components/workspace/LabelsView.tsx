/**
 * LabelsView - Display all annotations in a table format
 */

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type GroundTruthAnnotation } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Search, Download, Filter, FileText, Calendar, User } from "lucide-react";
import { cn } from "@/lib/utils";

export function LabelsView() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDocument, setSelectedDocument] = useState<string>("all");
  const [selectedField, setSelectedField] = useState<string>("all");
  const [localStorageVersion, setLocalStorageVersion] = useState(0);

  const projectId = localStorage.getItem("selected-project") || "all";

  // Fetch documents
  const { data: documentsData } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
  });

  const documents = useMemo(() => {
    if (!documentsData?.documents || !projectId || projectId === "all") {
      return [];
    }
    
    try {
      const stored = localStorage.getItem("uu-projects");
      if (!stored) return [];
      
      const projects = JSON.parse(stored);
      const project = projects.find((p: { id: string }) => p.id === projectId);
      if (!project) return [];
      
      const projectDocumentIds = project.documentIds || [];
      return documentsData.documents.filter(doc => projectDocumentIds.includes(doc.id));
    } catch (error) {
      console.error("Error filtering documents:", error);
      return [];
    }
  }, [documentsData, projectId, localStorageVersion]);

  // Fetch all annotations for all documents in the project
  const { data: allAnnotationsData, isLoading } = useQuery({
    queryKey: ["all-annotations", projectId, documents.map(d => d.id)],
    queryFn: async () => {
      if (documents.length === 0) return [];
      
      const results = await Promise.all(
        documents.map(doc => 
          api.getGroundTruthAnnotations(doc.id)
            .then(data => ({
              documentId: doc.id,
              documentName: doc.filename,
              annotations: data.annotations || []
            }))
            .catch(() => ({
              documentId: doc.id,
              documentName: doc.filename,
              annotations: []
            }))
        )
      );
      
      return results;
    },
    enabled: documents.length > 0,
  });

  // Flatten all annotations with document info
  const allAnnotations = useMemo(() => {
    if (!allAnnotationsData) return [];
    
    return allAnnotationsData.flatMap(doc => 
      doc.annotations.map(ann => ({
        ...ann,
        documentId: doc.documentId,
        documentName: doc.documentName,
      }))
    );
  }, [allAnnotationsData]);

  // Get unique field names
  const uniqueFields = useMemo(() => {
    const fields = new Set(allAnnotations.map(ann => ann.field_name));
    return Array.from(fields).sort();
  }, [allAnnotations]);

  // Filter annotations
  const filteredAnnotations = useMemo(() => {
    let filtered = allAnnotations;

    // Filter by document
    if (selectedDocument !== "all") {
      filtered = filtered.filter(ann => ann.documentId === selectedDocument);
    }

    // Filter by field
    if (selectedField !== "all") {
      filtered = filtered.filter(ann => ann.field_name === selectedField);
    }

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(ann => 
        ann.field_name.toLowerCase().includes(query) ||
        (ann.value && String(ann.value).toLowerCase().includes(query)) ||
        ann.documentName.toLowerCase().includes(query)
      );
    }

    return filtered;
  }, [allAnnotations, selectedDocument, selectedField, searchQuery]);

  // Export to CSV
  const handleExportCSV = () => {
    const headers = ["Document", "Field Name", "Value", "Instance #", "Labeled By", "Created At"];
    const rows = filteredAnnotations.map(ann => [
      ann.documentName,
      ann.field_name,
      ann.value || "",
      (ann.annotation_data as any)?.instance_num || "",
      ann.labeled_by || "",
      new Date(ann.created_at).toLocaleString(),
    ]);

    const csv = [
      headers.join(","),
      ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `labels-${projectId}-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Group annotations by document and field for summary stats
  const stats = useMemo(() => {
    const totalAnnotations = allAnnotations.length;
    const totalDocuments = new Set(allAnnotations.map(ann => ann.documentId)).size;
    const totalFields = uniqueFields.length;
    const annotationsByLabeler = allAnnotations.reduce((acc, ann) => {
      const labeler = ann.labeled_by || "unknown";
      acc[labeler] = (acc[labeler] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return {
      totalAnnotations,
      totalDocuments,
      totalFields,
      annotationsByLabeler,
    };
  }, [allAnnotations, uniqueFields]);

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Annotations</CardDescription>
            <CardTitle className="text-3xl">{stats.totalAnnotations}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Documents Labeled</CardDescription>
            <CardTitle className="text-3xl">{stats.totalDocuments}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Unique Fields</CardDescription>
            <CardTitle className="text-3xl">{stats.totalFields}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Manual Labels</CardDescription>
            <CardTitle className="text-3xl">
              {stats.annotationsByLabeler.manual || 0}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Filters and Actions */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>All Labels</CardTitle>
              <CardDescription>
                View and export all annotations across your project
              </CardDescription>
            </div>
            <Button onClick={handleExportCSV} variant="outline" size="sm">
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filters */}
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search annotations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={selectedDocument} onValueChange={setSelectedDocument}>
              <SelectTrigger className="w-[250px]">
                <FileText className="h-4 w-4 mr-2" />
                <SelectValue placeholder="All documents" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All documents</SelectItem>
                {documents.map(doc => (
                  <SelectItem key={doc.id} value={doc.id}>
                    {doc.filename}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedField} onValueChange={setSelectedField}>
              <SelectTrigger className="w-[250px]">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="All fields" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All fields</SelectItem>
                {uniqueFields.map(field => (
                  <SelectItem key={field} value={field}>
                    {field}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Results count */}
          <div className="text-sm text-muted-foreground">
            Showing {filteredAnnotations.length} of {allAnnotations.length} annotations
          </div>

          {/* Table */}
          <div className="border rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Document</TableHead>
                  <TableHead>Field Name</TableHead>
                  <TableHead>Value</TableHead>
                  <TableHead className="w-[100px]">Instance #</TableHead>
                  <TableHead className="w-[120px]">Labeled By</TableHead>
                  <TableHead className="w-[180px]">Created At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                      Loading annotations...
                    </TableCell>
                  </TableRow>
                ) : filteredAnnotations.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                      No annotations found
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredAnnotations.map((ann) => {
                    const instanceNum = (ann.annotation_data as any)?.instance_num;
                    return (
                      <TableRow key={ann.id}>
                        <TableCell className="font-medium max-w-[200px] truncate" title={ann.documentName}>
                          {ann.documentName}
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {ann.field_name}
                        </TableCell>
                        <TableCell className="max-w-[300px]">
                          <div className="truncate" title={String(ann.value || "")}>
                            {ann.value || <span className="text-muted-foreground italic">No value</span>}
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          {instanceNum ? (
                            <Badge variant="secondary" className="text-xs">
                              #{instanceNum}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge 
                            variant={ann.labeled_by === "manual" ? "default" : "secondary"}
                            className="text-xs"
                          >
                            {ann.labeled_by || "unknown"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(ann.created_at).toLocaleString()}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
