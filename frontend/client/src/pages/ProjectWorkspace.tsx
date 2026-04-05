import { Shell } from "@/components/layout/Shell";
import { useParams } from "wouter";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  BarChart3,
  BookOpenText,
  Boxes,
  Braces,
  FileText,
  Rocket,
  Save,
  Tags,
  Waypoints,
} from "lucide-react";
import { useState, useMemo, useEffect, type ComponentType } from "react";
import { useQuery } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";
import { api, type ProjectSummary } from "@/lib/api";
import { cn } from "@/lib/utils";
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
  doc_count?: number;
  model?: string | null;
}

type WorkspaceTabId =
  | "schema"
  | "documents"
  | "extraction"
  | "labeller"
  | "labels"
  | "evaluate"
  | "api"
  | "deployment";

const WORKSPACE_TABS: WorkspaceTabId[] = [
  "schema",
  "documents",
  "extraction",
  "labeller",
  "labels",
  "evaluate",
  "api",
  "deployment",
];

const WORKSPACE_TAB_META: Record<
  WorkspaceTabId,
  {
    label: string;
    icon: ComponentType<{ className?: string }>;
    className?: string;
  }
> = {
  schema: { label: "Schema", icon: Braces },
  documents: { label: "Documents", icon: FileText },
  extraction: { label: "Extraction", icon: Waypoints },
  labeller: { label: "Data Labeller", icon: BookOpenText },
  labels: { label: "Labels", icon: Tags },
  evaluate: { label: "Evaluate", icon: BarChart3 },
  api: { label: "API Management", icon: Boxes },
  deployment: { label: "Deployment", icon: Rocket, className: "ml-auto" },
};

function isWorkspaceTabId(value: string): value is WorkspaceTabId {
  return WORKSPACE_TABS.includes(value as WorkspaceTabId);
}

export default function ProjectWorkspace() {
  const { id } = useParams();
  const { toast } = useToast();

  useEffect(() => {
    if (id) {
      localStorage.setItem("selected-project", id);
    }
  }, [id]);

  const getTabFromUrl = (): WorkspaceTabId => {
    const hash = window.location.hash.slice(1);
    if (!hash) return "documents";
    return isWorkspaceTabId(hash) ? hash : "documents";
  };

  const [activeTab, setActiveTab] = useState<WorkspaceTabId>(getTabFromUrl());
  const [savingDeploymentVersion, setSavingDeploymentVersion] = useState(false);

  const handleTabChange = (tab: string) => {
    if (!isWorkspaceTabId(tab)) return;
    setActiveTab(tab);
    window.location.hash = tab;
  };

  useEffect(() => {
    const handleHashChange = () => {
      setActiveTab(getTabFromUrl());
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const { data: projectData } = useQuery({
    queryKey: ["project", id],
    queryFn: () => api.getProject(id || ""),
    enabled: !!id,
  });

  const project = useMemo<Project>(() => {
    if (projectData?.project) {
      return projectData.project as ProjectSummary;
    }

    return {
      id: id || "unknown",
      name: id
        ? id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
        : "Project",
      description: "",
      doc_count: 0,
    };
  }, [id, projectData]);

  const handleCreateDeploymentVersion = async () => {
    if (!id) return;
    setSavingDeploymentVersion(true);
    try {
      const selectedTypeStorageKey = `uu-schema-selected-type:${id}`;
      let documentTypeId = localStorage.getItem(selectedTypeStorageKey) || "";

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
    <Shell
      section="workspace"
      projectId={id}
      pageTitle={project.name}
      pageDescription={
        project.description ||
        "Configure schemas and extract structured data from documents."
      }
      primaryAction={
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline" size="sm" className="gap-2">
              <Save className="h-4 w-4" />
              Save as New Version
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Create Project Version?</AlertDialogTitle>
              <AlertDialogDescription>
                This captures the current schema, prompts, and model settings as
                a versioned deployment artifact.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleCreateDeploymentVersion}
                disabled={savingDeploymentVersion}
              >
                {savingDeploymentVersion ? "Creating..." : "Create Version"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      }
      secondaryActions={
        <Badge variant="outline" className="font-mono text-xs">
          {project.id}
        </Badge>
      }
      contentClassName="py-0 px-0 md:px-0"
      contentFullWidth
    >
      <div className="flex flex-col h-[calc(100vh-7rem)] min-h-[600px]">
        <Tabs
          value={activeTab}
          onValueChange={handleTabChange}
          className="flex-1 flex flex-col overflow-hidden"
        >
          <div className="sticky top-0 z-20 border-b border-[var(--border-subtle)] bg-[var(--surface-elevated)]/95 shadow-[0_1px_0_rgba(56,1,64,0.08)] backdrop-blur supports-[backdrop-filter]:bg-[var(--surface-elevated)]/80">
            <div className="w-full lg:max-w-[80vw] mx-auto px-4 md:px-8">
              <div className="pt-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-secondary)]">
                  Project Modules
                </p>
              </div>
              <TabsList className="w-full justify-start bg-transparent border-0 p-0 py-2.5 gap-2 overflow-x-auto overflow-y-hidden whitespace-nowrap">
                {WORKSPACE_TABS.map((tabId) => {
                  const tabMeta = WORKSPACE_TAB_META[tabId];
                  const Icon = tabMeta.icon;

                  return (
                    <TabsTrigger
                      key={tabId}
                      value={tabId}
                      className={cn(
                        "h-10 px-3.5 gap-2 text-xs md:text-sm",
                        tabMeta.className,
                      )}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      {tabMeta.label}
                    </TabsTrigger>
                  );
                })}
              </TabsList>
            </div>
          </div>

          <div className="w-full lg:max-w-[80vw] mx-auto flex-1 flex flex-col min-h-0">
            <div className="flex-1 overflow-hidden bg-gradient-to-b from-[var(--surface-elevated)]/50 via-transparent to-transparent">
              <TabsContent
                value="schema"
                className="h-full m-0 overflow-hidden p-4"
              >
                <SchemaViewer projectId={id} />
              </TabsContent>
              <TabsContent
                value="documents"
                className="h-full m-0 p-6 overflow-auto"
              >
                <DocumentPool projectId={id} />
              </TabsContent>
              <TabsContent
                value="extraction"
                className="h-full m-0 p-6 overflow-auto"
              >
                <ExtractionRunner projectId={id} />
              </TabsContent>
              <TabsContent
                value="labeller"
                className="h-full m-0 p-0 overflow-hidden"
              >
                <div className="h-full p-4 xl:px-5 overflow-hidden">
                  <DataLabeller projectId={id} />
                </div>
              </TabsContent>
              <TabsContent
                value="labels"
                className="h-full m-0 p-6 overflow-auto"
              >
                <LabelsView projectId={id} />
              </TabsContent>
              <TabsContent
                value="evaluate"
                className="h-full m-0 p-6 overflow-auto"
              >
                <EvaluateView projectId={id} />
              </TabsContent>
              <TabsContent value="api" className="h-full m-0 p-6 overflow-auto">
                <APIManagement />
              </TabsContent>
              <TabsContent
                value="deployment"
                className="h-full m-0 p-6 overflow-auto"
              >
                <DeploymentView projectId={id} />
              </TabsContent>
            </div>
          </div>
        </Tabs>
      </div>
    </Shell>
  );
}
