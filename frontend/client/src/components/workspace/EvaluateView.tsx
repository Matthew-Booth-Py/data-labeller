/**
 * EvaluateView - Compare ground truth vs predicted values
 */

import { Fragment, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Download,
  FileSpreadsheet,
  ListChecks,
  Loader2,
  Play,
  Sparkles,
  Target,
  Trash2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const MATCH_TYPE_STYLES: Record<string, string> = {
  exact:
    "border-[var(--status-success)]/30 bg-[var(--status-success)]/10 text-[var(--status-success)]",
  normalized:
    "border-[var(--interactive-primary)]/25 bg-[var(--interactive-primary)]/10 text-[var(--interactive-primary)]",
  fuzzy:
    "border-[var(--status-warn)]/30 bg-[var(--status-warn)]/10 text-[var(--status-warn)]",
  semantic:
    "border-[var(--interactive-accent)]/30 bg-[var(--interactive-accent)]/10 text-[var(--interactive-accent)]",
  no_match:
    "border-[var(--status-error)]/30 bg-[var(--status-error)]/10 text-[var(--status-error)]",
};

function formatPercentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function getScoreTextClass(score: number): string {
  if (score >= 0.9) return "text-[var(--status-success)]";
  if (score >= 0.75) return "text-[var(--status-warn)]";
  return "text-[var(--status-error)]";
}

function getScorePillClass(score: number): string {
  if (score >= 0.9) {
    return "border-[var(--status-success)]/30 bg-[var(--status-success)]/10 text-[var(--status-success)]";
  }
  if (score >= 0.75) {
    return "border-[var(--status-warn)]/30 bg-[var(--status-warn)]/10 text-[var(--status-warn)]";
  }
  return "border-[var(--status-error)]/30 bg-[var(--status-error)]/10 text-[var(--status-error)]";
}

function getScoreLabel(score: number): string {
  if (score >= 0.9) return "Strong";
  if (score >= 0.75) return "Stable";
  return "Needs work";
}

function getMatchTypeBadge(matchType: string) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-xs font-medium capitalize border",
        MATCH_TYPE_STYLES[matchType] ||
          "border-[var(--border-strong)] bg-muted/30",
      )}
    >
      {matchType.replace(/_/g, " ")}
    </Badge>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (Array.isArray(value)) return value.join(" > ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected error";
}

export function EvaluateView({ projectId }: { projectId?: string }) {
  const queryClient = useQueryClient();
  const [selectedDocument, setSelectedDocument] = useState<string>("");
  const [selectedEvaluation, setSelectedEvaluation] = useState<string | null>(
    null,
  );
  const [localStorageVersion, setLocalStorageVersion] = useState(0);

  useEffect(() => {
    setLocalStorageVersion((previous) => previous + 1);
  }, [projectId]);

  const {
    data: documentsData,
    isLoading: documentsLoading,
    error: documentsError,
  } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
  });

  const { data: projectData } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId || ""),
    enabled: !!projectId && projectId !== "all",
  });

  const documents = useMemo(() => {
    if (!documentsData?.documents || !projectId || projectId === "all") {
      return [];
    }

    try {
      const projectDocumentIds = projectData?.project?.document_ids || [];
      return documentsData.documents.filter((doc) =>
        projectDocumentIds.includes(doc.id),
      );
    } catch (error) {
      console.error("Error filtering documents:", error);
      return [];
    }
  }, [documentsData, localStorageVersion, projectData, projectId]);

  const documentNameById = useMemo(() => {
    return new Map(documents.map((doc) => [doc.id, doc.filename]));
  }, [documents]);

  const resolveDocumentName = (documentId: string) => {
    return documentNameById.get(documentId) || `${documentId.slice(0, 8)}...`;
  };

  const {
    data: evaluationsData,
    isLoading: evaluationsLoading,
    error: evaluationsError,
  } = useQuery({
    queryKey: ["evaluations", projectId],
    queryFn: () =>
      api.listEvaluations(projectId !== "all" ? projectId : undefined),
    enabled: !!projectId,
  });

  const {
    data: summaryData,
    isLoading: summaryLoading,
    error: summaryError,
  } = useQuery({
    queryKey: ["evaluation-summary", projectId],
    queryFn: () =>
      api.getEvaluationSummary(projectId !== "all" ? projectId : undefined),
    enabled: !!projectId,
  });

  const {
    data: selectedEvaluationData,
    isLoading: selectedEvaluationLoading,
    error: selectedEvaluationError,
  } = useQuery({
    queryKey: ["evaluation-details", selectedEvaluation],
    queryFn: () =>
      selectedEvaluation
        ? api.getEvaluationDetails(selectedEvaluation)
        : Promise.resolve(null),
    enabled: !!selectedEvaluation,
  });

  const runEvaluationMutation = useMutation({
    mutationFn: async (documentId: string) => {
      return api.runEvaluation(
        documentId,
        projectId !== "all" ? projectId : undefined,
      );
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["evaluations"] });
      queryClient.invalidateQueries({ queryKey: ["evaluation-summary"] });
      setSelectedEvaluation(data.run.id);
      toast.success("Evaluation completed successfully");
    },
    onError: (error: Error) => {
      toast.error(`Evaluation failed: ${error.message}`);
    },
  });

  const deleteEvaluationMutation = useMutation({
    mutationFn: async (evaluationId: string) => {
      return api.deleteEvaluation(evaluationId);
    },
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["evaluations"] });
      queryClient.invalidateQueries({ queryKey: ["evaluation-summary"] });

      if (selectedEvaluation === deletedId) {
        const fallbackRun =
          evaluationsData?.runs.find((run) => run.id !== deletedId) || null;
        setSelectedEvaluation(fallbackRun?.id || null);
      }

      toast.success("Evaluation run deleted");
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete: ${error.message}`);
    },
  });

  const handleRunEvaluation = async () => {
    if (!selectedDocument) {
      toast.error("Please select a document");
      return;
    }

    try {
      const gtData = await api.getGroundTruthAnnotations(selectedDocument);
      if (!gtData.annotations || gtData.annotations.length === 0) {
        toast.error(
          "This document has no ground truth annotations. Please label it first in the Data Labeller tab.",
        );
        return;
      }
    } catch {
      toast.error("Failed to check ground truth annotations");
      return;
    }

    runEvaluationMutation.mutate(selectedDocument);
  };

  const handleExportCSV = () => {
    if (!selectedEvaluationData) return;

    const evaluation = selectedEvaluationData.run;
    const headers = [
      "Field Name",
      "Ground Truth",
      "Predicted",
      "Match",
      "Match Type",
      "Confidence",
    ];

    const rows = evaluation.result.field_comparisons
      .filter((comparison) => {
        const leaf =
          comparison.field_name.split(".").pop() || comparison.field_name;
        return !leaf.includes("_header");
      })
      .map((comparison) => [
        comparison.field_name,
        String(comparison.ground_truth_value || ""),
        String(comparison.predicted_value || ""),
        comparison.match_result.is_match ? "✓" : "✗",
        comparison.match_result.match_type,
        comparison.match_result.confidence.toFixed(2),
      ]);

    const csv = [
      headers.join(","),
      ...rows.map((row) =>
        row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","),
      ),
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `evaluation-${evaluation.id}-${new Date().toISOString().split("T")[0]}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const evaluationRuns = evaluationsData?.runs || [];
  const summary = summaryData;
  const evaluation = selectedEvaluationData?.run;

  const selectedRun = useMemo(() => {
    if (!selectedEvaluation) return null;
    return evaluationRuns.find((run) => run.id === selectedEvaluation) || null;
  }, [evaluationRuns, selectedEvaluation]);

  useEffect(() => {
    if (!selectedEvaluation && evaluationRuns.length > 0) {
      setSelectedEvaluation(evaluationRuns[0].id);
    }
  }, [evaluationRuns, selectedEvaluation]);

  const flattenedComparisons = useMemo(() => {
    return (evaluation?.result.field_comparisons || []).filter((comparison) => {
      const leaf =
        comparison.field_name.split(".").pop() || comparison.field_name;
      return !leaf.includes("_header");
    });
  }, [evaluation]);

  const fieldMetrics = useMemo(() => {
    if (!evaluation) return [];

    return Object.values(evaluation.result.metrics.field_metrics).sort(
      (a, b) => a.accuracy - b.accuracy,
    );
  }, [evaluation]);

  // Aggregate sub-field metrics up to the top-level schema field name.
  const schemaFieldMetrics = useMemo(() => {
    if (!evaluation) return [];

    const groups: Record<
      string,
      { correct: number; total: number; incorrect: number; missing: number }
    > = {};

    for (const metric of Object.values(evaluation.result.metrics.field_metrics)) {
      const leaf = metric.field_name.split(".").pop() || metric.field_name;
      if (leaf.includes("_header")) continue;
      const parent = metric.field_name.split(".")[0];
      if (!groups[parent]) groups[parent] = { correct: 0, total: 0, incorrect: 0, missing: 0 };
      groups[parent].correct += metric.correct_predictions;
      groups[parent].total += metric.total_occurrences;
      groups[parent].incorrect += metric.incorrect_predictions;
      groups[parent].missing += metric.missing_predictions;
    }

    return Object.entries(groups)
      .map(([name, g]) => ({
        field_name: name,
        accuracy: g.total > 0 ? g.correct / g.total : 0,
        correct: g.correct,
        total: g.total,
        incorrect: g.incorrect,
        missing: g.missing,
      }))
      .sort((a, b) => a.accuracy - b.accuracy);
  }, [evaluation]);


  const hasTopErrors =
    !!documentsError ||
    !!evaluationsError ||
    !!summaryError ||
    !!selectedEvaluationError;

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden border-primary/20 bg-[var(--surface-panel)]">
        <div className="bg-gradient-to-r from-primary to-[var(--interactive-primary-hover)] px-6 py-6 text-primary-foreground">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <h3 className="text-2xl font-semibold leading-tight text-primary-foreground">
                Evaluate Extraction Performance
              </h3>
              <p className="max-w-2xl text-sm text-primary-foreground/80">
                Compare extraction output against labeled ground truth, inspect
                mismatch patterns, and prioritize schema or prompt improvements.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:min-w-[280px]">
              <div className="rounded-lg border border-white/30 bg-white/10 px-3 py-2">
                <p className="text-[11px] uppercase tracking-wider text-primary-foreground/80">
                  Total Runs
                </p>
                <p className="text-lg font-semibold">
                  {summary?.total_evaluations ?? evaluationRuns.length}
                </p>
              </div>
              <div className="rounded-lg border border-white/30 bg-white/10 px-3 py-2">
                <p className="text-[11px] uppercase tracking-wider text-primary-foreground/80">
                  Avg F1
                </p>
                <p className="text-lg font-semibold">
                  {summary ? formatPercentage(summary.avg_f1_score) : "-"}
                </p>
              </div>
            </div>
          </div>
        </div>

        <CardContent className="space-y-4 pt-5">
          {hasTopErrors && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {documentsError && (
                <p>
                  Failed to load documents: {getErrorMessage(documentsError)}
                </p>
              )}
              {evaluationsError && (
                <p>
                  Failed to load evaluation history:{" "}
                  {getErrorMessage(evaluationsError)}
                </p>
              )}
              {summaryError && (
                <p>
                  Failed to load evaluation summary:{" "}
                  {getErrorMessage(summaryError)}
                </p>
              )}
              {selectedEvaluationError && (
                <p>
                  Failed to load selected run details:{" "}
                  {getErrorMessage(selectedEvaluationError)}
                </p>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_auto_auto] gap-3 items-end">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Document
              </p>
              <Select
                value={selectedDocument}
                onValueChange={setSelectedDocument}
              >
                <SelectTrigger className="w-full h-10">
                  <SelectValue
                    placeholder={
                      documentsLoading
                        ? "Loading project documents..."
                        : "Select document to evaluate"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {documents.length === 0 ? (
                    <div className="px-3 py-2 text-sm text-muted-foreground">
                      No documents found in this project
                    </div>
                  ) : (
                    documents.map((doc) => (
                      <SelectItem key={doc.id} value={doc.id}>
                        {doc.filename}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>

            <Button
              onClick={handleRunEvaluation}
              disabled={!selectedDocument || runEvaluationMutation.isPending}
              className="min-w-[170px]"
            >
              {runEvaluationMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {runEvaluationMutation.isPending
                ? "Running..."
                : "Run Evaluation"}
            </Button>

            <Button
              onClick={handleExportCSV}
              variant="secondary"
              disabled={!evaluation}
              className="min-w-[130px]"
            >
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
          </div>

          <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)]/65 p-4 space-y-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <Clock3 className="h-4 w-4 text-[var(--text-secondary)]" />
                <p className="text-sm font-medium">Recent evaluations</p>
              </div>
              <Badge variant="outline" className="w-fit">
                {evaluationsLoading
                  ? "Loading..."
                  : `${evaluationRuns.length} loaded`}
              </Badge>
            </div>

            {evaluationRuns.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No evaluations yet. Run your first evaluation to populate
                analytics.
              </p>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_auto] gap-3">
                <Select
                  value={selectedEvaluation || ""}
                  onValueChange={setSelectedEvaluation}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select an evaluation run" />
                  </SelectTrigger>
                  <SelectContent>
                    {evaluationRuns.map((run) => (
                      <SelectItem key={run.id} value={run.id}>
                        {resolveDocumentName(run.document_id)} -{" "}
                        {new Date(run.evaluated_at).toLocaleString()}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {selectedEvaluation && (
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        variant="outline"
                        className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>
                          Delete Evaluation Run?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                          This action permanently removes the selected
                          evaluation run and its metrics.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() => {
                            if (selectedEvaluation) {
                              deleteEvaluationMutation.mutate(
                                selectedEvaluation,
                              );
                            }
                          }}
                          disabled={deleteEvaluationMutation.isPending}
                        >
                          {deleteEvaluationMutation.isPending
                            ? "Deleting..."
                            : "Delete Run"}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                )}
              </div>
            )}

            {selectedRun && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-[var(--text-secondary)]">
                <p>
                  <span className="font-medium text-[var(--text-primary)]">
                    Document:
                  </span>{" "}
                  {resolveDocumentName(selectedRun.document_id)}
                </p>
                <p>
                  <span className="font-medium text-[var(--text-primary)]">
                    Evaluated:
                  </span>{" "}
                  {new Date(selectedRun.evaluated_at).toLocaleString()}
                </p>
              </div>
            )}
          </div>

          {documents.length === 0 && !documentsLoading && (
            <p className="text-sm text-muted-foreground">
              Add documents to this project first, then run evaluations.
            </p>
          )}
        </CardContent>
      </Card>

      {summary && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <Card className="border-[var(--border-subtle)]">
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-2">
                  <Target className="h-4 w-4" />
                  Accuracy
                </CardDescription>
                <CardTitle
                  className={cn(
                    "text-3xl",
                    getScoreTextClass(summary.avg_accuracy),
                  )}
                >
                  {formatPercentage(summary.avg_accuracy)}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <Badge
                  variant="outline"
                  className={cn(
                    "border",
                    getScorePillClass(summary.avg_accuracy),
                  )}
                >
                  {getScoreLabel(summary.avg_accuracy)}
                </Badge>
              </CardContent>
            </Card>

            <Card className="border-[var(--border-subtle)]">
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  Precision
                </CardDescription>
                <CardTitle
                  className={cn(
                    "text-3xl",
                    getScoreTextClass(summary.avg_precision),
                  )}
                >
                  {formatPercentage(summary.avg_precision)}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0 text-xs text-muted-foreground">
                Correct predictions / total extracted
              </CardContent>
            </Card>

            <Card className="border-[var(--border-subtle)]">
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-2">
                  <ListChecks className="h-4 w-4" />
                  Recall
                </CardDescription>
                <CardTitle
                  className={cn(
                    "text-3xl",
                    getScoreTextClass(summary.avg_recall),
                  )}
                >
                  {formatPercentage(summary.avg_recall)}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0 text-xs text-muted-foreground">
                Correct predictions / fields present in truth
              </CardContent>
            </Card>

            <Card className="border-[var(--border-subtle)]">
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  F1 Score
                </CardDescription>
                <CardTitle
                  className={cn(
                    "text-3xl",
                    getScoreTextClass(summary.avg_f1_score),
                  )}
                >
                  {formatPercentage(summary.avg_f1_score)}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0 text-xs text-muted-foreground">
                Balanced precision-recall harmonic mean
              </CardContent>
            </Card>
          </div>

        </>
      )}

      {selectedEvaluationLoading && (
        <Card>
          <CardContent className="py-8">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading selected evaluation details...
            </div>
          </CardContent>
        </Card>
      )}

      {evaluation && (
        <Card>
          <CardHeader className="border-b border-[var(--border-subtle)]">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4" />
                  Evaluation Results
                </CardTitle>
                <CardDescription>
                  {resolveDocumentName(evaluation.document_id)} - evaluated on{" "}
                  {new Date(evaluation.evaluated_at).toLocaleString()}
                </CardDescription>
              </div>
              <Badge variant="outline" className="w-fit font-mono text-[11px]">
                {evaluation.id}
              </Badge>
            </div>
          </CardHeader>

          <CardContent className="pt-6">
            <Tabs defaultValue="field" className="w-full">
              <TabsList className="w-full justify-start overflow-x-auto">
                <TabsTrigger value="field" className="gap-2">
                  <Target className="h-4 w-4" />
                  Field Summary
                </TabsTrigger>
                <TabsTrigger value="instance" className="gap-2">
                  <ListChecks className="h-4 w-4" />
                  Instance
                </TabsTrigger>
                <TabsTrigger value="flattened" className="gap-2">
                  <BarChart3 className="h-4 w-4" />
                  Flattened
                </TabsTrigger>
              </TabsList>

              <TabsContent value="flattened" className="space-y-4">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  <div className="rounded-lg border border-[var(--status-success)]/30 bg-[var(--status-success)]/10 px-4 py-3 text-center">
                    <p className="text-2xl font-semibold text-[var(--status-success)]">
                      {evaluation.result.metrics.flattened.correct_fields}
                    </p>
                    <p className="text-xs uppercase tracking-wide text-[var(--status-success)]">
                      Correct
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--status-error)]/30 bg-[var(--status-error)]/10 px-4 py-3 text-center">
                    <p className="text-2xl font-semibold text-[var(--status-error)]">
                      {evaluation.result.metrics.flattened.incorrect_fields}
                    </p>
                    <p className="text-xs uppercase tracking-wide text-[var(--status-error)]">
                      Incorrect
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--status-warn)]/30 bg-[var(--status-warn)]/10 px-4 py-3 text-center">
                    <p className="text-2xl font-semibold text-[var(--status-warn)]">
                      {evaluation.result.metrics.flattened.missing_fields}
                    </p>
                    <p className="text-xs uppercase tracking-wide text-[var(--status-warn)]">
                      Missing
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--interactive-primary)]/30 bg-[var(--interactive-primary)]/10 px-4 py-3 text-center">
                    <p className="text-2xl font-semibold text-[var(--interactive-primary)]">
                      {evaluation.result.metrics.flattened.extra_fields}
                    </p>
                    <p className="text-xs uppercase tracking-wide text-[var(--interactive-primary)]">
                      Extra
                    </p>
                  </div>
                </div>

                <div className="rounded-xl border border-[var(--border-subtle)] overflow-hidden">
                  <Table>
                    <TableHeader sticky>
                      <TableRow className="bg-[var(--surface-elevated)]/70 hover:bg-[var(--surface-elevated)]/70">
                        <TableHead className="w-[220px]">Field</TableHead>
                        <TableHead>Ground Truth</TableHead>
                        <TableHead>Predicted</TableHead>
                        <TableHead className="w-[90px]">Match</TableHead>
                        <TableHead className="w-[130px]">Type</TableHead>
                        <TableHead className="w-[110px]">Confidence</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {flattenedComparisons.length === 0 ? (
                        <TableRow>
                          <TableCell
                            colSpan={6}
                            className="py-10 text-center text-muted-foreground"
                          >
                            No flattened field comparisons for this run.
                          </TableCell>
                        </TableRow>
                      ) : (
                        flattenedComparisons.map((comparison, index) => (
                          <TableRow key={`${comparison.field_name}-${index}`}>
                            <TableCell className="font-mono text-xs text-[var(--text-primary)] break-all">
                              {comparison.field_name}
                            </TableCell>
                            <TableCell
                              className="max-w-[260px] truncate"
                              title={formatValue(comparison.ground_truth_value)}
                            >
                              {formatValue(comparison.ground_truth_value)}
                            </TableCell>
                            <TableCell
                              className="max-w-[260px] truncate"
                              title={formatValue(comparison.predicted_value)}
                            >
                              {formatValue(comparison.predicted_value)}
                            </TableCell>
                            <TableCell>
                              {comparison.match_result.is_match ? (
                                <CheckCircle2 className="h-4 w-4 text-[var(--status-success)]" />
                              ) : (
                                <XCircle className="h-4 w-4 text-[var(--status-error)]" />
                              )}
                            </TableCell>
                            <TableCell>
                              {getMatchTypeBadge(
                                comparison.match_result.match_type,
                              )}
                            </TableCell>
                            <TableCell
                              className={cn(
                                "font-medium",
                                getScoreTextClass(
                                  comparison.match_result.confidence,
                                ),
                              )}
                            >
                              {formatPercentage(
                                comparison.match_result.confidence,
                              )}
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>

              <TabsContent value="instance" className="space-y-4">
                {Object.entries(evaluation.result.instance_comparisons)
                  .length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[var(--border-strong)] px-6 py-10 text-center text-sm text-muted-foreground">
                    No instance-level comparisons were generated for this run.
                  </div>
                ) : (
                  Object.entries(evaluation.result.instance_comparisons).map(
                    ([parentField, instances]) => {
                      const metrics =
                        evaluation.result.metrics.instance_metrics[parentField];

                      const allFields = Array.from(
                        new Set(
                          instances.flatMap((instance) =>
                            instance.field_comparisons
                              .filter(
                                (comparison) =>
                                  !comparison.field_name.includes("_header"),
                              )
                              .map(
                                (comparison) =>
                                  comparison.field_name.split(".").pop() ||
                                  comparison.field_name,
                              ),
                          ),
                        ),
                      );

                      return (
                        <div
                          key={parentField}
                          className="rounded-xl border border-[var(--border-subtle)] overflow-hidden"
                        >
                          <div className="border-b border-[var(--border-subtle)] bg-[var(--surface-elevated)]/70 px-4 py-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                            <h4 className="font-semibold text-[var(--text-primary)]">
                              {parentField}
                            </h4>
                            {metrics && (
                              <div className="flex items-center gap-4 text-xs text-[var(--text-secondary)]">
                                <span>
                                  Match Rate{" "}
                                  <strong
                                    className={getScoreTextClass(
                                      metrics.instance_match_rate,
                                    )}
                                  >
                                    {formatPercentage(
                                      metrics.instance_match_rate,
                                    )}
                                  </strong>
                                </span>
                                <span>
                                  F1{" "}
                                  <strong
                                    className={getScoreTextClass(
                                      metrics.instance_f1_score,
                                    )}
                                  >
                                    {formatPercentage(
                                      metrics.instance_f1_score,
                                    )}
                                  </strong>
                                </span>
                              </div>
                            )}
                          </div>

                          <Table>
                            <TableHeader sticky>
                              <TableRow className="bg-background hover:bg-background">
                                <TableHead className="w-16">Row</TableHead>
                                <TableHead className="w-32">Source</TableHead>
                                {allFields.map((field) => (
                                  <TableHead key={field}>{field}</TableHead>
                                ))}
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {instances.map((instance) => {
                                const gtValues: Record<string, unknown> = {};
                                const predValues: Record<string, unknown> = {};
                                const matchStatus: Record<string, boolean> = {};

                                instance.field_comparisons.forEach(
                                  (comparison) => {
                                    const fieldKey =
                                      comparison.field_name.split(".").pop() ||
                                      comparison.field_name;

                                    gtValues[fieldKey] =
                                      comparison.ground_truth_value;
                                    predValues[fieldKey] =
                                      comparison.predicted_value;
                                    matchStatus[fieldKey] =
                                      comparison.match_result.is_match;
                                  },
                                );

                                return (
                                  <Fragment
                                    key={`${parentField}-${instance.instance_num}`}
                                  >
                                    <TableRow className="bg-[var(--surface-elevated)]/40 hover:bg-[var(--surface-elevated)]/45">
                                      <TableCell
                                        rowSpan={2}
                                        className="font-semibold text-xs text-center"
                                      >
                                        {instance.instance_num}
                                      </TableCell>
                                      <TableCell className="text-xs">
                                        <Badge
                                          variant="outline"
                                          className="text-[10px]"
                                        >
                                          Ground Truth
                                        </Badge>
                                      </TableCell>
                                      {allFields.map((field) => (
                                        <TableCell
                                          key={`gt-${instance.instance_num}-${field}`}
                                            className={cn(
                                              "text-xs",
                                              matchStatus[field] === false &&
                                              gtValues[field]
                                                ? "bg-[var(--status-error)]/10"
                                                : "",
                                            )}
                                          >
                                          {formatValue(gtValues[field])}
                                        </TableCell>
                                      ))}
                                    </TableRow>

                                    <TableRow className="border-b-2 border-b-[var(--border-subtle)] bg-[var(--interactive-primary)]/10 hover:bg-[var(--interactive-primary)]/12">
                                      <TableCell className="text-xs">
                                        <Badge
                                          variant="outline"
                                          className="text-[10px] border-[var(--interactive-primary)]/35 text-[var(--interactive-primary)] bg-[var(--interactive-primary)]/10"
                                        >
                                          Prediction
                                        </Badge>
                                      </TableCell>
                                      {allFields.map((field) => {
                                        const isMatch = matchStatus[field];
                                        const hasPrediction =
                                          predValues[field] !== null &&
                                          predValues[field] !== undefined &&
                                          predValues[field] !== "";

                                        return (
                                          <TableCell
                                            key={`pred-${instance.instance_num}-${field}`}
                                            className={cn(
                                              "text-xs",
                                              isMatch && hasPrediction
                                                ? "bg-[var(--status-success)]/12"
                                                : "",
                                              !isMatch && hasPrediction
                                                ? "bg-[var(--status-error)]/10"
                                                : "",
                                            )}
                                          >
                                            <div className="flex items-center gap-1">
                                              <span>
                                                {formatValue(predValues[field])}
                                              </span>
                                              {isMatch && hasPrediction && (
                                                <CheckCircle2 className="h-3.5 w-3.5 text-[var(--status-success)]" />
                                              )}
                                              {!isMatch && hasPrediction && (
                                                <XCircle className="h-3.5 w-3.5 text-[var(--status-error)]" />
                                              )}
                                            </div>
                                          </TableCell>
                                        );
                                      })}
                                    </TableRow>
                                  </Fragment>
                                );
                              })}
                            </TableBody>
                          </Table>
                        </div>
                      );
                    },
                  )
                )}
              </TabsContent>

              <TabsContent value="field" className="space-y-4">
                <div className="rounded-xl border border-[var(--border-subtle)] overflow-hidden">
                  <Table>
                    <TableHeader sticky>
                      <TableRow className="bg-[var(--surface-elevated)]/70 hover:bg-[var(--surface-elevated)]/70">
                        <TableHead>Schema Field</TableHead>
                        <TableHead className="w-[130px]">Correct</TableHead>
                        <TableHead className="w-[130px]">Incorrect</TableHead>
                        <TableHead className="w-[130px]">Missing</TableHead>
                        <TableHead className="w-[130px]">Accuracy</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {schemaFieldMetrics.length === 0 ? (
                        <TableRow>
                          <TableCell
                            colSpan={5}
                            className="py-10 text-center text-muted-foreground"
                          >
                            No field metrics available for this run.
                          </TableCell>
                        </TableRow>
                      ) : (
                        schemaFieldMetrics.map((metric) => (
                          <TableRow key={metric.field_name}>
                            <TableCell className="font-mono text-sm text-[var(--text-primary)]">
                              {metric.field_name}
                            </TableCell>
                            <TableCell className="text-[var(--status-success)] font-medium">
                              {metric.correct}
                            </TableCell>
                            <TableCell className="text-[var(--status-error)] font-medium">
                              {metric.incorrect}
                            </TableCell>
                            <TableCell className="text-[var(--status-warn)] font-medium">
                              {metric.missing}
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Progress
                                  value={metric.accuracy * 100}
                                  className="h-1.5 w-16 bg-muted/70"
                                />
                                <span
                                  className={cn(
                                    "font-medium text-sm",
                                    getScoreTextClass(metric.accuracy),
                                  )}
                                >
                                  {formatPercentage(metric.accuracy)}
                                </span>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}

      {!evaluation && !selectedEvaluationLoading && (
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="mx-auto h-10 w-10 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground">
              Run an evaluation or select a recent run to inspect results.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
