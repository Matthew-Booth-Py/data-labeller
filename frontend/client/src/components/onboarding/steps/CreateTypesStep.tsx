import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle2, FolderOpen, Lightbulb, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { useLocation } from "wouter";
import { Button } from "@/components/ui/button";

interface CreateTypesStepProps {
  onComplete: () => void;
}

export function CreateTypesStep({ onComplete }: CreateTypesStepProps) {
  const [, setLocation] = useLocation();

  // Fetch document types
  const { data: documentTypesResponse } = useQuery({
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

  const documentTypes = Array.isArray(documentTypesResponse?.types) ? documentTypesResponse.types : [];

  const expectedTypes = [
    { name: "Insurance Claim Form", description: "Forms submitted by policyholders to report a loss" },
    { name: "Policy Document", description: "Insurance policy declarations and coverage documents" },
    { name: "Loss Report", description: "Detailed reports documenting theft, damage, or other loss events" },
    { name: "Vendor Invoice", description: "Invoices from repair shops, medical providers, and vendors" },
  ];

  const hasTypes = documentTypes && documentTypes.length >= 4;

  return (
    <div className="space-y-6">
      <Alert className="bg-blue-500/10 border-blue-500/20">
        <Lightbulb className="h-4 w-4 text-blue-500" />
        <AlertDescription className="text-blue-700 dark:text-blue-300">
          Document types define the categories of documents you'll process. Each type can have
          its own schema with specific fields to extract.
        </AlertDescription>
      </Alert>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {expectedTypes.map((type, i) => {
          const exists = Array.isArray(documentTypes) && documentTypes.some(dt => dt.name === type.name);
          return (
            <Card key={i} className={exists ? "border-emerald-500/50 bg-emerald-500/5" : ""}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  {exists ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                  ) : (
                    <FolderOpen className="h-5 w-5 text-muted-foreground" />
                  )}
                  {type.name}
                </CardTitle>
                <CardDescription className="text-sm">
                  {type.description}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Badge variant={exists ? "default" : "secondary"}>
                  {exists ? "Created" : "To Create"}
                </Badge>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {hasTypes ? (
        <div className="flex items-center justify-center gap-2 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          <span className="font-medium text-emerald-700 dark:text-emerald-300">
            All document types are ready! Click "Next" to continue.
          </span>
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Create Document Types</CardTitle>
            <CardDescription>
              The tutorial has already created these types for you. If you don't see them,
              go back to the Welcome step and click "Set Up Sample Data".
            </CardDescription>
          </CardHeader>
          <CardContent className="flex gap-4">
            <Button variant="outline" onClick={() => setLocation("/project/tutorial/schema")}>
              Open Schema Manager
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
