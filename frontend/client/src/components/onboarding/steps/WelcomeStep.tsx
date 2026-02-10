import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  FileText,
  Tag,
  Wand2,
  Brain,
  CheckCircle2,
  Loader2,
  Play,
  Target,
  ArrowRight,
} from "lucide-react";

interface WelcomeStepProps {
  onSetup: () => void;
  isSettingUp: boolean;
  isSetup: boolean;
}

export function WelcomeStep({ onSetup, isSettingUp, isSetup }: WelcomeStepProps) {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Hero section */}
      <div className="text-center space-y-4">
        <h2 className="text-3xl font-bold">Welcome to Unstructured Unlocked</h2>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          Learn how to classify, label, and extract structured data from your documents
          using AI-powered tools.
        </p>
      </div>

      {/* What you'll learn */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5 text-primary" />
            What You'll Learn
          </CardTitle>
          <CardDescription>
            Complete this tutorial to master the core features
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-start gap-3 p-4 rounded-lg border bg-muted/30">
              <div className="p-2 rounded-md bg-blue-500/10">
                <FileText className="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <h4 className="font-medium">Document Classification</h4>
                <p className="text-sm text-muted-foreground">
                  Organize documents by type (claims, policies, invoices)
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-lg border bg-muted/30">
              <div className="p-2 rounded-md bg-emerald-500/10">
                <Tag className="h-5 w-5 text-emerald-500" />
              </div>
              <div>
                <h4 className="font-medium">Annotation & Labeling</h4>
                <p className="text-sm text-muted-foreground">
                  Mark and label key information in documents
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-lg border bg-muted/30">
              <div className="p-2 rounded-md bg-purple-500/10">
                <Wand2 className="h-5 w-5 text-purple-500" />
              </div>
              <div>
                <h4 className="font-medium">AI Auto-Classification</h4>
                <p className="text-sm text-muted-foreground">
                  Let AI automatically classify your documents
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-lg border bg-muted/30">
              <div className="p-2 rounded-md bg-amber-500/10">
                <Brain className="h-5 w-5 text-amber-500" />
              </div>
              <div>
                <h4 className="font-medium">Smart Suggestions</h4>
                <p className="text-sm text-muted-foreground">
                  Get AI-powered label suggestions as you work
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Sample documents info */}
      <Card>
        <CardHeader>
          <CardTitle>Sample Insurance Documents</CardTitle>
          <CardDescription>
            We'll use 6 realistic insurance documents for hands-on practice
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {[
              { name: "Auto Claim Form", type: "Claim Form" },
              { name: "Property Claim Form", type: "Claim Form" },
              { name: "Homeowners Policy", type: "Policy" },
              { name: "Theft Loss Report", type: "Loss Report" },
              { name: "Repair Invoice", type: "Invoice" },
              { name: "Medical Invoice", type: "Invoice" },
            ].map((doc, i) => (
              <div key={i} className="flex items-center gap-2 p-2 rounded border">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{doc.name}</div>
                  <Badge variant="secondary" className="text-xs">
                    {doc.type}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Start button */}
      <div className="flex justify-center">
        {isSetup ? (
          <div className="flex items-center gap-2 text-emerald-600">
            <CheckCircle2 className="h-5 w-5" />
            <span className="font-medium">Tutorial is ready! Click "Next" to continue.</span>
          </div>
        ) : (
          <Button size="lg" onClick={onSetup} disabled={isSettingUp} className="gap-2">
            {isSettingUp ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Setting up tutorial...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Set Up Sample Data
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
