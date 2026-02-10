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
}

interface Evaluation {
  id: string;
  document_id: string;
  document_type_id: string;
  prompt_version_id: string | null;
  prompt_version_name: string | null;
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
  const [selectedEvaluation, setSelectedEvaluation] = useState<Evaluation | null>(null);
  const [showDetailsDialog, setShowDetailsDialog] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);

  useEffect(() => {
    loadDocuments();
  }, []);

  // Load evaluations after we have the document type ID
  useEffect(() => {
    if (documentTypeId) {
      loadEvaluations();
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
    } catch (error) {
      console.error('Error loading evaluations:', error);
    } finally {
      setLoading(false);
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

      // Run evaluation on all documents in the project
      const response = await fetch(`${getApiUrl()}/api/v1/evaluation/run-project`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_type_id: documentTypeId,
          use_structured_output: useStructuredOutput,
          use_llm_refinement: !useStructuredOutput,
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

  // Prepare chart data
  const chartData = evaluations.slice(0, 5).reverse().map((evaluation, idx) => ({
    promptVersion: evaluation.prompt_version_name || `Run ${idx + 1}`,
    accuracy: evaluation.metrics.accuracy * 100,
    completeness: evaluation.metrics.recall * 100,
    latency: evaluation.extraction_time_ms,
    cost: 0.45, // Mock cost for now
  }));

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
             <Card className="col-span-1 lg:col-span-2 border-muted bg-white">
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
                            />
                            <Legend />
                            <Bar dataKey="accuracy" name="Field Accuracy" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} barSize={40} />
                            <Bar dataKey="completeness" name="Completeness" fill="hsl(var(--chart-2))" radius={[4, 4, 0, 0]} barSize={40} />
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
             </Card>

             <Card className="border-muted bg-white">
                <CardHeader>
                    <CardTitle className="text-primary text-sm uppercase tracking-wider font-bold">Latency (ms)</CardTitle>
                </CardHeader>
                <CardContent className="h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted))" />
                            <XAxis dataKey="promptVersion" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                            <Tooltip />
                            <Line type="monotone" dataKey="latency" stroke="hsl(var(--chart-3))" strokeWidth={3} dot={{r: 6, fill: 'hsl(var(--chart-3))'}} />
                        </LineChart>
                    </ResponsiveContainer>
                </CardContent>
             </Card>

             <Card className="border-muted bg-white">
                <CardHeader>
                    <CardTitle className="text-primary text-sm uppercase tracking-wider font-bold">Cost Efficiency</CardTitle>
                </CardHeader>
                 <CardContent className="h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted))" />
                            <XAxis dataKey="promptVersion" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                            <Tooltip />
                            <Line type="monotone" dataKey="cost" stroke="hsl(var(--chart-5))" strokeWidth={3} dot={{r: 6, fill: 'hsl(var(--chart-5))'}} />
                        </LineChart>
                    </ResponsiveContainer>
                </CardContent>
             </Card>
          </div>

          <div className="space-y-4">
            <h4 className="font-medium">Recent Runs</h4>
            <div className="rounded-md border bg-card overflow-hidden border-muted shadow-sm">
                <div className="grid grid-cols-7 p-4 border-b font-bold text-[10px] uppercase tracking-wider text-muted-foreground bg-muted/30">
                    <div className="col-span-2">Document / Version</div>
                    <div>Date</div>
                    <div>F1 Score</div>
                    <div>Accuracy</div>
                    <div>Time (ms)</div>
                    <div className="text-right">Actions</div>
                </div>
                {evaluations.slice(0, 10).map((evaluation) => (
                    <div key={evaluation.id} className="grid grid-cols-7 p-4 border-b last:border-0 text-sm hover:bg-accent/5 transition-colors items-center">
                        <div className="col-span-2">
                            <div className="font-medium text-primary truncate">{evaluation.document_id.slice(0, 12)}...</div>
                            <div className="text-xs text-muted-foreground">
                              <Badge variant="outline" className="text-[10px] border-accent/20 text-accent font-mono">
                                {evaluation.prompt_version_name || 'Default'}
                              </Badge>
                            </div>
                        </div>
                        <div className="flex items-center text-muted-foreground text-xs">
                          {new Date(evaluation.evaluated_at).toLocaleDateString()}
                        </div>
                        <div className="flex items-center font-mono font-bold text-accent">
                          {formatPercentage(evaluation.metrics.f1_score)}
                        </div>
                        <div className="flex items-center font-mono font-medium">
                          {formatPercentage(evaluation.metrics.accuracy)}
                        </div>
                        <div className="flex items-center font-mono text-muted-foreground text-xs">
                          {evaluation.extraction_time_ms}ms
                        </div>
                        <div className="flex items-center justify-end gap-1">
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => {
                              setSelectedEvaluation(evaluation);
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
                              if (confirm('Delete this evaluation run?')) {
                                try {
                                  await api.deleteEvaluation(evaluation.id);
                                  loadEvaluations();
                                  toast({ title: "Evaluation deleted" });
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
          <Dialog open={showDetailsDialog} onOpenChange={setShowDetailsDialog}>
            <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Evaluation Details</DialogTitle>
                <DialogDescription>
                  Field-by-field comparison of extracted values vs. ground truth
                </DialogDescription>
              </DialogHeader>
              
              {selectedEvaluation && (
                <div className="space-y-6">
                  {/* Summary */}
                  <div className="grid grid-cols-4 gap-4">
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-accent">
                          {formatPercentage(selectedEvaluation.metrics.f1_score)}
                        </div>
                        <p className="text-xs text-muted-foreground">F1 Score</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold">
                          {formatPercentage(selectedEvaluation.metrics.accuracy)}
                        </div>
                        <p className="text-xs text-muted-foreground">Accuracy</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-green-600">
                          {selectedEvaluation.metrics.correct_fields}
                        </div>
                        <p className="text-xs text-muted-foreground">Correct</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-red-600">
                          {selectedEvaluation.metrics.incorrect_fields}
                        </div>
                        <p className="text-xs text-muted-foreground">Incorrect</p>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Field Evaluations */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="font-semibold">Field Predictions</h4>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowRawJson(!showRawJson)}
                      >
                        {showRawJson ? 'Show Table View' : 'Show Raw JSON'}
                      </Button>
                    </div>
                    {selectedEvaluation.metrics.field_evaluations?.map((field, idx) => {
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
                          <Card key={idx} className={field.is_correct ? 'border-green-200' : 'border-red-200'}>
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
                                <pre className="text-sm bg-muted p-2 rounded overflow-x-auto">
                                  {JSON.stringify(field.extracted_value, null, 2)}
                                </pre>
                              </div>
                              <div>
                                <p className="text-xs font-semibold text-muted-foreground mb-1">Ground Truth:</p>
                                <pre className="text-sm bg-muted p-2 rounded overflow-x-auto">
                                  {JSON.stringify(field.ground_truth_value, null, 2)}
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
                          const key = String(item[primaryKey] || '').toLowerCase();
                          gtMap.set(key, item);
                        });

                        return (
                          <Card key={idx} className={field.is_correct ? 'border-green-200' : 'border-red-200'}>
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
                                      const itemKey = String(extItem[primaryKey] || '').toLowerCase();
                                      const gtItem = gtMap.get(itemKey);
                                      
                                      return (
                                        <TableRow key={`ext-${rowIdx}`} className="border-b">
                                          <TableCell className="text-center">
                                            {gtItem && JSON.stringify(extItem) === JSON.stringify(gtItem) ? (
                                              <Check className="h-4 w-4 text-green-600 mx-auto" />
                                            ) : (
                                              <X className="h-4 w-4 text-red-600 mx-auto" />
                                            )}
                                          </TableCell>
                                          {columns.map(col => {
                                            const extValue = extItem[col];
                                            const gtValue = gtItem?.[col];
                                            const matches = String(extValue) === String(gtValue);
                                            
                                            return (
                                              <TableCell 
                                                key={col}
                                                className={`text-sm ${!matches && gtItem ? 'bg-red-50' : ''}`}
                                              >
                                                <div className="font-medium">{String(extValue ?? '')}</div>
                                                {gtItem && !matches && (
                                                  <div className="text-xs text-muted-foreground mt-1">
                                                    Expected: {String(gtValue ?? '')}
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
                                      const gtKey = String(gtItem[primaryKey] || '').toLowerCase();
                                      return !extractedData.some(extItem => 
                                        String(extItem[primaryKey] || '').toLowerCase() === gtKey
                                      );
                                    }).map((gtItem, rowIdx) => (
                                      <TableRow key={`missing-${rowIdx}`} className="border-b bg-yellow-50">
                                        <TableCell className="text-center">
                                          <X className="h-4 w-4 text-red-600 mx-auto" />
                                        </TableCell>
                                        {columns.map(col => (
                                          <TableCell key={col} className="text-sm">
                                            <div className="text-xs text-muted-foreground italic">
                                              Expected: {String(gtItem[col] ?? '')}
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
