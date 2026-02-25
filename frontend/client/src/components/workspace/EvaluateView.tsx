/**
 * EvaluateView - Compare ground truth vs predicted values
 */

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type EvaluationRun, type EvaluationSummary, type FieldComparison } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Play, Download, CheckCircle2, XCircle, AlertCircle, TrendingUp, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export function EvaluateView() {
  const queryClient = useQueryClient();
  const [selectedDocument, setSelectedDocument] = useState<string>("");
  const [selectedEvaluation, setSelectedEvaluation] = useState<string | null>(null);
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

  // Fetch evaluation runs
  const { data: evaluationsData } = useQuery({
    queryKey: ["evaluations", projectId],
    queryFn: () => api.listEvaluations(projectId !== "all" ? projectId : undefined),
    enabled: !!projectId,
  });

  // Fetch evaluation summary
  const { data: summaryData } = useQuery({
    queryKey: ["evaluation-summary", projectId],
    queryFn: () => api.getEvaluationSummary(projectId !== "all" ? projectId : undefined),
    enabled: !!projectId,
  });

  // Fetch selected evaluation details
  const { data: selectedEvaluationData } = useQuery({
    queryKey: ["evaluation-details", selectedEvaluation],
    queryFn: () => selectedEvaluation ? api.getEvaluationDetails(selectedEvaluation) : Promise.resolve(null),
    enabled: !!selectedEvaluation,
  });

  // Run evaluation mutation
  const runEvaluationMutation = useMutation({
    mutationFn: async (documentId: string) => {
      console.log("Running evaluation for document:", documentId, "project:", projectId);
      return api.runEvaluation(documentId, projectId !== "all" ? projectId : undefined);
    },
    onSuccess: (data) => {
      console.log("Evaluation completed:", data);
      queryClient.invalidateQueries({ queryKey: ["evaluations"] });
      queryClient.invalidateQueries({ queryKey: ["evaluation-summary"] });
      setSelectedEvaluation(data.run.id);
      toast.success("Evaluation completed successfully");
    },
    onError: (error: Error) => {
      console.error("Evaluation error:", error);
      toast.error(`Evaluation failed: ${error.message}`);
    },
  });

  // Delete evaluation mutation
  const deleteEvaluationMutation = useMutation({
    mutationFn: async (evaluationId: string) => {
      return api.deleteEvaluation(evaluationId);
    },
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["evaluations"] });
      queryClient.invalidateQueries({ queryKey: ["evaluation-summary"] });
      if (selectedEvaluation === deletedId) {
        setSelectedEvaluation(null);
      }
      toast.success("Evaluation run deleted");
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete: ${error.message}`);
    },
  });

  const handleDeleteEvaluation = (evaluationId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("Delete this evaluation run?")) {
      deleteEvaluationMutation.mutate(evaluationId);
    }
  };

  const handleRunEvaluation = async () => {
    console.log("handleRunEvaluation called, selectedDocument:", selectedDocument);
    if (!selectedDocument) {
      toast.error("Please select a document");
      return;
    }
    
    // Check if document has ground truth annotations
    try {
      const gtData = await api.getGroundTruthAnnotations(selectedDocument);
      if (!gtData.annotations || gtData.annotations.length === 0) {
        toast.error("This document has no ground truth annotations. Please label it first in the Data Labeller tab.");
        return;
      }
      console.log(`Document has ${gtData.annotations.length} ground truth annotations`);
    } catch (error) {
      console.error("Error checking ground truth:", error);
      toast.error("Failed to check ground truth annotations");
      return;
    }
    
    console.log("Starting evaluation mutation...");
    runEvaluationMutation.mutate(selectedDocument);
  };

  const handleExportCSV = () => {
    if (!selectedEvaluationData) return;

    const evaluation = selectedEvaluationData.run;
    const headers = ["Field Name", "Ground Truth", "Predicted", "Match", "Match Type", "Confidence"];
    const rows = evaluation.result.field_comparisons
      .filter((fc) => {
        const leaf = fc.field_name.split('.').pop() || fc.field_name;
        return !leaf.includes('_header');
      })
      .map(fc => [
        fc.field_name,
        String(fc.ground_truth_value || ""),
        String(fc.predicted_value || ""),
        fc.match_result.is_match ? "✓" : "✗",
        fc.match_result.match_type,
        fc.match_result.confidence.toFixed(2),
      ]);

    const csv = [
      headers.join(","),
      ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `evaluation-${evaluation.id}-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const formatPercentage = (value: number) => `${(value * 100).toFixed(1)}%`;

  const getScoreColor = (score: number) => {
    if (score >= 0.9) return "text-green-600";
    if (score >= 0.7) return "text-yellow-600";
    return "text-red-600";
  };

  const getMatchIcon = (isMatch: boolean) => {
    return isMatch ? (
      <CheckCircle2 className="h-4 w-4 text-green-600" />
    ) : (
      <XCircle className="h-4 w-4 text-red-600" />
    );
  };

  const getMatchTypeBadge = (matchType: string) => {
    const colors = {
      exact: "bg-green-100 text-green-800",
      normalized: "bg-blue-100 text-blue-800",
      fuzzy: "bg-yellow-100 text-yellow-800",
      semantic: "bg-purple-100 text-purple-800",
      no_match: "bg-red-100 text-red-800",
    };
    return (
      <Badge variant="secondary" className={cn("text-xs", colors[matchType as keyof typeof colors] || "")}>
        {matchType}
      </Badge>
    );
  };

  const evaluation = selectedEvaluationData?.run;
  const summary = summaryData;
  const flattenedComparisons = (evaluation?.result.field_comparisons || []).filter((fc) => {
    const leaf = fc.field_name.split('.').pop() || fc.field_name;
    return !leaf.includes('_header');
  });

  return (
    <div className="space-y-6">
      {/* Controls */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Run Evaluation</CardTitle>
              <CardDescription>
                Compare ground truth annotations with extraction results
              </CardDescription>
            </div>
            {evaluation && (
              <Button onClick={handleExportCSV} variant="outline" size="sm">
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <Select value={selectedDocument} onValueChange={setSelectedDocument}>
              <SelectTrigger className="w-[300px]">
                <SelectValue placeholder="Select document to evaluate" />
              </SelectTrigger>
              <SelectContent>
                {documents.length === 0 ? (
                  <div className="p-2 text-sm text-muted-foreground">
                    No documents in this project
                  </div>
                ) : (
                  documents.map(doc => (
                    <SelectItem key={doc.id} value={doc.id}>
                      {doc.filename}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
            <Button 
              onClick={handleRunEvaluation} 
              disabled={!selectedDocument || runEvaluationMutation.isPending}
            >
              <Play className="h-4 w-4 mr-2" />
              {runEvaluationMutation.isPending ? "Running..." : "Run Evaluation"}
            </Button>
          </div>
          
          {documents.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Add documents to your project first to run evaluations
            </p>
          )}

          {/* Recent evaluations selector */}
          {evaluationsData && evaluationsData.runs.length > 0 && (
            <div className="flex gap-4 items-center">
              <span className="text-sm text-muted-foreground">Or view recent:</span>
              <Select value={selectedEvaluation || ""} onValueChange={setSelectedEvaluation}>
                <SelectTrigger className="w-[300px]">
                  <SelectValue placeholder="Select evaluation" />
                </SelectTrigger>
                <SelectContent>
                  {evaluationsData.runs.map(run => (
                    <SelectItem key={run.id} value={run.id}>
                      {run.document_id.slice(0, 8)}... - {new Date(run.evaluated_at).toLocaleString()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedEvaluation && (
                <Button 
                  variant="outline" 
                  size="sm"
                  className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
                  onClick={(e) => handleDeleteEvaluation(selectedEvaluation, e)}
                  disabled={deleteEvaluationMutation.isPending}
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  Delete
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary Metrics */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Accuracy</CardDescription>
              <CardTitle className={cn("text-3xl", getScoreColor(summary.avg_accuracy))}>
                {formatPercentage(summary.avg_accuracy)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">
                {summary.total_evaluations} evaluations
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Precision</CardDescription>
              <CardTitle className={cn("text-3xl", getScoreColor(summary.avg_precision))}>
                {formatPercentage(summary.avg_precision)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">Correct / Extracted</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Recall</CardDescription>
              <CardTitle className={cn("text-3xl", getScoreColor(summary.avg_recall))}>
                {formatPercentage(summary.avg_recall)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">Correct / Present</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>F1 Score</CardDescription>
              <CardTitle className={cn("text-3xl", getScoreColor(summary.avg_f1_score))}>
                {formatPercentage(summary.avg_f1_score)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">Harmonic mean</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Evaluation Results */}
      {evaluation && (
        <Card>
          <CardHeader>
            <CardTitle>Evaluation Results</CardTitle>
            <CardDescription>
              Document: {evaluation.document_id.slice(0, 8)}... | 
              Evaluated: {new Date(evaluation.evaluated_at).toLocaleString()}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="flattened" className="w-full">
              <TabsList>
                <TabsTrigger value="flattened">Flattened View</TabsTrigger>
                <TabsTrigger value="instance">Instance View</TabsTrigger>
                <TabsTrigger value="field">Field Summary</TabsTrigger>
              </TabsList>

              {/* Flattened View */}
              <TabsContent value="flattened" className="space-y-4">
                <div className="grid grid-cols-4 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {evaluation.result.metrics.flattened.correct_fields}
                    </div>
                    <div className="text-xs text-muted-foreground">Correct</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-600">
                      {evaluation.result.metrics.flattened.incorrect_fields}
                    </div>
                    <div className="text-xs text-muted-foreground">Incorrect</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-yellow-600">
                      {evaluation.result.metrics.flattened.missing_fields}
                    </div>
                    <div className="text-xs text-muted-foreground">Missing</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">
                      {evaluation.result.metrics.flattened.extra_fields}
                    </div>
                    <div className="text-xs text-muted-foreground">Extra</div>
                  </div>
                </div>

                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Field</TableHead>
                      <TableHead>Ground Truth</TableHead>
                      <TableHead>Predicted</TableHead>
                      <TableHead>Match</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Confidence</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {flattenedComparisons.map((fc, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-mono text-sm">{fc.field_name}</TableCell>
                        <TableCell className="max-w-[200px] truncate">
                          {String(fc.ground_truth_value || "-")}
                        </TableCell>
                        <TableCell className="max-w-[200px] truncate">
                          {String(fc.predicted_value || "-")}
                        </TableCell>
                        <TableCell>{getMatchIcon(fc.match_result.is_match)}</TableCell>
                        <TableCell>{getMatchTypeBadge(fc.match_result.match_type)}</TableCell>
                        <TableCell>{formatPercentage(fc.match_result.confidence)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TabsContent>

              {/* Instance View */}
              <TabsContent value="instance" className="space-y-4">
                {Object.entries(evaluation.result.instance_comparisons).map(([parentField, instances]) => {
                  const metrics = evaluation.result.metrics.instance_metrics[parentField];
                  
                  // Get all unique field names (columns), excluding headers
                  const allFields = Array.from(
                    new Set(
                      instances.flatMap(inst => 
                        inst.field_comparisons
                          .filter(fc => !fc.field_name.includes('_header'))
                          .map(fc => fc.field_name.split('.').pop() || fc.field_name)
                      )
                    )
                  );
                  
                  // Helper to format field values (especially hierarchy_path arrays)
                  const formatFieldValue = (value: any): string => {
                    if (value === null || value === undefined) return "-";
                    if (Array.isArray(value)) {
                      // For hierarchy_path arrays, show as breadcrumb
                      return value.join(" > ");
                    }
                    return String(value);
                  };
                  
                  return (
                    <div key={parentField} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold">{parentField}</h3>
                        {metrics && (
                          <div className="flex gap-4 text-sm">
                            <span>Match Rate: {formatPercentage(metrics.instance_match_rate)}</span>
                            <span>F1: {formatPercentage(metrics.instance_f1_score)}</span>
                          </div>
                        )}
                      </div>
                      
                      {/* Table format like extraction output */}
                      <div className="border rounded-lg overflow-hidden">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead className="w-12">Row</TableHead>
                              <TableHead className="w-32">Source</TableHead>
                              {allFields.map(field => (
                                <TableHead key={field} className="text-xs">
                                  {field}
                                </TableHead>
                              ))}
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {instances.map((inst) => {
                              // Build a map of field values for this instance
                              const gtValues: Record<string, any> = {};
                              const predValues: Record<string, any> = {};
                              const matchStatus: Record<string, boolean> = {};
                              
                              inst.field_comparisons.forEach(fc => {
                                const fieldKey = fc.field_name.split('.').pop() || fc.field_name;
                                gtValues[fieldKey] = fc.ground_truth_value;
                                predValues[fieldKey] = fc.predicted_value;
                                matchStatus[fieldKey] = fc.match_result.is_match;
                              });
                              
                              return (
                                <>
                                  {/* Ground Truth Row */}
                                  <TableRow key={`${inst.instance_num}-gt`} className="bg-slate-50/70">
                                    <TableCell className="font-semibold text-xs" rowSpan={2}>
                                      {inst.instance_num}
                                    </TableCell>
                                    <TableCell className="text-xs">
                                      <Badge variant="secondary" className="bg-slate-200 text-slate-800">
                                        Ground Truth
                                      </Badge>
                                    </TableCell>
                                    {allFields.map(field => (
                                      <TableCell 
                                        key={field} 
                                        className={cn(
                                          "text-xs",
                                          matchStatus[field] === false && gtValues[field] ? "bg-red-50" : ""
                                        )}
                                      >
                                        {formatFieldValue(gtValues[field])}
                                      </TableCell>
                                    ))}
                                  </TableRow>
                                  {/* Predicted Row */}
                                  <TableRow key={`${inst.instance_num}-pred`} className="bg-emerald-50/70 border-b-2">
                                    <TableCell className="text-xs">
                                      <Badge variant="secondary" className="bg-emerald-200 text-emerald-800">
                                        Prediction
                                      </Badge>
                                    </TableCell>
                                    {allFields.map(field => {
                                      const isMatch = matchStatus[field];
                                      const hasPred = predValues[field] !== null && predValues[field] !== undefined && predValues[field] !== "";
                                      
                                      return (
                                        <TableCell 
                                          key={field} 
                                          className={cn(
                                            "text-xs",
                                            isMatch && hasPred ? "bg-green-50" : "",
                                            !isMatch && hasPred ? "bg-red-50" : ""
                                          )}
                                        >
                                          <div className="flex items-center gap-1">
                                            {formatFieldValue(predValues[field])}
                                            {isMatch && hasPred && <CheckCircle2 className="w-3 h-3 text-green-600" />}
                                            {!isMatch && hasPred && <XCircle className="w-3 h-3 text-red-600" />}
                                          </div>
                                        </TableCell>
                                      );
                                    })}
                                  </TableRow>
                                </>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </div>
                    </div>
                  );
                })}
              </TabsContent>

              {/* Field Summary */}
              <TabsContent value="field" className="space-y-4">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Field Name</TableHead>
                      <TableHead>Occurrences</TableHead>
                      <TableHead>Accuracy</TableHead>
                      <TableHead>Precision</TableHead>
                      <TableHead>Recall</TableHead>
                      <TableHead>Avg Confidence</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Object.values(evaluation.result.metrics.field_metrics).map((fm) => (
                      <TableRow key={fm.field_name}>
                        <TableCell className="font-mono text-sm">{fm.field_name}</TableCell>
                        <TableCell>{fm.total_occurrences}</TableCell>
                        <TableCell className={getScoreColor(fm.accuracy)}>
                          {formatPercentage(fm.accuracy)}
                        </TableCell>
                        <TableCell className={getScoreColor(fm.precision)}>
                          {formatPercentage(fm.precision)}
                        </TableCell>
                        <TableCell className={getScoreColor(fm.recall)}>
                          {formatPercentage(fm.recall)}
                        </TableCell>
                        <TableCell>{formatPercentage(fm.avg_confidence)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {!evaluation && !summary && (
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              Select a document and run an evaluation to see results
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
