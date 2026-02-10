import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  GraduationCap,
  FileText,
  Tag,
  Wand2,
  Brain,
  ArrowRight,
  Sparkles,
  Rocket,
  BookOpen,
} from "lucide-react";
import { useLocation, Link } from "wouter";

interface CompleteStepProps {
  onComplete: () => void;
}

export function CompleteStep({ onComplete }: CompleteStepProps) {
  const [, setLocation] = useLocation();

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Celebration header */}
      <div className="text-center space-y-4">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-emerald-500/10">
          <GraduationCap className="h-10 w-10 text-emerald-500" />
        </div>
        <h2 className="text-3xl font-bold">Congratulations!</h2>
        <p className="text-lg text-muted-foreground max-w-xl mx-auto">
          You've completed the Getting Started tutorial and learned the core features
          of Unstructured Unlocked.
        </p>
      </div>

      {/* What you learned */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            What You Learned
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="h-5 w-5 text-emerald-500 mt-0.5" />
              <div>
                <div className="font-medium">Document Types</div>
                <p className="text-sm text-muted-foreground">
                  Create schemas to categorize documents
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle2 className="h-5 w-5 text-emerald-500 mt-0.5" />
              <div>
                <div className="font-medium">Document Classification</div>
                <p className="text-sm text-muted-foreground">
                  Manually and automatically classify documents
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle2 className="h-5 w-5 text-emerald-500 mt-0.5" />
              <div>
                <div className="font-medium">Annotation Labels</div>
                <p className="text-sm text-muted-foreground">
                  Define labels for data extraction
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle2 className="h-5 w-5 text-emerald-500 mt-0.5" />
              <div>
                <div className="font-medium">AI Suggestions</div>
                <p className="text-sm text-muted-foreground">
                  Get AI-powered annotation suggestions
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Next steps */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Rocket className="h-5 w-5 text-primary" />
            What's Next
          </CardTitle>
          <CardDescription>
            Continue exploring and scaling your document processing
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-start gap-4 p-4 rounded-lg border bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                 onClick={() => setLocation("/project/tutorial")}>
              <div className="p-2 rounded-lg bg-blue-500/10">
                <FileText className="h-5 w-5 text-blue-500" />
              </div>
              <div className="flex-1">
                <div className="font-medium">Upload Your Documents</div>
                <p className="text-sm text-muted-foreground">
                  Start processing your own documents. The system learns from each annotation.
                </p>
              </div>
              <ArrowRight className="h-5 w-5 text-muted-foreground" />
            </div>

            <div className="flex items-start gap-4 p-4 rounded-lg border bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                 onClick={() => setLocation("/project/tutorial/schema")}>
              <div className="p-2 rounded-lg bg-purple-500/10">
                <Tag className="h-5 w-5 text-purple-500" />
              </div>
              <div className="flex-1">
                <div className="font-medium">Customize Your Schema</div>
                <p className="text-sm text-muted-foreground">
                  Add new document types and labels specific to your use case.
                </p>
              </div>
              <ArrowRight className="h-5 w-5 text-muted-foreground" />
            </div>

            <div className="flex items-start gap-4 p-4 rounded-lg border bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                 onClick={() => setLocation("/project/tutorial/search")}>
              <div className="p-2 rounded-lg bg-amber-500/10">
                <Brain className="h-5 w-5 text-amber-500" />
              </div>
              <div className="flex-1">
                <div className="font-medium">Search & Ask Questions</div>
                <p className="text-sm text-muted-foreground">
                  Use semantic search and Q&A to find information across your documents.
                </p>
              </div>
              <ArrowRight className="h-5 w-5 text-muted-foreground" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tips for scaling */}
      <Card className="border-primary/20 bg-primary/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Tips for Scaling
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            <li className="flex items-start gap-2 text-sm">
              <span className="text-primary">•</span>
              <span>
                <strong>Aim for 20+ annotations per label</strong> - This triggers ML model training for faster, more accurate suggestions.
              </span>
            </li>
            <li className="flex items-start gap-2 text-sm">
              <span className="text-primary">•</span>
              <span>
                <strong>Be consistent with labeling</strong> - Use the same label for similar content across documents.
              </span>
            </li>
            <li className="flex items-start gap-2 text-sm">
              <span className="text-primary">•</span>
              <span>
                <strong>Use auto-classification</strong> - Let AI classify documents first, then verify and correct.
              </span>
            </li>
            <li className="flex items-start gap-2 text-sm">
              <span className="text-primary">•</span>
              <span>
                <strong>Review suggestions</strong> - Accept good suggestions to speed up annotation and improve the model.
              </span>
            </li>
          </ul>
        </CardContent>
      </Card>

      {/* CTA */}
      <div className="flex justify-center gap-4">
        <Button variant="outline" onClick={() => setLocation("/")}>
          <BookOpen className="h-4 w-4 mr-2" />
          Back to Dashboard
        </Button>
        <Button onClick={() => navigate("/project/tutorial")} className="gap-2">
          Go to Workspace
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
