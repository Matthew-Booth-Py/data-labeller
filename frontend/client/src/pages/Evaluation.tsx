import { useState, useEffect } from 'react';
import { useParams } from 'wouter';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { PlayCircle, TrendingUp, AlertCircle, CheckCircle2, XCircle } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface FieldEvaluation {
  field_name: string;
  extracted_value: any;
  ground_truth_value: any;
  is_correct: boolean;
  is_present: boolean;
  is_extracted: boolean;
}

interface EvaluationMetrics {
  total_fields: number;
  correct_fields: number;
  incorrect_fields: number;
  missing_fields: number;
  extra_fields: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  field_evaluations: FieldEvaluation[];
}

interface Evaluation {
  id: string;
  document_id: string;
  document_type_id: string;
  prompt_version_id: string | null;
  prompt_version_name: string | null;
  metrics: EvaluationMetrics;
  extraction_time_ms: number;
  evaluated_at: string;
  notes: string | null;
}

interface EvaluationSummary {
  prompt_version_id: string | null;
  prompt_version_name: string | null;
  document_type_id: string | null;
  total_evaluations: number;
  avg_accuracy: number;
  avg_precision: number;
  avg_recall: number;
  avg_f1_score: number;
  field_performance: Record<string, { accuracy: number; precision: number; recall: number }>;
}

interface PromptVersion {
  id: string;
  name: string;
  document_type_id: string | null;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export default function Evaluation() {
  const { projectId } = useParams();
  const { toast } = useToast();
  
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [summary, setSummary] = useState<EvaluationSummary | null>(null);
  const [promptVersions, setPromptVersions] = useState<PromptVersion[]>([]);
  const [selectedPromptVersion, setSelectedPromptVersion] = useState<string>('all');
  const [loading, setLoading] = useState(false);
  const [runningEval, setRunningEval] = useState(false);
  const [showRunDialog, setShowRunDialog] = useState(false);
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<string>('');
  const [useStructuredOutput, setUseStructuredOutput] = useState(true);

  useEffect(() => {
    loadEvaluations();
    loadPromptVersions();
    loadDocuments();
  }, [projectId, selectedPromptVersion]);

  const loadDocuments = async () => {
    try {
      const response = await fetch('/api/v1/documents');
      if (!response.ok) throw new Error('Failed to load documents');
      const data = await response.json();
      setDocuments(data.documents || []);
    } catch (error) {
      console.error('Error loading documents:', error);
    }
  };

  const loadEvaluations = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedPromptVersion !== 'all') {
        params.append('prompt_version_id', selectedPromptVersion);
      }
      
      const response = await fetch(`/api/evaluation?${params}`);
      if (!response.ok) throw new Error('Failed to load evaluations');
      
      const data = await response.json();
      setEvaluations(data.evaluations);
      
      // Load summary
      const summaryResponse = await fetch(`/api/evaluation/summary/aggregate?${params}`);
      if (summaryResponse.ok) {
        const summaryData = await summaryResponse.json();
        setSummary(summaryData.summary);
      }
    } catch (error) {
      console.error('Error loading evaluations:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadPromptVersions = async () => {
    try {
      const response = await fetch('/api/evaluation/prompts');
      if (!response.ok) throw new Error('Failed to load prompt versions');
      
      const data = await response.json();
      setPromptVersions(data.prompt_versions);
    } catch (error) {
      console.error('Error loading prompt versions:', error);
    }
  };

  const runEvaluation = async () => {
    if (!selectedDocument) {
      toast({
        title: 'No Document Selected',
        description: 'Please select a document to evaluate.',
        variant: 'destructive',
      });
      return;
    }

    setRunningEval(true);
    try {
      const response = await fetch('/api/v1/evaluation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_id: selectedDocument,
          prompt_version_id: selectedPromptVersion !== 'all' ? selectedPromptVersion : null,
          use_structured_output: useStructuredOutput,
          use_llm_refinement: !useStructuredOutput,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Evaluation failed');
      }

      const result = await response.json();
      const f1Score = (result.evaluation.metrics.f1_score * 100).toFixed(1);

      toast({
        title: 'Evaluation Complete',
        description: `F1 Score: ${f1Score}% - Extraction quality metrics calculated.`,
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

  const getScoreColor = (score: number) => {
    if (score >= 0.9) return 'text-green-600';
    if (score >= 0.7) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Extraction Evaluation</h1>
          <p className="text-muted-foreground mt-1">
            Measure extraction quality against ground truth annotations
          </p>
        </div>
        
        <div className="flex gap-3">
          <Dialog open={showRunDialog} onOpenChange={setShowRunDialog}>
            <DialogTrigger asChild>
              <Button className="gap-2">
                <PlayCircle className="w-4 h-4" />
                Run Evaluation
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Run Extraction Evaluation</DialogTitle>
                <DialogDescription>
                  Select a labeled document to evaluate extraction quality
                </DialogDescription>
              </DialogHeader>
              
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Document</Label>
                  <Select value={selectedDocument} onValueChange={setSelectedDocument}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a document" />
                    </SelectTrigger>
                    <SelectContent>
                      {documents.map((doc) => (
                        <SelectItem key={doc.id} value={doc.id}>
                          {doc.filename}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Prompt Version</Label>
                  <Select 
                    value={selectedPromptVersion === 'all' ? '' : selectedPromptVersion} 
                    onValueChange={(value) => setSelectedPromptVersion(value || 'all')}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Default (Active)" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">Default (Active)</SelectItem>
                      {promptVersions.map((pv) => (
                        <SelectItem key={pv.id} value={pv.id}>
                          {pv.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
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
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setShowRunDialog(false)}>
                  Cancel
                </Button>
                <Button onClick={runEvaluation} disabled={runningEval}>
                  {runningEval ? 'Running...' : 'Run Evaluation'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Select value={selectedPromptVersion} onValueChange={setSelectedPromptVersion}>
            <SelectTrigger className="w-[250px]">
              <SelectValue placeholder="Filter by prompt version" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Prompt Versions</SelectItem>
              {promptVersions.map((pv) => (
                <SelectItem key={pv.id} value={pv.id}>
                  {pv.name} {pv.is_active && '(Active)'}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Accuracy
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${getScoreColor(summary.avg_accuracy)}`}>
                {formatPercentage(summary.avg_accuracy)}
              </div>
              <Progress value={summary.avg_accuracy * 100} className="mt-2" />
              <p className="text-xs text-muted-foreground mt-2">
                {summary.total_evaluations} evaluations
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Precision
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${getScoreColor(summary.avg_precision)}`}>
                {formatPercentage(summary.avg_precision)}
              </div>
              <Progress value={summary.avg_precision * 100} className="mt-2" />
              <p className="text-xs text-muted-foreground mt-2">
                Correct / Extracted
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Recall
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${getScoreColor(summary.avg_recall)}`}>
                {formatPercentage(summary.avg_recall)}
              </div>
              <Progress value={summary.avg_recall * 100} className="mt-2" />
              <p className="text-xs text-muted-foreground mt-2">
                Correct / Present
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                F1 Score
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${getScoreColor(summary.avg_f1_score)}`}>
                {formatPercentage(summary.avg_f1_score)}
              </div>
              <Progress value={summary.avg_f1_score * 100} className="mt-2" />
              <p className="text-xs text-muted-foreground mt-2">
                Harmonic mean
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Field Performance */}
      {summary && Object.keys(summary.field_performance).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Field-Level Performance</CardTitle>
            <CardDescription>
              Accuracy breakdown by field
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Field Name</TableHead>
                  <TableHead>Accuracy</TableHead>
                  <TableHead>Precision</TableHead>
                  <TableHead>Recall</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(summary.field_performance).map(([fieldName, metrics]) => (
                  <TableRow key={fieldName}>
                    <TableCell className="font-medium">{fieldName}</TableCell>
                    <TableCell className={getScoreColor(metrics.accuracy)}>
                      {formatPercentage(metrics.accuracy)}
                    </TableCell>
                    <TableCell className={getScoreColor(metrics.precision)}>
                      {formatPercentage(metrics.precision)}
                    </TableCell>
                    <TableCell className={getScoreColor(metrics.recall)}>
                      {formatPercentage(metrics.recall)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Recent Evaluations */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Evaluations</CardTitle>
          <CardDescription>
            Latest extraction quality assessments
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">
              Loading evaluations...
            </div>
          ) : evaluations.length === 0 ? (
            <div className="text-center py-8">
              <AlertCircle className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                No evaluations yet. Run an evaluation on a labeled document to get started.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Document</TableHead>
                  <TableHead>Prompt Version</TableHead>
                  <TableHead>F1 Score</TableHead>
                  <TableHead>Accuracy</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {evaluations.map((evaluation) => (
                  <TableRow key={evaluation.id}>
                    <TableCell className="font-medium">
                      {evaluation.document_id.slice(0, 8)}...
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {evaluation.prompt_version_name || 'Default'}
                      </Badge>
                    </TableCell>
                    <TableCell className={getScoreColor(evaluation.metrics.f1_score)}>
                      {formatPercentage(evaluation.metrics.f1_score)}
                    </TableCell>
                    <TableCell className={getScoreColor(evaluation.metrics.accuracy)}>
                      {formatPercentage(evaluation.metrics.accuracy)}
                    </TableCell>
                    <TableCell>{evaluation.extraction_time_ms}ms</TableCell>
                    <TableCell>
                      {new Date(evaluation.evaluated_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Badge variant="secondary" className="text-xs">
                          <CheckCircle2 className="w-3 h-3 mr-1" />
                          {evaluation.metrics.correct_fields}
                        </Badge>
                        <Badge variant="destructive" className="text-xs">
                          <XCircle className="w-3 h-3 mr-1" />
                          {evaluation.metrics.incorrect_fields}
                        </Badge>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Prompt Comparison */}
      {promptVersions.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              Prompt Version Comparison
            </CardTitle>
            <CardDescription>
              Compare performance across different prompt versions
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={() => window.location.href = `/projects/${projectId}/evaluation/compare`}
              variant="outline"
            >
              View Detailed Comparison
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
