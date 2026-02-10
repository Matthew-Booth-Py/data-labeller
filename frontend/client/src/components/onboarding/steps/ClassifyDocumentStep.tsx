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
  FolderOpen,
  MousePointer,
  ArrowRight,
} from "lucide-react";
import { api } from "@/lib/api";

interface ClassifyDocumentStepProps {
  documentId: string | null;
  onComplete: () => void;
}

export function ClassifyDocumentStep({ documentId, onComplete }: ClassifyDocumentStepProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Fetch document
  const { data: documentResponse } = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => api.getDocument(documentId!),
    enabled: !!documentId,
  });

  const document = documentResponse?.document;

  // Fetch document types
  const { data: documentTypesResponse } = useQuery({
    queryKey: ["document-types"],
    queryFn: () => api.listDocumentTypes(),
  });

  const documentTypes = documentTypesResponse?.types ?? [];

  // Fetch current classification
  const { data: classificationResponse, refetch: refetchClassification } = useQuery({
    queryKey: ["document-classification", documentId],
    queryFn: () => api.getDocumentClassification(documentId!),
    enabled: !!documentId,
  });

  const classification = classificationResponse?.classification;

  // Classify mutation
  const classifyMutation = useMutation({
    mutationFn: (typeId: string) => api.classifyDocument(documentId!, typeId),
    onSuccess: (result) => {
      refetchClassification();
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast({
        title: "Document Classified",
        description: `Classified as ${result.classification.document_type_name}`,
      });
      onComplete();
    },
    onError: (error: Error) => {
      toast({
        title: "Classification Failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  if (!documentId) {
    return (
      <Alert className="bg-amber-500/10 border-amber-500/20">
        <Lightbulb className="h-4 w-4 text-amber-500" />
        <AlertDescription className="text-amber-700 dark:text-amber-300">
          Please go back to the "Sample Documents" step and select a document first.
        </AlertDescription>
      </Alert>
    );
  }

  const isClassified = classification?.document_type_id != null;

  return (
    <div className="space-y-6">
      <Alert className="bg-blue-500/10 border-blue-500/20">
        <Lightbulb className="h-4 w-4 text-blue-500" />
        <AlertDescription className="text-blue-700 dark:text-blue-300">
          Manual classification helps train the AI to recognize document types. 
          Click on a document type below to classify the selected document.
        </AlertDescription>
      </Alert>

      {/* Current document info */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Selected Document
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">{document?.filename}</div>
              {isClassified && (
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="default">{classification.document_type_name}</Badge>
                  <span className="text-sm text-muted-foreground">
                    Already classified
                  </span>
                </div>
              )}
            </div>
            {isClassified && (
              <CheckCircle2 className="h-6 w-6 text-emerald-500" />
            )}
          </div>
        </CardContent>
      </Card>

      {/* Document type selection */}
      <div>
        <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
          <MousePointer className="h-4 w-4" />
          Click a document type to classify:
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {documentTypes?.map((type) => {
            const isSelected = classification?.document_type_id === type.id;
            return (
              <Button
                key={type.id}
                variant={isSelected ? "default" : "outline"}
                className={`h-auto py-4 flex flex-col items-start gap-1 ${
                  isSelected ? "" : "hover:border-primary"
                }`}
                onClick={() => classifyMutation.mutate(type.id)}
                disabled={classifyMutation.isPending}
              >
                <div className="flex items-center gap-2 w-full">
                  <FolderOpen className="h-4 w-4" />
                  <span className="font-medium">{type.name}</span>
                  {isSelected && <CheckCircle2 className="h-4 w-4 ml-auto" />}
                </div>
                <div className="text-xs text-muted-foreground text-left font-normal">
                  {type.description}
                </div>
              </Button>
            );
          })}
        </div>
      </div>

      {isClassified && (
        <div className="flex items-center justify-center gap-2 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          <span className="font-medium text-emerald-700 dark:text-emerald-300">
            Document classified! Click "Next" to test auto-classification.
          </span>
        </div>
      )}

      {/* Document preview - scrollable */}
      {document?.content && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Document Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-64 rounded border p-4 bg-muted/30">
              <pre className="text-xs whitespace-pre-wrap font-mono">
                {document.content.slice(0, 2000)}
                {document.content.length > 2000 && "..."}
              </pre>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
