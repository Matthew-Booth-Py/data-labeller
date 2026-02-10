import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import {
  FileText,
  CheckCircle2,
  Lightbulb,
  Brain,
  Loader2,
  Sparkles,
  Wand2,
  ArrowRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { useLocation } from "wouter";

interface GetSuggestionsStepProps {
  documentId: string | null;
  onComplete: () => void;
}

export function GetSuggestionsStep({ documentId, onComplete }: GetSuggestionsStepProps) {
  const [, setLocation] = useLocation();
  const { toast } = useToast();
  const [suggestions, setSuggestions] = useState<Array<{
    text: string;
    label_name: string;
  }>>([]);

  // Fetch document
  const { data: documentResponse } = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => api.getDocument(documentId!),
    enabled: !!documentId,
  });

  const document = documentResponse?.document;

  // Get suggestions mutation
  const suggestMutation = useMutation({
    mutationFn: () => api.suggestAnnotations(documentId!),
    onSuccess: (result) => {
      setSuggestions(result.suggestions);
      toast({
        title: "Suggestions Generated",
        description: `Found ${result.suggestions.length} potential annotations`,
      });
      if (result.suggestions.length > 0) {
        onComplete();
      }
    },
    onError: (error: Error) => {
      toast({
        title: "Suggestion Failed",
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

  return (
    <div className="space-y-6">
      <Alert className="bg-purple-500/10 border-purple-500/20">
        <Brain className="h-4 w-4 text-purple-500" />
        <AlertDescription className="text-purple-700 dark:text-purple-300">
          AI suggestions combine LLM analysis with machine learning trained on your annotations.
          As you label more documents, suggestions become more accurate.
        </AlertDescription>
      </Alert>

      {/* Current document */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Document
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="font-medium">{document?.filename}</div>
            <Button
              onClick={() => suggestMutation.mutate()}
              disabled={suggestMutation.isPending}
              className="gap-2"
            >
              {suggestMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Get AI Suggestions
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* How it works */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wand2 className="h-5 w-5 text-primary" />
            How AI Suggestions Work
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-lg border bg-muted/30">
              <div className="flex items-center gap-2 mb-2">
                <Brain className="h-5 w-5 text-purple-500" />
                <span className="font-medium">LLM Analysis</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Uses GPT to understand document context and find entities matching your label definitions.
              </p>
            </div>
            <div className="p-4 rounded-lg border bg-muted/30">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="h-5 w-5 text-amber-500" />
                <span className="font-medium">ML Training</span>
              </div>
              <p className="text-sm text-muted-foreground">
                After ~20 annotations, a local ML model learns your patterns for faster, more accurate suggestions.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Suggestions results */}
      {suggestions.length > 0 && (
        <Card className="border-emerald-500/50 bg-emerald-500/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300">
              <CheckCircle2 className="h-5 w-5" />
              AI Suggestions ({suggestions.length})
            </CardTitle>
            <CardDescription>
              These are potential annotations found by the AI
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-64 overflow-auto">
              {suggestions.slice(0, 10).map((suggestion, i) => (
                <div key={i} className="flex items-center gap-3 p-2 rounded border bg-background">
                  <Badge variant="outline">{suggestion.label_name}</Badge>
                  <code className="text-sm bg-muted px-2 py-0.5 rounded">
                    {suggestion.text.slice(0, 50)}{suggestion.text.length > 50 ? "..." : ""}
                  </code>
                </div>
              ))}
              {suggestions.length > 10 && (
                <div className="text-sm text-muted-foreground text-center py-2">
                  +{suggestions.length - 10} more suggestions
                </div>
              )}
            </div>
            <Button
              variant="outline"
              className="w-full mt-4 gap-2"
              onClick={() => setLocation(`/project/tutorial`)}
            >
              View in Label Studio
              <ArrowRight className="h-4 w-4" />
            </Button>
          </CardContent>
        </Card>
      )}

      {suggestions.length > 0 ? (
        <div className="flex items-center justify-center gap-2 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          <span className="font-medium text-emerald-700 dark:text-emerald-300">
            AI found {suggestions.length} suggestions! Click "Next" to complete the tutorial.
          </span>
        </div>
      ) : (
        <div className="flex items-center justify-center gap-2 p-4 rounded-lg bg-muted border">
          <Lightbulb className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            Click "Get AI Suggestions" to see what the AI finds.
          </span>
        </div>
      )}
    </div>
  );
}
