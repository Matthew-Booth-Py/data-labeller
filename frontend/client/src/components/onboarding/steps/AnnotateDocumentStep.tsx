import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  FileText,
  CheckCircle2,
  Lightbulb,
  MousePointer,
  ArrowRight,
  Tag,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { useLocation } from "wouter";

interface AnnotateDocumentStepProps {
  documentId: string | null;
  onComplete: () => void;
}

export function AnnotateDocumentStep({ documentId, onComplete }: AnnotateDocumentStepProps) {
  const [, setLocation] = useLocation();

  // Fetch document
  const { data: documentResponse } = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => api.getDocument(documentId!),
    enabled: !!documentId,
  });

  const document = documentResponse?.document;

  // Fetch annotations for this document
  const { data: annotations } = useQuery({
    queryKey: ["annotations", documentId],
    queryFn: () => api.listAnnotations(documentId!),
    enabled: !!documentId,
  });

  const annotationCount = annotations?.length || 0;
  const hasAnnotations = annotationCount > 0;

  // What to look for in insurance documents
  const annotationHints = [
    { label: "Claim Number", example: "CLM-2024-AUTO-00147", tip: "Look in the header section" },
    { label: "Policy Number", example: "POL-AUTO-2024-88421", tip: "Usually near the claim number" },
    { label: "Person Name", example: "Robert J. Thompson", tip: "Claimant or insured name" },
    { label: "Date", example: "January 15, 2024", tip: "Date of loss, filing date" },
    { label: "Amount", example: "$3,950.00", tip: "Damage estimates, totals" },
  ];

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

  return (
    <div className="space-y-6">
      <Alert className="bg-blue-500/10 border-blue-500/20">
        <MousePointer className="h-4 w-4 text-blue-500" />
        <AlertDescription className="text-blue-700 dark:text-blue-300">
          <strong>What is annotation?</strong> Annotation means highlighting text in documents and tagging it with labels.
          For example, you might select "CLM-2024-AUTO-00147" and tag it as "Claim Number".
          This trains the AI to recognize and extract these fields automatically from future documents.
        </AlertDescription>
      </Alert>

      {/* Current document */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Current Document
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">{document?.filename}</div>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="secondary">
                  {annotationCount} annotation{annotationCount !== 1 ? "s" : ""}
                </Badge>
                {hasAnnotations && (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                )}
              </div>
            </div>
            <Button onClick={() => setLocation(`/project/tutorial`)}>
              Open in Label Studio
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Annotation hints */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            What to Annotate
          </CardTitle>
          <CardDescription>
            Look for these types of information in the document
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {annotationHints.map((hint, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg border bg-muted/30">
                <Tag className="h-4 w-4 text-muted-foreground mt-1" />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{hint.label}</span>
                    <Badge variant="outline" className="text-xs font-mono">
                      {hint.example}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{hint.tip}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Instructions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Step-by-Step Guide</CardTitle>
          <CardDescription>
            Follow these steps to create your first annotation
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="space-y-4">
            <li className="flex gap-3">
              <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 text-sm font-medium text-primary">1</div>
              <div>
                <div className="text-sm font-medium">Open the document</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  Click "Open in Label Studio" above to view the document content
                </div>
              </div>
            </li>
            <li className="flex gap-3">
              <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 text-sm font-medium text-primary">2</div>
              <div>
                <div className="text-sm font-medium">Select text with your mouse</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  Click and drag to highlight text (e.g., "CLM-2024-AUTO-00147")
                </div>
              </div>
            </li>
            <li className="flex gap-3">
              <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 text-sm font-medium text-primary">3</div>
              <div>
                <div className="text-sm font-medium">Pick a label from the menu</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  A popup will appear - choose the matching label (e.g., "Claim Number")
                </div>
              </div>
            </li>
            <li className="flex gap-3">
              <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 text-sm font-medium text-primary">4</div>
              <div>
                <div className="text-sm font-medium">Annotate more fields</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  Repeat for other important information like dates, amounts, and names
                </div>
              </div>
            </li>
          </ol>
        </CardContent>
      </Card>

      {hasAnnotations ? (
        <div className="flex items-center justify-center gap-2 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          <span className="font-medium text-emerald-700 dark:text-emerald-300">
            Great work! You've created {annotationCount} annotation{annotationCount !== 1 ? "s" : ""}. 
            Click "Next" to get AI suggestions.
          </span>
        </div>
      ) : (
        <div className="flex items-center justify-center gap-2 p-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <Lightbulb className="h-4 w-4 text-amber-500" />
          <span className="text-sm text-amber-700 dark:text-amber-300">
            Try creating at least one annotation, then click "Next" to continue.
          </span>
        </div>
      )}
    </div>
  );
}
