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

  // Fetch labels
  const { data: labelsResponse } = useQuery({
    queryKey: ["labels"],
    queryFn: async () => {
      try {
        return await api.listLabels();
      } catch (error) {
        console.error("Failed to fetch labels:", error);
        return [];
      }
    },
  });

  const labels = Array.isArray(labelsResponse) ? labelsResponse : [];

  const expectedLabels = [
    { name: "Claim Number", color: "#ef4444", description: "Unique identifier for insurance claims" },
    { name: "Policy Number", color: "#f97316", description: "Insurance policy identifier" },
    { name: "Person Name", color: "#3b82f6", description: "Names of individuals" },
    { name: "Date", color: "#10b981", description: "Any significant date" },
    { name: "Amount", color: "#8b5cf6", description: "Monetary values" },
  ];

  const hasLabels = labels && labels.length >= 5;

  return (
    <div className="space-y-6">
      <Alert className="bg-blue-500/10 border-blue-500/20">
        <Lightbulb className="h-4 w-4 text-blue-500" />
        <AlertDescription className="text-blue-700 dark:text-blue-300">
          <strong>What are labels?</strong> Labels (also called "fields") define what information you want to extract.
          For example, "Claim Number" or "Policy Number". You'll use these labels to highlight and tag text in your documents.
          The tutorial automatically created 5 common insurance labels for you.
        </AlertDescription>
      </Alert>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {expectedLabels.map((label, i) => {
          const exists = Array.isArray(labels) && labels.some(l => l.name === label.name);
          return (
            <Card key={i} className={exists ? "border-emerald-500/50 bg-emerald-500/5" : ""}>
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <div
                    className="w-4 h-4 rounded-full flex-shrink-0 mt-0.5"
                    style={{ backgroundColor: label.color }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{label.name}</span>
                      {exists && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {label.description}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Additional labels that were created */}
      {labels && labels.length > 5 && (
        <div className="flex flex-wrap gap-2">
          <span className="text-sm text-muted-foreground">Additional labels:</span>
          {labels.slice(5).map((label) => (
            <Badge
              key={label.id}
              variant="outline"
              style={{ borderColor: label.color, color: label.color }}
            >
              {label.name}
            </Badge>
          ))}
        </div>
      )}

      {hasLabels ? (
        <div className="flex items-center justify-center gap-2 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          <span className="font-medium text-emerald-700 dark:text-emerald-300">
            Labels are ready! Click "Next" to start annotating.
          </span>
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Labels Not Found</CardTitle>
            <CardDescription>
              The tutorial should have created these labels automatically. If you don't see them,
              go back to the Welcome step and click "Set Up Sample Data" to initialize the tutorial.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              In a real project, you would create labels in the Fields Library to match the information
              you want to extract from your documents.
            </p>
            <Button variant="outline" onClick={() => setLocation("/fields-library")}>
              Open Fields Library
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
