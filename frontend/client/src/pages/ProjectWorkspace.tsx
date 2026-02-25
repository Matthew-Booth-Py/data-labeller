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
import { DeploymentView } from "@/components/workspace/DeploymentView";
import { APIManagement } from "@/components/workspace/APIManagement";
import { ExtractionRunner } from "@/components/workspace/ExtractionRunner";
import { DataLabellerV2 as DataLabeller } from "@/components/workspace/DataLabellerV2";
import { LabelsView } from "@/components/workspace/LabelsView";
import { EvaluateView } from "@/components/workspace/EvaluateView";

interface Project {
  id: string;
  name: string;
  description?: string;
  type?: string;
  docCount?: number;
  model?: string;
}

export default function ProjectWorkspace() {
  const { id } = useParams();
  const { toast } = useToast();
  const validTabs = new Set([
    "schema",
    "documents",
    "extraction",
    "labeller",
    "labels",
    "evaluate",
    "api",
    "deployment",
  ]);

  // Set the selected project in localStorage for other components to use
  useEffect(() => {
    if (id) {
      localStorage.setItem("selected-project", id);
      console.log('[ProjectWorkspace] Set selected-project to:', id);
    }
  }, [id]);
  
  // Get tab from URL hash or default to "documents"
  const getTabFromUrl = () => {
    const hash = window.location.hash.slice(1); // Remove the '#'
    if (!hash) return "documents";
    return validTabs.has(hash) ? hash : "documents";
  };
  
  const [activeTab, setActiveTab] = useState(getTabFromUrl());
  const [savingDeploymentVersion, setSavingDeploymentVersion] = useState(false);

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
    
    // Return a default project with the URL id
    return {
      id: id || "unknown",
      name: id ? id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "Project",
      description: "",
      docCount: 0,
      model: "GPT-5-mini",
    };
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
            <p className="text-sm text-muted-foreground">
              {project.description || "Configure schemas and extract structured data from documents"}
            </p>
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
                value="extraction"
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Extraction
              </TabsTrigger>
              <TabsTrigger
                value="labeller"
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Data Labeller
              </TabsTrigger>
              <TabsTrigger
                value="labels"
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Labels
              </TabsTrigger>
              <TabsTrigger
                value="evaluate"
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-accent rounded-none h-full px-0 font-medium text-muted-foreground data-[state=active]:text-foreground transition-none"
              >
                Evaluate
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
              <DocumentPool projectId={id} />
            </TabsContent>
            <TabsContent value="extraction" className="h-full m-0 p-6 overflow-auto">
              <ExtractionRunner projectId={id} />
            </TabsContent>
            <TabsContent value="labeller" className="h-full m-0 p-0 overflow-hidden">
              <DataLabeller />
            </TabsContent>
            <TabsContent value="labels" className="h-full m-0 p-6 overflow-auto">
              <LabelsView />
            </TabsContent>
            <TabsContent value="evaluate" className="h-full m-0 p-6 overflow-auto">
              <EvaluateView />
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
