import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip, Legend, Line, LineChart, CartesianGrid } from "recharts";
import { Play, TrendingUp, AlertCircle, Check, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";

interface FieldEvaluation {
  field_name: string;
  extracted_value: any;
  ground_truth_value: any;
  is_correct: boolean;
  is_present: boolean;
  is_extracted: boolean;
  r2_score?: number;
  comparison_score?: number;
}

interface Evaluation {
  id: string;
  document_id: string;
  document_type_id: string;
  prompt_version_id: string | null;
  prompt_version_name: string | null;
  notes?: string | null;
  field_prompt_versions?: Record<string, string>;
  metrics: {
    f1_score: number;
    accuracy: number;
    precision: number;
    recall: number;
    correct_fields: number;
    incorrect_fields: number;
    field_evaluations?: FieldEvaluation[];
  };
  extraction_time_ms: number;
  evaluated_at: string;
}

interface AggregatedRun {
  runKey: string;
  promptVersionName: string;
  evaluatedAt: string;
  documentCount: number;
  accuracy: number;
  recall: number;
  f1Score: number;
  latencyMs: number;
  correctFields: number;
  incorrectFields: number;
  evaluations: Evaluation[];
}

interface PromptVersion {
  id: string;
  name: string;
  is_active: boolean;
}

interface EvaluationBoardProps {
  projectId?: string;
}

export function EvaluationBoard({ projectId }: EvaluationBoardProps) {
  const { toast } = useToast();
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [loading, setLoading] = useState(true);
  const [showRunDialog, setShowRunDialog] = useState(false);
  const [runningEval, setRunningEval] = useState(false);
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<string>('');
  const [useStructuredOutput, setUseStructuredOutput] = useState(true);
  const [documentTypeId, setDocumentTypeId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<AggregatedRun | null>(null);
  const [selectedRunDocumentEvaluationId, setSelectedRunDocumentEvaluationId] = useState<string | null>(null);
  const [showDetailsDialog, setShowDetailsDialog] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);
  const [promptVersions, setPromptVersions] = useState<PromptVersion[]>([]);
  const [selectedPromptVersion, setSelectedPromptVersion] = useState<string>("default");
  const [selectedEvaluationIds, setSelectedEvaluationIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadDocuments();
  }, []);

  // Load evaluations after we have the document type ID
  useEffect(() => {
    if (documentTypeId) {
      loadEvaluations();
      loadPromptVersions(documentTypeId);
    }
  }, [documentTypeId]);

  const getApiUrl = () => {
    // In Docker, frontend calls backend directly
    return 'http://localhost:8000';
  };

  const loadEvaluations = async () => {
    if (!documentTypeId) return;
    
    setLoading(true);
    try {
      // Filter evaluations by document type (project)
      const response = await fetch(`${getApiUrl()}/api/v1/evaluation?document_type_id=${documentTypeId}`);
      if (!response.ok) throw new Error('Failed to load evaluations');
      const data = await response.json();
      console.log('Loaded evaluations:', data.evaluations?.length || 0);
      setEvaluations(data.evaluations || []);
      setSelectedEvaluationIds(new Set());
    } catch (error) {
      console.error('Error loading evaluations:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadPromptVersions = async (docTypeId: string) => {
    try {
      const response = await fetch(`${getApiUrl()}/api/v1/evaluation/prompts?document_type_id=${docTypeId}`);
      if (!response.ok) throw new Error("Failed to load prompt versions");
      const data = await response.json();
      setPromptVersions(data.prompt_versions || []);
    } catch (error) {
      console.error("Error loading prompt versions:", error);
      setPromptVersions([]);
    }
  };

  const loadDocuments = async () => {
    try {
      console.log('Loading documents for project:', projectId);
      
      // Get project's document IDs from localStorage (same as DocumentPool)
      let projectDocumentIds: string[] = [];
      try {
        const stored = localStorage.getItem("uu-projects");
        if (stored) {
          const projects = JSON.parse(stored);
          const project = projects.find((p: any) => p.id === projectId);
          projectDocumentIds = project?.documentIds || [];
        }
      } catch {
        projectDocumentIds = [];
      }
      
      console.log('Project document IDs from localStorage:', projectDocumentIds.length);
      
      // Fetch all documents and filter to this project's documents
      const response = await fetch(`${getApiUrl()}/api/v1/documents`);
      if (!response.ok) {
        throw new Error('Failed to load documents');
      }
      const data = await response.json();
      
      // Filter to only documents in this project
      const projectDocs = data.documents.filter((doc: any) => 
        projectDocumentIds.includes(doc.id)
      );
      
      console.log('Filtered to project documents:', projectDocs.length);
      setDocuments(projectDocs);

      // Get document type ID from the first document
      if (projectDocs.length > 0) {
        const classificationResponse = await fetch(
          `${getApiUrl()}/api/v1/documents/${projectDocs[0].id}/classification`
        );
        if (classificationResponse.ok) {
          const classificationData = await classificationResponse.json();
          const docTypeId = classificationData.classification.document_type_id;
          console.log('Document type ID:', docTypeId);
          setDocumentTypeId(docTypeId);
        }
      }
    } catch (error) {
      console.error('Error loading documents:', error);
      toast({
        title: 'Failed to Load Documents',
        description: 'Could not fetch document list. Check console for details.',
        variant: 'destructive',
      });
    }
  };

  const runEvaluation = async () => {
    setRunningEval(true);
    try {
      if (!documentTypeId) {
        throw new Error('Document type not found');
      }

      const runMarker =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

      // Run evaluation on all documents in the project
      const response = await fetch(`${getApiUrl()}/api/v1/evaluation/run-project`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_type_id: documentTypeId,
          prompt_version_id: selectedPromptVersion === "default" ? null : selectedPromptVersion,
          use_structured_output: useStructuredOutput,
          use_llm_refinement: !useStructuredOutput,
          notes: `project_run:${runMarker}`,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Evaluation failed');
      }

      const result = await response.json();
      const avgF1 = result.evaluations.length > 0
        ? (result.evaluations.reduce((sum: number, e: any) => sum + e.metrics.f1_score, 0) / result.evaluations.length * 100).toFixed(1)
        : '0.0';

      toast({
        title: 'Evaluation Complete',
        description: `Evaluated ${result.total} documents. Average F1 Score: ${avgF1}%`,
      });

      setShowRunDialog(false);
      setSelectedDocument('');
      loadEvaluations();
    } catch (error: any) {
      toast({
        title: 'Evaluation Failed',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setRunningEval(false);
    }
  };

  const formatPercentage = (value: number) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const truncateText = (value: unknown, max: number = 100) => {
    const text = String(value ?? "");
    return text.length > max ? `${text.slice(0, max)}...` : text;
  };

  const toPreviewJson = (value: unknown, max: number = 100) => {
    return JSON.stringify(
      value,
      (_key, v) => (typeof v === "string" ? truncateText(v, max) : v),
      2
    );
  };

  const normalizeComparable = (value: unknown): unknown => {
    if (value === null || value === undefined) return null;
    if (typeof value === "number") return Number(value);
    if (typeof value === "string") {
      const trimmed = value.trim();
      const cleaned = trimmed.replace(/\$/g, "").replace(/,/g, "");
      if (/^-?\d+(\.\d+)?$/.test(cleaned)) {
        return Number(cleaned);
      }
      return cleaned.toLowerCase();
    }
    return String(value).toLowerCase();
  };

  const valuesMatch = (a: unknown, b: unknown): boolean => {
    const na = normalizeComparable(a);
    const nb = normalizeComparable(b);
    if (typeof na === "number" && typeof nb === "number") {
      return Math.abs(na - nb) < 1e-9;
    }
    return na === nb;
  };

  const aggregatedRuns: AggregatedRun[] = (() => {
    const groups = new Map<
      string,
      {
        key: string;
        evaluations: Evaluation[];
        latestTimestamp: number;
        versionLabel: string;
      }
    >();

    evaluations.forEach((evaluation) => {
      const notes = evaluation.notes || "";
      const markerMatch = notes.match(/project_run:([A-Za-z0-9-]+)/);
      const marker = markerMatch ? markerMatch[1] : null;
      const evaluatedAt = new Date(evaluation.evaluated_at).getTime();
      const minuteBucket = new Date(evaluation.evaluated_at).toISOString().slice(0, 16);
      const key = marker || `${evaluation.prompt_version_id || "default"}:${minuteBucket}`;

      const current = groups.get(key) || {
        key,
        evaluations: [],
        latestTimestamp: evaluatedAt,
        versionLabel: evaluation.prompt_version_name || "Default",
      };

      current.evaluations.push(evaluation);
      current.latestTimestamp = Math.max(current.latestTimestamp, evaluatedAt);
      if (!current.versionLabel && evaluation.prompt_version_name) {
        current.versionLabel = evaluation.prompt_version_name;
      }
      groups.set(key, current);
    });

    return Array.from(groups.values())
      .sort((a, b) => b.latestTimestamp - a.latestTimestamp)
      .map((group) => {
        const count = group.evaluations.length || 1;
        const accuracy = group.evaluations.reduce((sum, e) => sum + e.metrics.accuracy, 0) / count;
        const recall = group.evaluations.reduce((sum, e) => sum + e.metrics.recall, 0) / count;
        const f1Score = group.evaluations.reduce((sum, e) => sum + e.metrics.f1_score, 0) / count;
        const latencyMs = group.evaluations.reduce((sum, e) => sum + e.extraction_time_ms, 0) / count;
        const correctFields = group.evaluations.reduce((sum, e) => sum + e.metrics.correct_fields, 0);
        const incorrectFields = group.evaluations.reduce((sum, e) => sum + e.metrics.incorrect_fields, 0);
        const newestEvaluation = group.evaluations.reduce((latest, current) =>
          new Date(current.evaluated_at).getTime() > new Date(latest.evaluated_at).getTime() ? current : latest
        , group.evaluations[0]);

        return {
          runKey: group.key,
          promptVersionName: group.versionLabel || "Default",
          evaluatedAt: newestEvaluation?.evaluated_at || new Date(group.latestTimestamp).toISOString(),
          documentCount: group.evaluations.length,
          accuracy,
          recall,
          f1Score,
          latencyMs,
          correctFields,
          incorrectFields,
          evaluations: group.evaluations,
        };
      });
  })();

  // Prepare chart data by aggregate evaluation run (one run click across all docs)
  const chartData = aggregatedRuns
    .slice(0, 5)
    .reverse()
    .map((run, idx) => {
      return {
        promptVersion: `Run ${idx + 1}`,
        versionLabel: run.promptVersionName || "Default",
        docs: run.documentCount,
        accuracy: run.accuracy * 100,
        completeness: run.recall * 100,
        latency: run.latencyMs,
        cost: 0.45,
      };
    });

  const fieldScorecard = (() => {
    const stats = new Map<string, {
      total: number;
      correct: number;
      present: number;
      extracted: number;
      avgScore: number;
      scoreCount: number;
    }>();

    evaluations.forEach((evaluation) => {
      (evaluation.metrics.field_evaluations || []).forEach((field) => {
        const current = stats.get(field.field_name) || {
          total: 0,
          correct: 0,
          present: 0,
          extracted: 0,
          avgScore: 0,
          scoreCount: 0,
        };
        current.total += 1;
        if (field.is_correct) current.correct += 1;
        if (field.is_present) current.present += 1;
        if (field.is_extracted) current.extracted += 1;
        if (typeof field.comparison_score === "number") {
          current.avgScore += field.comparison_score;
          current.scoreCount += 1;
        }
        stats.set(field.field_name, current);
      });
    });

    return Array.from(stats.entries())
      .map(([fieldName, s]) => {
        const accuracy = s.total > 0 ? s.correct / s.total : 0;
        const extractionRate = s.present > 0 ? s.extracted / s.present : 0;
        const avgSimilarity = s.scoreCount > 0 ? s.avgScore / s.scoreCount : 0;
        return {
          fieldName,
          accuracy,
          extractionRate,
          avgSimilarity,
          runs: s.total,
          correct: s.correct,
        };
      })
      .sort((a, b) => b.accuracy - a.accuracy);
  })();

  const componentScorecard = (() => {
    const stats = new Map<string, { total: number; correct: number }>();

    evaluations.forEach((evaluation) => {
      (evaluation.metrics.field_evaluations || []).forEach((field) => {
        const extracted = field.extracted_value;
        const truth = field.ground_truth_value;
        const isArrayObjects =
          Array.isArray(extracted) &&
          Array.isArray(truth) &&
          extracted.length > 0 &&
          truth.length > 0 &&
          typeof extracted[0] === "object" &&
          typeof truth[0] === "object";

        if (!isArrayObjects) return;

        const extractedData = extracted as Record<string, unknown>[];
        const groundTruthData = truth as Record<string, unknown>[];
        const allKeys = new Set<string>();
        [...extractedData, ...groundTruthData].forEach((item) => {
          Object.keys(item).forEach((k) => allKeys.add(k));
        });

        const primaryKeys = ["id", "name", "item", "item_name", "claim_item", "title", "key"];
        const primaryKey = primaryKeys.find((k) => allKeys.has(k)) || Array.from(allKeys)[0];
        if (!primaryKey) return;

        const gtMap = new Map<string, Record<string, unknown>>();
        groundTruthData.forEach((item) => {
          gtMap.set(String(normalizeComparable(item[primaryKey] ?? "")), item);
        });
        const extMap = new Map<string, Record<string, unknown>>();
        extractedData.forEach((item) => {
          extMap.set(String(normalizeComparable(item[primaryKey] ?? "")), item);
        });
        const rowKeys = new Set<string>([...gtMap.keys(), ...extMap.keys()]);

        rowKeys.forEach((rowKey) => {
          const extItem = extMap.get(rowKey) || {};
          const gtItem = gtMap.get(rowKey) || {};
          allKeys.forEach((component) => {
            const key = `${field.field_name}.${component}`;
            const current = stats.get(key) || { total: 0, correct: 0 };
            current.total += 1;
            if (valuesMatch(extItem[component], gtItem[component])) {
              current.correct += 1;
            }
            stats.set(key, current);
          });
        });
      });
    });

    return Array.from(stats.entries())
      .map(([componentName, s]) => ({
        componentName,
        accuracy: s.total > 0 ? s.correct / s.total : 0,
        correct: s.correct,
        total: s.total,
      }))
      .sort((a, b) => b.accuracy - a.accuracy);
  })();

  const fieldVersionScorecard = (() => {
    const stats = new Map<string, {
      fieldName: string;
      version: string;
      total: number;
      correct: number;
      present: number;
      extracted: number;
      avgScore: number;
      scoreCount: number;
    }>();

    evaluations.forEach((evaluation) => {
      const versionMap = evaluation.field_prompt_versions || {};
      (evaluation.metrics.field_evaluations || []).forEach((field) => {
        const version = versionMap[field.field_name] || "0.0";
        const key = `${field.field_name}@@${version}`;
        const current = stats.get(key) || {
          fieldName: field.field_name,
          version,
          total: 0,
          correct: 0,
          present: 0,
          extracted: 0,
          avgScore: 0,
          scoreCount: 0,
        };
        current.total += 1;
        if (field.is_correct) current.correct += 1;
        if (field.is_present) current.present += 1;
        if (field.is_extracted) current.extracted += 1;
        if (typeof field.comparison_score === "number") {
          current.avgScore += field.comparison_score;
          current.scoreCount += 1;
        }
        stats.set(key, current);
      });
    });

    return Array.from(stats.values())
      .map((s) => ({
        fieldName: s.fieldName,
        version: s.version,
        accuracy: s.total > 0 ? s.correct / s.total : 0,
        extractionRate: s.present > 0 ? s.extracted / s.present : 0,
        avgSimilarity: s.scoreCount > 0 ? s.avgScore / s.scoreCount : 0,
        runs: s.total,
        correct: s.correct,
      }))
      .sort((a, b) => {
        if (a.fieldName !== b.fieldName) return a.fieldName.localeCompare(b.fieldName);
        return b.version.localeCompare(a.version, undefined, { numeric: true });
      });
  })();

  const recentEvaluations = aggregatedRuns.slice(0, 10);
  const selectedDocumentEvaluation =
    selectedRun?.evaluations.find((evaluation) => evaluation.id === selectedRunDocumentEvaluationId) || null;
  const allRecentSelected =
    recentEvaluations.length > 0 &&
    recentEvaluations.every((run) => selectedEvaluationIds.has(run.runKey));
  const someRecentSelected =
    recentEvaluations.some((run) => selectedEvaluationIds.has(run.runKey)) && !allRecentSelected;

  const toggleSelectAllRecent = (checked: boolean) => {
    if (checked) {
      setSelectedEvaluationIds(new Set(recentEvaluations.map((run) => run.runKey)));
    } else {
      setSelectedEvaluationIds(new Set());
    }
  };

  const toggleSelectEvaluation = (runKey: string, checked: boolean) => {
    setSelectedEvaluationIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(runKey);
      } else {
        next.delete(runKey);
      }
      return next;
    });
  };

  const deleteSelectedEvaluations = async () => {
    if (selectedEvaluationIds.size === 0) return;
    if (!confirm(`Delete ${selectedEvaluationIds.size} selected aggregated run(s)?`)) return;
    try {
      const selectedRuns = aggregatedRuns.filter((run) => selectedEvaluationIds.has(run.runKey));
      const evaluationIdsToDelete = selectedRuns.flatMap((run) => run.evaluations.map((e) => e.id));
      await Promise.all(evaluationIdsToDelete.map((id) => api.deleteEvaluation(id)));
      toast({
        title: "Runs deleted",
        description: `Deleted ${selectedRuns.length} run(s), ${evaluationIdsToDelete.length} document eval(s)`,
      });
      await loadEvaluations();
    } catch (error: any) {
      toast({
        title: "Failed to delete selected runs",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
           <h3 className="text-lg font-medium">Evaluation History</h3>
           <p className="text-sm text-muted-foreground">Compare model performance across versions.</p>
        </div>
        
        <Dialog open={showRunDialog} onOpenChange={setShowRunDialog}>
          <DialogTrigger asChild>
            <Button className="gap-2 bg-accent hover:bg-accent/90">
              <Play className="h-4 w-4" />
              New Evaluation Run
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Run Project Evaluation</DialogTitle>
              <DialogDescription>
                Evaluate all labeled documents in this project to measure extraction quality
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div className="rounded-lg border p-4 bg-muted/30">
                <p className="text-sm font-medium mb-2">Documents to evaluate:</p>
                <p className="text-2xl font-bold text-primary">{documents.length}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Only documents with annotations will be evaluated
                </p>
              </div>

              <div className="flex items-center justify-between space-x-2">
                <div className="space-y-0.5">
                  <Label>Use Structured Output</Label>
                  <p className="text-sm text-muted-foreground">
                    Recommended for tables and complex schemas
                  </p>
                </div>
                <Switch
                  checked={useStructuredOutput}
                  onCheckedChange={setUseStructuredOutput}
                />
              </div>

              <div className="space-y-2">
                <Label>Prompt Version</Label>
                <Select value={selectedPromptVersion} onValueChange={setSelectedPromptVersion}>
                  <SelectTrigger>
                    <SelectValue placeholder="Use default prompt configuration" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Default (Document Type Prompt)</SelectItem>
                    {promptVersions.map((pv) => (
                      <SelectItem key={pv.id} value={pv.id}>
                        {pv.name}{pv.is_active ? " (Active)" : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Run evaluations against a specific prompt version to compare field-level performance.
                </p>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setShowRunDialog(false)}>
                Cancel
              </Button>
              <Button onClick={runEvaluation} disabled={runningEval}>
                {runningEval ? 'Evaluating...' : 'Run Evaluation'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {loading ? (
        <div className="text-center py-12 text-muted-foreground">
          Loading evaluations...
        </div>
      ) : evaluations.length === 0 ? (
        <Card className="border-muted">
          <CardContent className="pt-6">
            <div className="text-center py-8">
              <AlertCircle className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground mb-4">
                No evaluations yet. Run an evaluation on a labeled document to get started.
              </p>
              <Button onClick={() => setShowRunDialog(true)} className="gap-2">
                <Play className="h-4 w-4" />
                Run Your First Evaluation
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
             {/* Main Scoreboard */}
             <Card className="col-span-1 lg:col-span-2 border-muted bg-card">
                <CardHeader>
                    <CardTitle className="text-primary">Accuracy vs Completeness</CardTitle>
                    <CardDescription>Performance metrics per run</CardDescription>
                </CardHeader>
                <CardContent className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted))" />
                            <XAxis dataKey="promptVersion" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} domain={[0, 100]} />
                            <Tooltip 
                                contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', color: 'hsl(var(--foreground))' }}
                                formatter={(value: number, name: string) => [`${Number(value).toFixed(1)}%`, name]}
                                labelFormatter={(_label, payload) => {
                                  const row = payload?.[0]?.payload;
                                  return `${row?.promptVersion || "Run"} • ${row?.versionLabel || "Default"} • ${row?.docs || 0} docs`;
                                }}
                            />
                            <Legend />
                            <Bar dataKey="accuracy" name="Field Accuracy" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} barSize={40} />
                            <Bar dataKey="completeness" name="Completeness" fill="hsl(var(--chart-2))" radius={[4, 4, 0, 0]} barSize={40} />
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
             </Card>

             <Card className="border-muted bg-card">
                <CardHeader>
                    <CardTitle className="text-primary text-sm uppercase tracking-wider font-bold">Latency (ms)</CardTitle>
                </CardHeader>
                <CardContent className="h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted))" />
                            <XAxis dataKey="promptVersion" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                            <Tooltip
                              formatter={(value: number) => [`${Math.round(Number(value))} ms`, "Latency"]}
                              labelFormatter={(_label, payload) => {
                                const row = payload?.[0]?.payload;
                                return `${row?.promptVersion || "Run"} • ${row?.versionLabel || "Default"} • ${row?.docs || 0} docs`;
                              }}
                            />
                            <Line type="monotone" dataKey="latency" stroke="hsl(var(--chart-3))" strokeWidth={3} dot={{r: 6, fill: 'hsl(var(--chart-3))'}} />
                        </LineChart>
                    </ResponsiveContainer>
                </CardContent>
             </Card>

             <Card className="border-muted bg-card">
                <CardHeader>
                    <CardTitle className="text-primary text-sm uppercase tracking-wider font-bold">Cost Efficiency</CardTitle>
                </CardHeader>
                 <CardContent className="h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted))" />
                            <XAxis dataKey="promptVersion" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                            <Tooltip
                              formatter={(value: number) => [`$${Number(value).toFixed(2)}`, "Cost"]}
                              labelFormatter={(_label, payload) => {
                                const row = payload?.[0]?.payload;
                                return `${row?.promptVersion || "Run"} • ${row?.versionLabel || "Default"} • ${row?.docs || 0} docs`;
                              }}
                            />
                            <Line type="monotone" dataKey="cost" stroke="hsl(var(--chart-5))" strokeWidth={3} dot={{r: 6, fill: 'hsl(var(--chart-5))'}} />
                        </LineChart>
                    </ResponsiveContainer>
                </CardContent>
             </Card>
          </div>

          <Card className="border-muted bg-card">
            <CardHeader>
              <CardTitle className="text-primary">Field Scorecard</CardTitle>
              <CardDescription>
                Independent tracking per field across runs, plus combined metrics above.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {fieldScorecard.length === 0 ? (
                <p className="text-sm text-muted-foreground">No field-level data yet.</p>
              ) : (
                <div className="rounded-md border overflow-hidden">
                  <div className="grid grid-cols-5 p-3 text-[10px] uppercase tracking-wider font-bold text-muted-foreground bg-muted/30">
                    <div>Field</div>
                    <div>Accuracy</div>
                    <div>Extraction Rate</div>
                    <div>Avg Similarity</div>
                    <div>Runs</div>
                  </div>
                  {fieldScorecard.map((row) => (
                    <div key={row.fieldName} className="grid grid-cols-5 p-3 border-t text-sm items-center">
                      <div className="font-mono text-primary">{row.fieldName}</div>
                      <div className="font-mono">{(row.accuracy * 100).toFixed(1)}%</div>
                      <div className="font-mono">{(row.extractionRate * 100).toFixed(1)}%</div>
                      <div className="font-mono">{(row.avgSimilarity * 100).toFixed(1)}%</div>
                      <div className="font-mono">{row.correct}/{row.runs}</div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-muted bg-card">
            <CardHeader>
              <CardTitle className="text-primary">Component Scorecard</CardTitle>
              <CardDescription>
                Sub-component performance (array/object fields) for every run.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {componentScorecard.length === 0 ? (
                <p className="text-sm text-muted-foreground">No component-level data yet.</p>
              ) : (
                <div className="rounded-md border overflow-hidden">
                  <div className="grid grid-cols-3 p-3 text-[10px] uppercase tracking-wider font-bold text-muted-foreground bg-muted/30">
                    <div>Component</div>
                    <div>Accuracy</div>
                    <div>Correct/Total</div>
                  </div>
                  {componentScorecard.map((row) => (
                    <div key={row.componentName} className="grid grid-cols-3 p-3 border-t text-sm items-center">
                      <div className="font-mono text-primary">{row.componentName}</div>
                      <div className="font-mono">{(row.accuracy * 100).toFixed(1)}%</div>
                      <div className="font-mono">{row.correct}/{row.total}</div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-muted bg-card">
            <CardHeader>
              <CardTitle className="text-primary">Field Version Scorecard</CardTitle>
              <CardDescription>
                Score breakdown by exact field prompt version used in each run.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {fieldVersionScorecard.length === 0 ? (
                <p className="text-sm text-muted-foreground">No version-attributed field data yet.</p>
              ) : (
                <div className="rounded-md border overflow-hidden">
                  <div className="grid grid-cols-6 p-3 text-[10px] uppercase tracking-wider font-bold text-muted-foreground bg-muted/30">
                    <div>Field</div>
                    <div>Version</div>
                    <div>Accuracy</div>
                    <div>Extraction Rate</div>
                    <div>Avg Similarity</div>
                    <div>Runs</div>
                  </div>
                  {fieldVersionScorecard.map((row, idx) => (
                    <div key={`${row.fieldName}-${row.version}-${idx}`} className="grid grid-cols-6 p-3 border-t text-sm items-center">
                      <div className="font-mono text-primary">{row.fieldName}</div>
                      <div className="font-mono">{row.version}</div>
                      <div className="font-mono">{(row.accuracy * 100).toFixed(1)}%</div>
                      <div className="font-mono">{(row.extractionRate * 100).toFixed(1)}%</div>
                      <div className="font-mono">{(row.avgSimilarity * 100).toFixed(1)}%</div>
                      <div className="font-mono">{row.correct}/{row.runs}</div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-medium">Recent Runs</h4>
              <Button
                variant="outline"
                size="sm"
                disabled={selectedEvaluationIds.size === 0}
                className="text-destructive hover:text-destructive hover:bg-destructive/10"
                onClick={deleteSelectedEvaluations}
              >
                Delete Selected ({selectedEvaluationIds.size})
              </Button>
            </div>
            <div className="rounded-md border bg-card overflow-hidden border-muted shadow-sm">
                <div className="grid grid-cols-8 p-4 border-b font-bold text-[10px] uppercase tracking-wider text-muted-foreground bg-muted/30">
                    <div className="flex items-center">
                      <Checkbox
                        checked={allRecentSelected}
                        onCheckedChange={(checked) => toggleSelectAllRecent(!!checked)}
                        aria-label="Select all recent runs"
                        className={someRecentSelected ? "opacity-60" : ""}
                      />
                    </div>
                    <div className="col-span-2">Run / Version</div>
                    <div>Date</div>
                    <div>F1 Score</div>
                    <div>Accuracy</div>
                    <div>Time (ms)</div>
                    <div className="text-right">Actions</div>
                </div>
                {recentEvaluations.map((run, idx) => (
                    <div key={run.runKey} className="grid grid-cols-8 p-4 border-b last:border-0 text-sm hover:bg-accent/5 transition-colors items-center">
                        <div className="flex items-center">
                          <Checkbox
                            checked={selectedEvaluationIds.has(run.runKey)}
                            onCheckedChange={(checked) => toggleSelectEvaluation(run.runKey, !!checked)}
                            aria-label={`Select run ${run.runKey}`}
                          />
                        </div>
                        <div className="col-span-2">
                            <div className="font-medium text-primary truncate">Run {recentEvaluations.length - idx}</div>
                            <div className="text-xs text-muted-foreground">
                              <Badge variant="outline" className="text-[10px] border-accent/20 text-accent font-mono">
                                {run.promptVersionName || 'Default'}
                              </Badge>
                              <span className="ml-2">{run.documentCount} docs</span>
                            </div>
                        </div>
                        <div className="flex items-center text-muted-foreground text-xs">
                          {new Date(run.evaluatedAt).toLocaleDateString()}
                        </div>
                        <div className="flex items-center font-mono font-bold text-accent">
                          {formatPercentage(run.f1Score)}
                        </div>
                        <div className="flex items-center font-mono font-medium">
                          {formatPercentage(run.accuracy)}
                        </div>
                        <div className="flex items-center font-mono text-muted-foreground text-xs">
                          {Math.round(run.latencyMs)}ms
                        </div>
                        <div className="flex items-center justify-end gap-1">
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => {
                              setSelectedRun(run);
                              setSelectedRunDocumentEvaluationId(run.evaluations[0]?.id || null);
                              setShowDetailsDialog(true);
                            }}
                          >
                            View Details
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm"
                            className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            onClick={async () => {
                              if (confirm('Delete this aggregated run?')) {
                                try {
                                  await Promise.all(run.evaluations.map((e) => api.deleteEvaluation(e.id)));
                                  await loadEvaluations();
                                  toast({ title: "Run deleted" });
                                } catch (error: any) {
                                  toast({ 
                                    title: "Failed to delete", 
                                    description: error.message,
                                    variant: "destructive" 
                                  });
                                }
                              }
                            }}
                          >
                            Delete
                          </Button>
                        </div>
                    </div>
                ))}
            </div>
          </div>

          {/* Evaluation Details Dialog */}
          <Dialog
            open={showDetailsDialog}
            onOpenChange={(open) => {
              setShowDetailsDialog(open);
              if (!open) {
                setSelectedRunDocumentEvaluationId(null);
              }
            }}
          >
            <DialogContent className="w-[96vw] max-w-[1200px] max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Evaluation Details</DialogTitle>
                <DialogDescription>
                  Field-by-field comparison of extracted values vs. ground truth
                </DialogDescription>
              </DialogHeader>
              
              {selectedRun && (
                <div className="space-y-6">
                  {/* Summary */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-accent">
                          {formatPercentage(selectedRun.f1Score)}
                        </div>
                        <p className="text-xs text-muted-foreground">F1 Score</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold">
                          {formatPercentage(selectedRun.accuracy)}
                        </div>
                        <p className="text-xs text-muted-foreground">Accuracy</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-green-600">
                          {selectedRun.correctFields}
                        </div>
                        <p className="text-xs text-muted-foreground">Correct</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-red-600">
                          {selectedRun.incorrectFields}
                        </div>
                        <p className="text-xs text-muted-foreground">Incorrect</p>
                      </CardContent>
                    </Card>
                  </div>

                  <div className="flex items-center justify-between rounded-md border p-3 bg-muted/20">
                    <div className="text-sm">
                      <span className="font-semibold">Version:</span> {selectedRun.promptVersionName}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {selectedRun.documentCount} documents • {new Date(selectedRun.evaluatedAt).toLocaleString()}
                    </div>
                  </div>

                  <Card className="border-muted">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Documents In This Run</CardTitle>
                      <CardDescription>Select a document to drill into its field predictions.</CardDescription>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="rounded-md border overflow-hidden">
                        <div className="grid grid-cols-6 p-3 text-[10px] uppercase tracking-wider font-bold text-muted-foreground bg-muted/30">
                          <div>Document</div>
                          <div>F1</div>
                          <div>Accuracy</div>
                          <div>Correct</div>
                          <div>Latency</div>
                          <div className="text-right">Action</div>
                        </div>
                        {selectedRun.evaluations.map((evaluation) => (
                          <div
                            key={evaluation.id}
                            className={`grid grid-cols-6 p-3 border-t text-sm items-center ${
                              selectedRunDocumentEvaluationId === evaluation.id ? "bg-accent/5" : ""
                            }`}
                          >
                            <div className="font-mono text-primary truncate">{evaluation.document_id.slice(0, 16)}...</div>
                            <div className="font-mono">{formatPercentage(evaluation.metrics.f1_score)}</div>
                            <div className="font-mono">{formatPercentage(evaluation.metrics.accuracy)}</div>
                            <div className="font-mono">{evaluation.metrics.correct_fields}/{evaluation.metrics.correct_fields + evaluation.metrics.incorrect_fields}</div>
                            <div className="font-mono">{evaluation.extraction_time_ms}ms</div>
                            <div className="text-right">
                              <Button
                                size="sm"
                                variant={selectedRunDocumentEvaluationId === evaluation.id ? "default" : "outline"}
                                onClick={() => setSelectedRunDocumentEvaluationId(evaluation.id)}
                              >
                                View Predictions
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Per-document details */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="font-semibold">
                        {selectedDocumentEvaluation
                          ? `Field Predictions • ${selectedDocumentEvaluation.document_id.slice(0, 12)}...`
                          : "Field Predictions"}
                      </h4>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowRawJson(!showRawJson)}
                        disabled={!selectedDocumentEvaluation}
                      >
                        {showRawJson ? 'Show Table View' : 'Show Raw JSON'}
                      </Button>
                    </div>
                    {!selectedDocumentEvaluation ? (
                      <Card className="border-dashed border-muted">
                        <CardContent className="py-8 text-center text-sm text-muted-foreground">
                          Select a document above to view field-level predictions.
                        </CardContent>
                      </Card>
                    ) : (selectedDocumentEvaluation ? [selectedDocumentEvaluation] : []).map((evaluation, evalIdx) => (
                      <Card key={`${evaluation.id}-${evalIdx}`} className="border-muted">
                        <CardHeader className="pb-2">
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-sm font-mono">
                              {evaluation.document_id.slice(0, 12)}...
                            </CardTitle>
                            <div className="flex items-center gap-3 text-xs text-muted-foreground">
                              <span>F1 {formatPercentage(evaluation.metrics.f1_score)}</span>
                              <span>Acc {formatPercentage(evaluation.metrics.accuracy)}</span>
                              <span>{evaluation.extraction_time_ms}ms</span>
                            </div>
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          {(evaluation.metrics.field_evaluations || []).map((field, idx) => {
                      // Check if this is an array of objects (table data)
                      const isArrayOfObjects = Array.isArray(field.extracted_value) && 
                                               field.extracted_value.length > 0 && 
                                               typeof field.extracted_value[0] === 'object';
                      
                      const gtIsArrayOfObjects = Array.isArray(field.ground_truth_value) && 
                                                 field.ground_truth_value.length > 0 && 
                                                 typeof field.ground_truth_value[0] === 'object';

                      // If showing raw JSON or not an array of objects, show JSON view
                      if (showRawJson || !isArrayOfObjects || !gtIsArrayOfObjects) {
                        return (
                          <Card key={idx} className={field.is_correct ? 'border-green-200 overflow-hidden' : 'border-red-200 overflow-hidden'}>
                            <CardHeader className="pb-3">
                              <div className="flex items-center justify-between">
                                <CardTitle className="text-sm font-mono">{field.field_name}</CardTitle>
                                <div className="flex items-center gap-2">
                                  {field.r2_score !== undefined && field.r2_score !== null && (
                                    <Badge variant="outline" className="font-mono">
                                      R² = {field.r2_score.toFixed(3)}
                                    </Badge>
                                  )}
                                  <Badge variant={field.is_correct ? 'default' : 'destructive'}>
                                    {field.is_correct ? '✓ Correct' : '✗ Incorrect'}
                                  </Badge>
                                </div>
                              </div>
                            </CardHeader>
                            <CardContent className="space-y-3">
                              <div>
                                <p className="text-xs font-semibold text-muted-foreground mb-1">Extracted Value:</p>
                                <pre className="text-sm bg-muted p-2 rounded whitespace-pre-wrap break-words overflow-x-auto">
                                  {toPreviewJson(field.extracted_value)}
                                </pre>
                              </div>
                              <div>
                                <p className="text-xs font-semibold text-muted-foreground mb-1">Ground Truth:</p>
                                <pre className="text-sm bg-muted p-2 rounded whitespace-pre-wrap break-words overflow-x-auto">
                                  {toPreviewJson(field.ground_truth_value)}
                                </pre>
                              </div>
                            </CardContent>
                          </Card>
                        );
                      }

                      // Otherwise show table view for arrays of objects
                      if (isArrayOfObjects && gtIsArrayOfObjects) {
                        // Render as table comparison
                        const extractedData = field.extracted_value as any[];
                        const groundTruthData = field.ground_truth_value as any[];
                        
                        // Get all unique keys from both arrays
                        const allKeys = new Set<string>();
                        [...extractedData, ...groundTruthData].forEach(item => {
                          Object.keys(item).forEach(key => allKeys.add(key));
                        });
                        const columns = Array.from(allKeys);

                        // Find primary key for matching
                        const primaryKeys = ['id', 'name', 'item', 'item_name', 'claim_item', 'title', 'key'];
                        const primaryKey = primaryKeys.find(key => allKeys.has(key)) || columns[0];

                        // Create a map of ground truth items by primary key
                        const gtMap = new Map();
                        groundTruthData.forEach(item => {
                          const key = String(normalizeComparable(item[primaryKey] ?? ""));
                          gtMap.set(key, item);
                        });

                        // Component-level (column) accuracy so prompts can be optimized per item.
                        const componentStats = columns.map((col) => {
                          let total = 0;
                          let correct = 0;
                          const extMap = new Map<string, Record<string, unknown>>();
                          extractedData.forEach((item) => {
                            extMap.set(String(normalizeComparable(item[primaryKey] ?? "")), item);
                          });
                          const rowKeys = new Set<string>([...gtMap.keys(), ...extMap.keys()]);
                          rowKeys.forEach((rowKey) => {
                            const gtItem = gtMap.get(rowKey) || {};
                            const extItem = extMap.get(rowKey) || {};
                            total += 1;
                            if (valuesMatch(extItem[col], gtItem[col])) {
                              correct += 1;
                            }
                          });
                          const accuracy = total > 0 ? correct / total : 0;
                          return { col, total, correct, accuracy };
                        });

                        return (
                          <Card key={idx} className={field.is_correct ? 'border-green-200 overflow-hidden' : 'border-red-200 overflow-hidden'}>
                            <CardHeader className="pb-3">
                              <div className="flex items-center justify-between">
                                <CardTitle className="text-sm font-mono">{field.field_name}</CardTitle>
                                <div className="flex items-center gap-2">
                                  {field.r2_score !== undefined && field.r2_score !== null && (
                                    <Badge variant="outline" className="font-mono">
                                      R² = {field.r2_score.toFixed(3)}
                                    </Badge>
                                  )}
                                  <Badge variant={field.is_correct ? 'default' : 'destructive'}>
                                    {field.is_correct ? '✓ Correct' : '✗ Incorrect'}
                                  </Badge>
                                </div>
                              </div>
                            </CardHeader>
                            <CardContent>
                              <div className="mb-3 flex flex-wrap gap-2">
                                {componentStats.map((s) => (
                                  <Badge key={s.col} variant="outline" className="font-mono">
                                    {s.col}: {(s.accuracy * 100).toFixed(0)}% ({s.correct}/{s.total})
                                  </Badge>
                                ))}
                              </div>
                              <div className="rounded-md border overflow-x-auto">
                                <Table>
                                  <TableHeader>
                                    <TableRow>
                                      <TableHead className="w-[50px]">Match</TableHead>
                                      {columns.map(col => (
                                        <TableHead key={col} className="font-mono text-xs">
                                          {col}
                                        </TableHead>
                                      ))}
                                      <TableHead className="text-xs text-muted-foreground">Source</TableHead>
                                    </TableRow>
                                  </TableHeader>
                                  <TableBody>
                                    {extractedData.map((extItem, rowIdx) => {
                                      const itemKey = String(normalizeComparable(extItem[primaryKey] ?? ""));
                                      const gtItem = gtMap.get(itemKey);
                                      const rowMatches = !!gtItem && columns.every((col) => valuesMatch(extItem[col], gtItem[col]));
                                      
                                      return (
                                        <TableRow key={`ext-${rowIdx}`} className="border-b">
                                          <TableCell className="text-center">
                                            {rowMatches ? (
                                              <Check className="h-4 w-4 text-green-600 mx-auto" />
                                            ) : (
                                              <X className="h-4 w-4 text-red-600 mx-auto" />
                                            )}
                                          </TableCell>
                                          {columns.map(col => {
                                            const extValue = extItem[col];
                                            const gtValue = gtItem?.[col];
                                            const matches = valuesMatch(extValue, gtValue);
                                            
                                            return (
                                              <TableCell 
                                                key={col}
                                                className={`text-sm ${!matches && gtItem ? 'bg-red-50' : ''}`}
                                              >
                                                <div className="font-medium">{truncateText(extValue)}</div>
                                                {gtItem && !matches && (
                                                  <div className="text-xs text-muted-foreground mt-1">
                                                    Expected: {truncateText(gtValue)}
                                                  </div>
                                                )}
                                              </TableCell>
                                            );
                                          })}
                                          <TableCell className="text-xs text-blue-600">Extracted</TableCell>
                                        </TableRow>
                                      );
                                    })}
                                    {/* Show ground truth items that weren't extracted */}
                                    {groundTruthData.filter(gtItem => {
                                      const gtKey = String(normalizeComparable(gtItem[primaryKey] ?? ""));
                                      return !extractedData.some(extItem => 
                                        String(normalizeComparable(extItem[primaryKey] ?? "")) === gtKey
                                      );
                                    }).map((gtItem, rowIdx) => (
                                      <TableRow key={`missing-${rowIdx}`} className="border-b bg-yellow-50">
                                        <TableCell className="text-center">
                                          <X className="h-4 w-4 text-red-600 mx-auto" />
                                        </TableCell>
                                        {columns.map(col => (
                                          <TableCell key={col} className="text-sm">
                                            <div className="text-xs text-muted-foreground italic">
                                              Expected: {truncateText(gtItem[col])}
                                            </div>
                                          </TableCell>
                                        ))}
                                        <TableCell className="text-xs text-red-600">Missing</TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </div>
                            </CardContent>
                          </Card>
                        );
                      }
                    })}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </DialogContent>
          </Dialog>
        </>
      )}
    </div>
  );
}
