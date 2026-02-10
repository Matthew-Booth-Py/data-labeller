import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Loader2, PlayCircle } from "lucide-react";
import { api } from "@/lib/api";

type ExtractedField = {
  field_name: string;
  value: unknown;
  confidence?: number;
};

export function ExtractionRunner({ projectId }: { projectId?: string }) {
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");
  const [useStructuredOutput, setUseStructuredOutput] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [fields, setFields] = useState<ExtractedField[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await api.listDocuments();
        setDocuments(response.documents || []);
        if (response.documents?.length) setSelectedDocumentId(response.documents[0].id);
      } catch (e: any) {
        setError(e.message || "Failed to load documents");
      }
    };
    load();
  }, []);

  const selectedDoc = useMemo(
    () => documents.find((d) => d.id === selectedDocumentId),
    [documents, selectedDocumentId]
  );

  const runExtraction = async () => {
    if (!selectedDocumentId) return;
    setIsRunning(true);
    setError(null);
    setFields([]);
    try {
      const response = await fetch(
        `/api/v1/documents/${selectedDocumentId}/extract?use_llm=${String(!useStructuredOutput)}&use_structured_output=${String(useStructuredOutput)}`,
        { method: "POST" }
      );
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || "Extraction failed");
      }
      const data = await response.json();
      setFields(data.fields || []);
    } catch (e: any) {
      setError(e.message || "Extraction failed");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Live Extraction Runner</CardTitle>
          <CardDescription>
            Runs real extraction against a stored document.
            {projectId ? <> Project ID: <span className="font-mono">{projectId}</span></> : null}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2 md:col-span-2">
              <Label>Document</Label>
              <Select value={selectedDocumentId} onValueChange={setSelectedDocumentId}>
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
              <Label>Mode</Label>
              <div className="flex items-center gap-2 rounded-md border px-3 py-2 h-10">
                <Switch checked={useStructuredOutput} onCheckedChange={setUseStructuredOutput} />
                <span className="text-sm">{useStructuredOutput ? "Structured output" : "Annotation refinement"}</span>
              </div>
            </div>
          </div>

          <Button onClick={runExtraction} disabled={!selectedDocumentId || isRunning} className="gap-2">
            {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
            Run Extraction
          </Button>
        </CardContent>
      </Card>

      {selectedDoc && (
        <Card>
          <CardHeader>
            <CardTitle>Document</CardTitle>
            <CardDescription>{selectedDoc.filename}</CardDescription>
          </CardHeader>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Extracted Fields</CardTitle>
          <CardDescription>Real extraction output from backend.</CardDescription>
        </CardHeader>
        <CardContent>
          {error ? <div className="text-sm text-red-600">{error}</div> : null}
          {!error && fields.length === 0 ? (
            <div className="text-sm text-muted-foreground">No extraction results yet.</div>
          ) : null}
          {fields.length > 0 ? (
            <div className="space-y-3">
              {fields.map((field) => (
                <div key={field.field_name} className="rounded-md border p-3">
                  <div className="text-xs uppercase text-muted-foreground">{field.field_name}</div>
                  <pre className="text-sm whitespace-pre-wrap break-all">{JSON.stringify(field.value, null, 2)}</pre>
                </div>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

