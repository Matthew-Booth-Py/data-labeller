import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Tag, Lightbulb, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { useLocation } from "wouter";

interface CreateLabelsStepProps {
  onComplete: () => void;
}

export function CreateLabelsStep({ onComplete }: CreateLabelsStepProps) {
  const [, setLocation] = useLocation();

  const { data: docTypesResponse } = useQuery({
    queryKey: ["document-types"],
    queryFn: async () => {
      try {
        return await api.listDocumentTypes();
      } catch (error) {
        console.error("Failed to fetch document types:", error);
        return { types: [], total: 0 };
      }
    },
  });

  const docTypes = docTypesResponse?.types || [];
  const claimForm = docTypes.find((type) => type.name === "Insurance Claim Form") || docTypes[0];
  const derivedFields = claimForm?.schema_fields || [];
  const hasDerivedLabels = derivedFields.length > 0;

  return (
    <div className="space-y-6">
      <Alert className="bg-blue-500/10 border-blue-500/20">
        <Lightbulb className="h-4 w-4 text-blue-500" />
        <AlertDescription className="text-blue-700 dark:text-blue-300">
          <strong>Labels are schema-derived.</strong> In the current workflow, labels come directly from
          your schema fields. You do not create labels separately. To add a new label, add a field in:
          <strong> Schema to Document Types to Fields Definition to Add Field</strong>.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Current Schema-Derived Labels</CardTitle>
          <CardDescription>
            These come from the selected document type fields and are synced automatically.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {claimForm ? (
            <>
              <p className="text-sm text-muted-foreground">
                Document type: <span className="font-medium text-foreground">{claimForm.name}</span>
              </p>
              <div className="flex flex-wrap gap-2">
                {derivedFields.map((field) => (
                  <Badge key={field.name} variant="outline">
                    {field.name}
                  </Badge>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              No document types found yet.
            </p>
          )}
          <Button variant="outline" onClick={() => setLocation("/project/tutorial#schema")}>
            Open Schema (Add Field)
            <ArrowRight className="h-4 w-4 ml-2" />
          </Button>
        </CardContent>
      </Card>

      {hasDerivedLabels ? (
        <div className="flex items-center justify-center gap-2 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          <span className="font-medium text-emerald-700 dark:text-emerald-300">
            Schema labels are ready! Click "Next" to start annotating.
          </span>
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Fields Not Found</CardTitle>
            <CardDescription>
              Add fields in Schema first. Labels are generated from those fields automatically.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Use the Add Field dialog and optionally AI Field Assistant to define fields quickly.
            </p>
            <Button variant="outline" onClick={() => setLocation("/project/tutorial#schema")}>
              Open Schema (Add Field)
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
