import { Shell } from "@/components/layout/Shell";
import { useParams } from "wouter";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RotateCcw, AlertTriangle, CheckCircle2, Save, Key } from "lucide-react";
import { useState, useCallback, useMemo, useEffect } from "react";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

import { DocumentPool } from "@/components/workspace/DocumentPool";
import { SchemaViewer } from "@/components/workspace/SchemaViewer";
import { LabelStudio } from "@/components/workspace/LabelStudio";
import { LabeledDataViewer } from "@/components/workspace/LabeledDataViewer";
import { EvaluationBoard } from "@/components/workspace/EvaluationBoard";
import { DeploymentView } from "@/components/workspace/DeploymentView";
import { DriftMap } from "@/components/workspace/DriftMap";
import { APIManagement } from "@/components/workspace/APIManagement";
import { Timeline } from "@/components/workspace/Timeline";
import { SearchPanel } from "@/components/workspace/SearchPanel";
import { ExtractionRunner } from "@/components/workspace/ExtractionRunner";

interface Project {
  id: string;
  name: string;
  description?: string;
  type?: string;
  coverage?: number;
  lastEval?: string;
  driftRisk?: "Low" | "Medium" | "High" | "Unknown";
  docCount?: number;
  model?: string;
}

export default function ProjectWorkspace() {
  const { id } = useParams();
  const { toast } = useToast();
  const validTabs = new Set([
    "schema",
    "documents",
    "label",
    "labeled-data",
    "evaluation",
    "extraction",
    "timeline",
    "search",
    "drift",
    "api",
    "deployment",
  ]);
  
  // Get tab from URL hash or default to "documents"
  const getTabFromUrl = () => {
    const hash = window.location.hash.slice(1); // Remove the '#'
    if (!hash) return "documents";
    return validTabs.has(hash) ? hash : "documents";
  };
  
  const [activeTab, setActiveTab] = useState(getTabFromUrl());
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [savingDeploymentVersion, setSavingDeploymentVersion] = useState(false);
  const [liveMetrics, setLiveMetrics] = useState<{
    coverage: number;
    lastEval: string;
    driftRisk: "Low" | "Medium" | "High" | "Unknown";
  }>({
    coverage: 0,
    lastEval: "Never",
    driftRisk: "Unknown",
  });

  // Update URL hash when tab changes
  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    window.location.hash = tab;
  };

  // Listen for hash changes (e.g., browser back/forward)
  useEffect(() => {
    const handleHashChange = () => {
      setActiveTab(getTabFromUrl());
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Load project from localStorage
  const project = useMemo<Project>(() => {
    try {
      const stored = localStorage.getItem("uu-projects");
      if (stored) {
        const projects: Project[] = JSON.parse(stored);
        const found = projects.find((p) => p.id === id);
        if (found) return found;
      }
    } catch {
      // Ignore parse errors
    }
    
    // Special case: if this is the tutorial project and it doesn't exist, create it
    if (id === "tutorial") {
      return {
        id: "tutorial",
        name: "Tutorial Project",
        description: "Sample insurance documents for the Getting Started tutorial",
        type: "Insurance",
        coverage: 0,
        driftRisk: "Low",
        docCount: 0,
        model: "GPT-5-mini",
        documentIds: [],
      };
    }
    
    // Return a default project with the URL id
    return {
      id: id || "unknown",
      name: id ? id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "Project",
      description: "",
      coverage: 0,
      driftRisk: "Low",
      docCount: 0,
      model: "GPT-5-mini",
    };
  }, [id]);

  const handleDocumentClick = useCallback((docId: string) => {
    setSelectedDocumentId(docId);
    setActiveTab("label");
  }, []);

  useEffect(() => {
    const persistProjectMetrics = (coverage: number, lastEval: string, driftRisk: "Low" | "Medium" | "High" | "Unknown") => {
      if (!id) return;
      try {
        const stored = localStorage.getItem("uu-projects");
        if (!stored) return;
        const projects = JSON.parse(stored);
        const idx = projects.findIndex((p: any) => p.id === id);
        if (idx < 0) return;
        projects[idx] = {
          ...projects[idx],
          coverage,
          lastEval,
          driftRisk,
        };
        localStorage.setItem("uu-projects", JSON.stringify(projects));
      } catch {
        // ignore persistence errors
      }
    };

    const loadLiveMetrics = async () => {
      if (!id) return;
      let documentIds: string[] = [];
      try {
        const stored = localStorage.getItem("uu-projects");
        if (stored) {
          const projects = JSON.parse(stored);
          const found = projects.find((p: any) => p.id === id);
          documentIds = found?.documentIds || [];
        }
      } catch {
        documentIds = [];
      }

      const docCount = documentIds.length;
      if (docCount === 0) {
        const next = { coverage: 0, lastEval: "Never", driftRisk: "Unknown" as const };
        setLiveMetrics(next);
        persistProjectMetrics(next.coverage, next.lastEval, next.driftRisk);
        return;
      }

      try {
        const response = await api.listEvaluations({ limit: 1000 });
        const docSet = new Set(documentIds);
        const projectEvals = (response.evaluations || []).filter((e: any) => docSet.has(e.document_id));
        const evaluatedDocs = new Set(projectEvals.map((e: any) => e.document_id));
        const coverage = Math.round((evaluatedDocs.size / docCount) * 100);

        const latestEval = projectEvals
          .map((e: any) => e.evaluated_at)
          .filter(Boolean)
          .sort((a: string, b: string) => new Date(b).getTime() - new Date(a).getTime())[0];

        const sortedByDate = [...projectEvals].sort(
          (a: any, b: any) => new Date(a.evaluated_at).getTime() - new Date(b.evaluated_at).getTime()
        );
        const f1Series = sortedByDate
          .map((e: any) => Number(e.metrics?.f1_score ?? 0))
          .filter((v: number) => Number.isFinite(v));

        let driftRisk: "Low" | "Medium" | "High" | "Unknown" = "Unknown";
        if (f1Series.length >= 2) {
          const recent = f1Series.slice(-5);
          const previous = f1Series.slice(-10, -5);
          const avg = (arr: number[]) => (arr.length ? arr.reduce((s, x) => s + x, 0) / arr.length : 0);
          const recentAvg = avg(recent);
          const previousAvg = previous.length ? avg(previous) : recentAvg;
          const delta = Math.abs(recentAvg - previousAvg);
          if (recentAvg < 0.75 || delta > 0.15) driftRisk = "High";
          else if (recentAvg < 0.9 || delta > 0.08) driftRisk = "Medium";
          else driftRisk = "Low";
        }

        const next = {
          coverage,
          lastEval: latestEval ? new Date(latestEval).toLocaleString() : "Never",
          driftRisk,
        };
        setLiveMetrics(next);
        persistProjectMetrics(next.coverage, next.lastEval, next.driftRisk);
      } catch {
        const next = { coverage: 0, lastEval: "Never", driftRisk: "Unknown" as const };
        setLiveMetrics(next);
        persistProjectMetrics(next.coverage, next.lastEval, next.driftRisk);
      }
    };

    loadLiveMetrics();
  }, [id]);

  const handleCreateDeploymentVersion = async () => {
    if (!id) return;
    setSavingDeploymentVersion(true);
    try {
      const selectedTypeStorageKey = `uu-schema-selected-type:${id}`;
      let documentTypeId = "";
      try {
        documentTypeId = localStorage.getItem(selectedTypeStorageKey) || "";
      } catch {
        documentTypeId = "";
      }
      if (!documentTypeId) {
        const types = await api.listDocumentTypes();
        documentTypeId = types.types?.[0]?.id || "";
      }
      if (!documentTypeId) {
        throw new Error("No document type found. Configure a schema first.");
      }

      const response = await api.createDeploymentVersion({
        project_id: id,
        document_type_id: documentTypeId,
        created_by: "ui",
        set_active: true,
      });
      const created = response.version;
      toast({
        title: "Deployment version created",
        description: `v${created.version} is now active at /api/v1/deployments/projects/${id}/extract`,
      });
    } catch (error: any) {
      toast({
        title: "Failed to create deployment version",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setSavingDeploymentVersion(false);
    }
  };

  return (
    <Shell>
      <div className="flex flex-col h-[calc(100vh-3.5rem)]">
        {/* Project Header / Cockpit Status */}
        <div className="bg-background border-b px-6 py-4 flex items-center justify-between shrink-0">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold tracking-tight text-primary">{project.name}</h1>
              <Badge variant="outline" className="font-mono text-xs border-accent/20 text-accent">{project.id}</Badge>
            </div>
            <div className="flex items-center gap-6 text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                Coverage: <span className="text-foreground font-mono font-medium">{liveMetrics.coverage}%</span>
              </span>
              <span className="flex items-center gap-1.5">
                <RotateCcw className="h-3.5 w-3.5" />
                Last eval: <span className="text-foreground">{liveMetrics.lastEval}</span>
              </span>
              <span className="flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                Drift Risk: <span className="text-foreground">{liveMetrics.driftRisk}</span>
              </span>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2 border-accent text-accent hover:bg-accent/5">
                  <Save className="h-4 w-4" />
                  Save as New Version
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Create Project Version?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will capture the current schema, prompt configuration, and model settings as a permanent version (v2.5). This allows you to run evaluations against this specific configuration and promote it to production later.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction className="bg-accent" onClick={handleCreateDeploymentVersion} disabled={savingDeploymentVersion}>
                    {savingDeploymentVersion ? "Creating..." : "Create Version"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>

        {/* Workspace Tabs */}
        <Tabs value={activeTab} onValueChange={handleTabChange} className="flex-1 flex flex-col overflow-hidden">
          <div className="px-6 border-b bg-background/50 backdrop-blur-sm">
            <TabsList className="h-12 w-full justify-start bg-transparent p-0 gap-6">
              <TabsTrigger 
                value="schema" 
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Schema
              </TabsTrigger>
              <TabsTrigger 
                value="documents" 
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Documents
              </TabsTrigger>
              <TabsTrigger 
                value="label" 
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Label Studio
              </TabsTrigger>
              <TabsTrigger 
                value="labeled-data" 
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Labeled Data
              </TabsTrigger>
              <TabsTrigger 
                value="evaluation" 
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Evaluation
              </TabsTrigger>
              <TabsTrigger
                value="extraction"
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Extraction
              </TabsTrigger>
              <TabsTrigger 
                value="timeline" 
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Timeline
              </TabsTrigger>
              <TabsTrigger 
                value="search" 
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Search & Q&A
              </TabsTrigger>
              <TabsTrigger 
                value="drift" 
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Drift & Coverage
              </TabsTrigger>
              <TabsTrigger 
                value="api" 
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                API Management
              </TabsTrigger>
              <TabsTrigger 
                value="deployment" 
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none ml-auto"
              >
                Deployment
              </TabsTrigger>
            </TabsList>
          </div>

          <div className="flex-1 overflow-hidden bg-muted/10">
            <TabsContent value="schema" className="h-full m-0 overflow-auto p-4">
              <SchemaViewer projectId={id} />
            </TabsContent>
            <TabsContent value="documents" className="h-full m-0 p-6 overflow-auto">
              <DocumentPool onDocumentClick={handleDocumentClick} projectId={id} />
            </TabsContent>
            <TabsContent value="label" className="h-full m-0 p-0 overflow-hidden">
              <LabelStudio documentId={selectedDocumentId} />
            </TabsContent>
            <TabsContent value="labeled-data" className="h-full m-0 p-6 overflow-auto">
              <LabeledDataViewer projectId={id} />
            </TabsContent>
            <TabsContent value="evaluation" className="h-full m-0 p-6 overflow-auto">
              <EvaluationBoard projectId={id} />
            </TabsContent>
            <TabsContent value="extraction" className="h-full m-0 p-6 overflow-auto">
              <ExtractionRunner projectId={id} />
            </TabsContent>
            <TabsContent value="timeline" className="h-full m-0 p-6 overflow-auto">
              <Timeline projectId={id} onDocumentClick={handleDocumentClick} />
            </TabsContent>
            <TabsContent value="search" className="h-full m-0 p-6 overflow-auto">
              <SearchPanel onDocumentClick={handleDocumentClick} />
            </TabsContent>
            <TabsContent value="drift" className="h-full m-0 p-6 overflow-auto">
              <DriftMap />
            </TabsContent>
            <TabsContent value="api" className="h-full m-0 p-6 overflow-auto">
              <APIManagement />
            </TabsContent>
            <TabsContent value="deployment" className="h-full m-0 p-6 overflow-auto">
              <DeploymentView projectId={id} />
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </Shell>
  );
}
