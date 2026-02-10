import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import {
  FileText,
  CheckCircle2,
  Lightbulb,
  Wand2,
  Loader2,
  Sparkles,
  Brain,
  X,
  Check,
} from "lucide-react";
import { api } from "@/lib/api";

interface AutoClassifyStepProps {
  onComplete: () => void;
}

interface ClassificationSuggestion {
  documentId: string;
  filename: string;
  suggestedType: string;
  suggestedTypeId: string;
  confidence: number;
  reasoning: string;
  status: 'pending' | 'approved' | 'rejected';
}

export function AutoClassifyStep({ onComplete }: AutoClassifyStepProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [suggestions, setSuggestions] = useState<ClassificationSuggestion[]>([]);
  const [classifying, setClassifying] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  // Fetch documents
  const { data: documentsResponse } = useQuery({
    queryKey: ["documents"],
    queryFn: async () => {
      try {
        return await api.listDocuments();
      } catch (error) {
        console.error("Failed to fetch documents:", error);
        return { documents: [], total: 0 };
      }
    },
  });

  const documents = Array.isArray(documentsResponse?.documents) ? documentsResponse.documents : [];
  
  // Filter to sample documents only
  const sampleDocs = documents.filter(d => 
    d.filename && d.filename.includes('2024.pdf') && 
    (d.filename.includes('claim') || d.filename.includes('policy') || 
     d.filename.includes('loss') || d.filename.includes('vendor'))
  );

  // Auto-classify all documents
  const handleAutoClassifyAll = async () => {
    setClassifying(true);
    setSuggestions([]);
    
    try {
      const results: ClassificationSuggestion[] = [];
      
      for (const doc of sampleDocs) {
        try {
          // Call auto-classify with save=false to just get suggestions
          const result = await api.autoClassifyDocument(doc.id, false);
          results.push({
            documentId: doc.id,
            filename: doc.filename,
            suggestedType: result.document_type_name,
            suggestedTypeId: result.document_type_id,
            confidence: result.confidence,
            reasoning: result.reasoning || "Document analyzed successfully",
            status: 'pending',
          });
        } catch (error) {
          console.error(`Failed to classify ${doc.filename}:`, error);
        }
      }
      
      setSuggestions(results);
      toast({
        title: "Auto-Classification Complete",
        description: `Analyzed ${results.length} documents`,
      });
    } catch (error) {
      toast({
        title: "Classification Failed",
        description: "Failed to auto-classify documents",
        variant: "destructive",
      });
    } finally {
      setClassifying(false);
    }
  };

  // Approve a suggestion
  const approveMutation = useMutation({
    mutationFn: ({ docId, typeId }: { docId: string; typeId: string }) => 
      api.classifyDocument(docId, typeId),
    onSuccess: (_, variables) => {
      setSuggestions(prev => prev.map(s => 
        s.documentId === variables.docId ? { ...s, status: 'approved' as const } : s
      ));
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast({
        title: "Classification Saved",
        description: "Document classification has been saved",
      });
    },
  });

  // Reject a suggestion
  const handleReject = (docId: string) => {
    setSuggestions(prev => prev.map(s => 
      s.documentId === docId ? { ...s, status: 'rejected' as const } : s
    ));
  };

  const allReviewed = suggestions.length > 0 && suggestions.every(s => s.status !== 'pending');
  const approvedCount = suggestions.filter(s => s.status === 'approved').length;

  // Fetch selected document for preview
  const { data: documentResponse } = useQuery({
    queryKey: ["document", selectedDocId],
    queryFn: () => api.getDocument(selectedDocId!),
    enabled: !!selectedDocId,
  });

  const selectedDocument = documentResponse?.document;

  return (
    <div className="space-y-6">
      <Alert className="bg-purple-500/10 border-purple-500/20">
        <Brain className="h-4 w-4 text-purple-500" />
        <AlertDescription className="text-purple-700 dark:text-purple-300">
          AI auto-classification uses LLM to analyze document content and determine its type automatically.
          Review and approve/reject each suggestion below.
        </AlertDescription>
      </Alert>

      {/* Auto-classify button */}
      {suggestions.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wand2 className="h-5 w-5 text-primary" />
              Auto-Classify Sample Documents
            </CardTitle>
            <CardDescription>
              Found {sampleDocs.length} sample documents. Click below to analyze them all with AI.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={handleAutoClassifyAll}
              disabled={classifying || sampleDocs.length === 0}
              size="lg"
              className="w-full gap-2"
            >
              {classifying ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Analyzing {sampleDocs.length} documents...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Auto-Classify All Documents
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Classification suggestions */}
      {suggestions.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Suggestions list */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-primary" />
                Classification Suggestions
              </CardTitle>
              <CardDescription>
                Click a document to preview, then approve or reject
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="max-h-[600px] overflow-y-auto space-y-3 pr-2">
                {suggestions.map((suggestion) => (
                    <div
                      key={suggestion.documentId}
                      onClick={() => setSelectedDocId(suggestion.documentId)}
                      className={`p-4 rounded-lg border cursor-pointer transition-all ${
                        selectedDocId === suggestion.documentId
                          ? 'ring-2 ring-primary'
                          : ''
                      } ${
                        suggestion.status === 'approved'
                          ? 'bg-emerald-500/10 border-emerald-500/50'
                          : suggestion.status === 'rejected'
                          ? 'bg-red-500/10 border-red-500/50'
                          : 'bg-muted/30 hover:bg-muted/50'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 space-y-2">
                          <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4 text-muted-foreground" />
                            <span className="font-medium">{suggestion.filename}</span>
                          </div>
                        
                        <div className="flex items-center gap-3">
                          <Badge variant="default">{suggestion.suggestedType}</Badge>
                          <span className="text-sm text-muted-foreground">
                            {Math.round(suggestion.confidence * 100)}% confidence
                          </span>
                        </div>
                        
                        <div className="text-sm text-muted-foreground bg-muted/50 p-2 rounded">
                          {suggestion.reasoning}
                        </div>
                      </div>
                      
                      {suggestion.status === 'pending' && (
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => 
                              approveMutation.mutate({
                                docId: suggestion.documentId,
                                typeId: suggestion.suggestedTypeId,
                              })
                            }
                            disabled={approveMutation.isPending}
                            className="gap-1 text-emerald-600 hover:text-emerald-700 hover:bg-emerald-500/10"
                          >
                            <Check className="h-4 w-4" />
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleReject(suggestion.documentId)}
                            className="gap-1 text-red-600 hover:text-red-700 hover:bg-red-500/10"
                          >
                            <X className="h-4 w-4" />
                            Reject
                          </Button>
                        </div>
                      )}
                      
                      {suggestion.status === 'approved' && (
                        <Badge variant="default" className="bg-emerald-600">
                          <Check className="h-3 w-3 mr-1" />
                          Approved
                        </Badge>
                      )}
                      
                      {suggestion.status === 'rejected' && (
                        <Badge variant="destructive">
                          <X className="h-3 w-3 mr-1" />
                          Rejected
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
        </Card>

        {/* Document preview */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-primary" />
              Document Preview
            </CardTitle>
            <CardDescription>
              {selectedDocument ? selectedDocument.filename : 'Select a document to preview'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {selectedDocument ? (
              <ScrollArea className="h-[600px] rounded border p-4 bg-muted/30">
                <pre className="text-xs whitespace-pre-wrap font-mono">
                  {selectedDocument.content}
                </pre>
              </ScrollArea>
            ) : (
              <div className="h-[600px] flex items-center justify-center text-muted-foreground border rounded bg-muted/10">
                Click on a document to see its preview
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      )}

      {allReviewed && (
        <div className="flex items-center justify-center gap-2 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          <span className="font-medium text-emerald-700 dark:text-emerald-300">
            Review complete! Approved {approvedCount} of {suggestions.length} suggestions. Click "Next" to continue.
          </span>
        </div>
      )}
    </div>
  );
}
