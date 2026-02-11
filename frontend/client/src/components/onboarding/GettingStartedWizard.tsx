import { useState, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import {
  CheckCircle2,
  Circle,
  ChevronRight,
  ChevronLeft,
  Loader2,
  BookOpen,
  FileText,
  Tag,
  Wand2,
  Sparkles,
  Brain,
  GraduationCap,
  FolderOpen,
  Target,
  RotateCcw,
} from "lucide-react";
import { api } from "@/lib/api";

// Step components
import {
  WelcomeStep,
  CreateTypesStep,
  ExploreDocumentsStep,
  ClassifyDocumentStep,
  AutoClassifyStep,
  CreateLabelsStep,
  AnnotateDocumentStep,
  GetSuggestionsStep,
  CompleteStep,
} from "./steps";

interface GettingStartedWizardProps {
  onComplete?: () => void;
}

interface WizardStep {
  id: string;
  title: string;
  description: string;
  icon: React.ElementType;
  objective: string;
}

const WIZARD_STEPS: WizardStep[] = [
  {
    id: "welcome",
    title: "Welcome",
    description: "Get started with Unstructured Unlocked",
    icon: BookOpen,
    objective: "Learn what you'll accomplish in this tutorial",
  },
  {
    id: "create-types",
    title: "Schema Setup",
    description: "Set document types and field schemas",
    icon: FolderOpen,
    objective: "In Schema Configuration → Fields Definition, click Add Field and use AI Field Assistant",
  },
  {
    id: "explore-docs",
    title: "Upload / Review Docs",
    description: "Review uploaded documents",
    icon: FileText,
    objective: "Confirm documents are ingested and ready for labeling",
  },
  {
    id: "classify",
    title: "Manual Classification",
    description: "Classify one document manually",
    icon: Target,
    objective: "Set the baseline document type by hand",
  },
  {
    id: "auto-classify",
    title: "LLM Classification",
    description: "Classify with AI",
    icon: Wand2,
    objective: "Use the LLM to classify additional documents by type",
  },
  {
    id: "create-labels",
    title: "Schema Labels",
    description: "Review schema-derived labels",
    icon: Tag,
    objective: "Verify labels are generated directly from your field definitions",
  },
  {
    id: "annotate",
    title: "Annotate",
    description: "Create ground truth",
    icon: Sparkles,
    objective: "Label key spans and values in the selected document",
  },
  {
    id: "suggestions",
    title: "AI Suggestions",
    description: "Assist annotation with AI",
    icon: Brain,
    objective: "Apply and edit AI suggestions to speed up labeling",
  },
  {
    id: "complete",
    title: "Done",
    description: "Run extraction and finish",
    icon: GraduationCap,
    objective: "Run extraction, inspect raw output, then finish the pipeline",
  },
];

// Local storage key for tutorial progress
const TUTORIAL_PROGRESS_KEY = "uu-tutorial-progress";

interface TutorialProgress {
  started: boolean;
  currentStep: number;
  completedSteps: string[];
  documentIds: string[];
  typeIds: string[];
  labelIds: string[];
  selectedDocumentId: string | null;
}

function loadProgress(): TutorialProgress {
  try {
    const saved = localStorage.getItem(TUTORIAL_PROGRESS_KEY);
    if (saved) {
      return JSON.parse(saved);
    }
  } catch (e) {
    console.error("Failed to load tutorial progress:", e);
  }
  return {
    started: false,
    currentStep: 0,
    completedSteps: [],
    documentIds: [],
    typeIds: [],
    labelIds: [],
    selectedDocumentId: null,
  };
}

function saveProgress(progress: TutorialProgress) {
  try {
    localStorage.setItem(TUTORIAL_PROGRESS_KEY, JSON.stringify(progress));
  } catch (e) {
    console.error("Failed to save tutorial progress:", e);
  }
}

export function GettingStartedWizard({ onComplete }: GettingStartedWizardProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [progress, setProgress] = useState<TutorialProgress>(loadProgress);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(() => {
    const saved = loadProgress();
    return saved.selectedDocumentId;
  });
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Fetch tutorial status
  const { data: tutorialStatus, refetch: refetchStatus, error: statusError } = useQuery({
    queryKey: ["tutorial-status"],
    queryFn: async () => {
      try {
        return await api.getTutorialStatus();
      } catch (error) {
        console.error("Failed to fetch tutorial status:", error);
        // Return default status on error
        return {
          is_setup: false,
          document_count: 0,
          document_type_count: 0,
          label_count: 0,
          sample_document_ids: [],
        };
      }
    },
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Fetch docs to validate any persisted selected document id
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
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Keep selected document in sync with actual ingested docs
  useEffect(() => {
    const docs = documentsResponse?.documents ?? [];
    if (!docs.length || !selectedDocumentId) {
      return;
    }
    const exists = docs.some((doc) => doc.id === selectedDocumentId);
    if (exists) {
      return;
    }

    const fallback =
      docs.find(
        (d) =>
          d.filename &&
          d.filename.includes("2024.pdf") &&
          (d.filename.includes("claim") ||
            d.filename.includes("policy") ||
            d.filename.includes("loss") ||
            d.filename.includes("vendor"))
      ) ?? docs[0];

    const nextSelected = fallback?.id ?? null;
    setSelectedDocumentId(nextSelected);
    const newProgress = { ...progress, selectedDocumentId: nextSelected };
    setProgress(newProgress);
    saveProgress(newProgress);
  }, [documentsResponse?.documents, selectedDocumentId, progress]);

  // Setup tutorial mutation
  const setupMutation = useMutation({
    mutationFn: () => api.setupTutorial(),
    onSuccess: (result) => {
      // Create a tutorial project in localStorage
      const tutorialProject = {
        id: 'tutorial',
        name: 'Tutorial Project',
        description: 'Sample insurance documents for the Getting Started tutorial',
        type: 'Insurance',
        docCount: result.document_ids.length,
        model: 'gpt-5-mini',
      };
      
      // Save to localStorage
      const projects = JSON.parse(localStorage.getItem('uu-projects') || '[]');
      const existingIndex = projects.findIndex((p: any) => p.id === 'tutorial');
      if (existingIndex >= 0) {
        projects[existingIndex] = { ...tutorialProject, documentIds: result.document_ids };
      } else {
        projects.push({ ...tutorialProject, documentIds: result.document_ids });
      }
      localStorage.setItem('uu-projects', JSON.stringify(projects));
      
      const newProgress = {
        ...progress,
        started: true,
        documentIds: result.document_ids,
        typeIds: result.document_type_ids,
        labelIds: result.label_ids,
      };
      setProgress(newProgress);
      saveProgress(newProgress);
      refetchStatus();
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["document-types"] });
      queryClient.invalidateQueries({ queryKey: ["labels"] });
      toast({
        title: "Tutorial Ready",
        description: result.message,
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Setup Failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Reset tutorial mutation
  const resetMutation = useMutation({
    mutationFn: () => api.resetTutorial(),
    onSuccess: () => {
      const newProgress = loadProgress();
      newProgress.started = false;
      newProgress.currentStep = 0;
      newProgress.completedSteps = [];
      newProgress.selectedDocumentId = null;
      setProgress(newProgress);
      saveProgress(newProgress);
      setCurrentStep(0);
      setSelectedDocumentId(null);
      refetchStatus();
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast({
        title: "Tutorial Reset",
        description: "You can start the tutorial again from the beginning.",
      });
    },
  });

  // Initialize from saved progress
  useEffect(() => {
    const saved = loadProgress();
    setProgress(saved);
    if (saved.currentStep > 0) {
      setCurrentStep(saved.currentStep);
    }
  }, []);

  // Save progress whenever currentStep changes
  useEffect(() => {
    if (currentStep > 0) {
      const newProgress = { ...progress, currentStep };
      setProgress(newProgress);
      saveProgress(newProgress);
    }
  }, [currentStep]);

  // Mark step as complete
  const completeStep = useCallback((stepId: string) => {
    const newProgress = {
      ...progress,
      completedSteps: [...new Set([...progress.completedSteps, stepId])],
    };
    setProgress(newProgress);
    saveProgress(newProgress);
  }, [progress]);

  // Navigate to next step
  const nextStep = useCallback(() => {
    if (currentStep < WIZARD_STEPS.length - 1) {
      const stepId = WIZARD_STEPS[currentStep].id;
      completeStep(stepId);
      const newStep = currentStep + 1;
      setCurrentStep(newStep);
      const newProgress = { ...progress, currentStep: newStep };
      saveProgress(newProgress);
    }
  }, [currentStep, completeStep, progress]);

  // Navigate to previous step
  const prevStep = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  }, [currentStep]);

  // Handle completion
  const handleComplete = useCallback(() => {
    completeStep("complete");
    onComplete?.();
  }, [completeStep, onComplete]);

  const step = WIZARD_STEPS[currentStep];
  const progressPercent = ((currentStep) / (WIZARD_STEPS.length - 1)) * 100;

  // Render the current step content
  const renderStepContent = () => {
    switch (step.id) {
      case "welcome":
        return (
          <WelcomeStep
            onSetup={() => setupMutation.mutate()}
            isSettingUp={setupMutation.isPending}
            isSetup={tutorialStatus?.is_setup ?? false}
          />
        );
      case "create-types":
        return <CreateTypesStep onComplete={() => completeStep("create-types")} />;
      case "explore-docs":
        return (
          <ExploreDocumentsStep
            onSelectDocument={(docId) => {
              setSelectedDocumentId(docId);
              const newProgress = { ...progress, selectedDocumentId: docId };
              setProgress(newProgress);
              saveProgress(newProgress);
            }}
            selectedDocumentId={selectedDocumentId}
          />
        );
      case "classify":
        return (
          <ClassifyDocumentStep
            documentId={selectedDocumentId}
            onComplete={() => completeStep("classify")}
          />
        );
      case "auto-classify":
        return (
          <AutoClassifyStep
            onComplete={() => completeStep("auto-classify")}
          />
        );
      case "create-labels":
        return <CreateLabelsStep onComplete={() => completeStep("create-labels")} />;
      case "annotate":
        return (
          <AnnotateDocumentStep
            documentId={selectedDocumentId}
            onComplete={() => completeStep("annotate")}
          />
        );
      case "suggestions":
        return (
          <GetSuggestionsStep
            documentId={selectedDocumentId}
            onComplete={() => completeStep("suggestions")}
          />
        );
      case "complete":
        return <CompleteStep onComplete={handleComplete} />;
      default:
        return null;
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 py-4 border-b bg-background">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold">Getting Started</h1>
            <p className="text-muted-foreground text-sm">
              Workflow: upload docs, Add Field with AI Field Assistant, classify (manual + LLM), annotate, extract raw output
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => resetMutation.mutate()}
            disabled={resetMutation.isPending}
            className="gap-2"
          >
            <RotateCcw className="h-4 w-4" />
            Reset Tutorial
          </Button>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Progress</span>
            <span className="font-medium">{Math.round(progressPercent)}%</span>
          </div>
          <Progress value={progressPercent} className="h-2" />
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Step sidebar */}
        <div className="w-72 border-r bg-muted/20 p-4 overflow-auto">
          <div className="space-y-1">
            {WIZARD_STEPS.map((s, index) => {
              const isComplete = progress.completedSteps.includes(s.id);
              const isCurrent = index === currentStep;
              const Icon = s.icon;

              return (
                <button
                  key={s.id}
                  onClick={() => setCurrentStep(index)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                    isCurrent
                      ? "bg-primary/10 text-primary"
                      : isComplete
                      ? "text-muted-foreground hover:bg-muted"
                      : "text-muted-foreground/60 hover:bg-muted/50"
                  }`}
                >
                  <div className="flex-shrink-0">
                    {isComplete ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                    ) : isCurrent ? (
                      <Icon className="h-5 w-5" />
                    ) : (
                      <Circle className="h-5 w-5" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className={`text-sm font-medium truncate ${isCurrent ? "" : ""}`}>
                      {s.title}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      {s.description}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Step content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Step header */}
          <div className="px-6 py-4 border-b bg-gradient-to-r from-primary/5 to-transparent">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <step.icon className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">{step.title}</h2>
                <p className="text-sm text-muted-foreground">{step.description}</p>
              </div>
            </div>
            {/* Objective banner */}
            <div className="mt-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-amber-600" />
                <span className="text-sm font-medium text-amber-700 dark:text-amber-400">
                  Objective:
                </span>
                <span className="text-sm text-amber-600 dark:text-amber-300">
                  {step.objective}
                </span>
              </div>
            </div>
          </div>

          {/* Step content area */}
          <div className="flex-1 overflow-auto p-6">
            {renderStepContent()}
          </div>

          {/* Navigation footer */}
          <div className="px-6 py-4 border-t bg-background flex items-center justify-between">
            <Button
              variant="outline"
              onClick={prevStep}
              disabled={currentStep === 0}
              className="gap-2"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>

            <div className="flex items-center gap-2">
              {WIZARD_STEPS.map((_, index) => (
                <div
                  key={index}
                  className={`w-2 h-2 rounded-full transition-colors ${
                    index === currentStep
                      ? "bg-primary"
                      : progress.completedSteps.includes(WIZARD_STEPS[index].id)
                      ? "bg-emerald-500"
                      : "bg-muted"
                  }`}
                />
              ))}
            </div>

            <Button
              onClick={currentStep === WIZARD_STEPS.length - 1 ? handleComplete : nextStep}
              className="gap-2"
            >
              {currentStep === WIZARD_STEPS.length - 1 ? (
                <>
                  Finish
                  <CheckCircle2 className="h-4 w-4" />
                </>
              ) : (
                <>
                  Next
                  <ChevronRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
