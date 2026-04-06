import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/components/layout/Shell";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Activity,
  ArrowRight,
  Building2,
  CheckCircle2,
  FileText,
  Layers,
  Plus,
} from "lucide-react";
import { api } from "@/lib/api";
import { useLocation } from "wouter";

export default function Dashboard() {
  const [, setLocation] = useLocation();

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth(),
    staleTime: 30000,
  });

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects(),
    staleTime: 30000,
  });

  const projects = useMemo(() => projectsData?.projects || [], [projectsData]);

  // When there's exactly one project, scope stats to it; otherwise aggregate across all
  const scopedProjectId = projects.length === 1 ? projects[0].id : undefined;

  const { data: ingestStatus } = useQuery({
    queryKey: ["ingest-status", scopedProjectId],
    queryFn: () => api.getIngestStatus(scopedProjectId),
    staleTime: 30000,
    enabled: projectsData !== undefined,
  });

  const { data: documentTypes } = useQuery({
    queryKey: ["document-types", scopedProjectId],
    queryFn: () => api.listDocumentTypes(scopedProjectId),
    staleTime: 30000,
    enabled: projectsData !== undefined,
  });

  const totalDocs = ingestStatus?.documents || 0;
  const classifiedDocs = ingestStatus?.classified_documents || 0;
  const indexingDocs = Math.max(totalDocs - classifiedDocs, 0);
  const healthStatus = health?.status === "healthy" ? "Healthy" : "Degraded";

  return (
    <Shell
      section="dashboard"
      pageTitle="Operations Overview"
      pageDescription="Live intake, extraction, and model-readiness posture across your projects."
      primaryAction={
        <Button onClick={() => setLocation("/projects/new")} className="gap-2">
          <Plus className="h-4 w-4" />
          Create Project
        </Button>
      }
      secondaryActions={
        <Button variant="outline" onClick={() => setLocation("/projects")}>
          View Projects
        </Button>
      }
    >
      <div className="space-y-7">
        <Card className="border-primary/20 bg-gradient-to-r from-primary to-[var(--interactive-primary-hover)] text-primary-foreground shadow-[0_10px_24px_rgba(56,1,64,0.2)]">
          <CardContent className="py-8 px-6 md:px-8">
            <div className="max-w-3xl space-y-3">
              <p className="text-xs tracking-[0.18em] uppercase text-primary-foreground/80">
                extraction command center
              </p>
              <h2 className="text-2xl md:text-3xl font-semibold leading-tight">
                Build, label, evaluate, and deploy
              </h2>
              <div className="pt-2">
                <Button
                  variant="link-accent"
                  className="text-primary-foreground"
                  onClick={() => setLocation("/projects")}
                >
                  Open active projects <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-secondary)]">
              Platform Snapshot
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Documents in System</CardDescription>
                <CardTitle className="text-3xl">
                  {totalDocs.toLocaleString()}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                  <FileText className="h-4 w-4" />
                  {classifiedDocs.toLocaleString()} classified
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Active Projects</CardDescription>
                <CardTitle className="text-3xl">{projects.length}</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                  <Building2 className="h-4 w-4" />
                  Multi-project operations
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Document Types</CardDescription>
                <CardTitle className="text-3xl">
                  {documentTypes?.types?.length || 0}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                  <Layers className="h-4 w-4" />
                  Schema catalog coverage
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Platform Health</CardDescription>
                <CardTitle className="text-3xl">{healthStatus}</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <Badge
                  variant={healthStatus === "Healthy" ? "primary" : "danger"}
                  className="gap-1"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {healthStatus === "Healthy"
                    ? "Operational"
                    : "Action Required"}
                </Badge>
              </CardContent>
            </Card>
          </div>
        </section>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle>System Activity</CardTitle>
              <CardDescription>
                Current ingestion and extraction posture.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-4">
                <p className="text-xs uppercase tracking-wider text-muted-foreground">
                  classified
                </p>
                <p className="text-2xl font-semibold mt-1">{classifiedDocs}</p>
              </div>
              <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-4">
                <p className="text-xs uppercase tracking-wider text-muted-foreground">
                  indexing
                </p>
                <p className="text-2xl font-semibold mt-1">{indexingDocs}</p>
              </div>
              <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-4">
                <p className="text-xs uppercase tracking-wider text-muted-foreground">
                  type coverage
                </p>
                <p className="text-2xl font-semibold mt-1">
                  {documentTypes?.types?.length || 0}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Next Actions</CardTitle>
              <CardDescription>Common operator workflows.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                variant="secondary"
                className="w-full justify-between"
                onClick={() => setLocation("/projects/new")}
              >
                Create extraction project
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button
                variant="quiet"
                className="w-full justify-between"
                onClick={() => setLocation("/fields-library")}
              >
                Curate global fields
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button
                variant="quiet"
                className="w-full justify-between"
                onClick={() => setLocation("/settings")}
              >
                Review platform settings
                <ArrowRight className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Active Projects
            </CardTitle>
            <CardDescription>Quick-open active workspaces.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {projects.length === 0 ? (
              <div className="col-span-full rounded-lg border border-dashed border-[var(--border-strong)] p-8 text-center text-muted-foreground">
                <p>
                  No projects yet. Create your first project to start ingestion
                  and schema work.
                </p>
                <div className="mt-4">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setLocation("/projects/new")}
                  >
                    Create Project
                  </Button>
                </div>
              </div>
            ) : (
              projects.map((project) => (
                <button
                  key={project.id}
                  type="button"
                  className="text-left rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-4 hover:border-primary/40 hover:bg-white transition-colors hover-elevate"
                  onClick={() => setLocation(`/project/${project.id}`)}
                >
                  <p className="font-medium">{project.name}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {project.id}
                  </p>
                </button>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </Shell>
  );
}
