import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Shell } from "@/components/layout/Shell";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Plus,
  FileText,
  Play,
  ArrowUpRight,
  Clock,
  Trash2,
  Loader2,
} from "lucide-react";
import { Link, useLocation } from "wouter";
import { api, type ProjectSummary } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

type Project = ProjectSummary & {
  coverage?: number;
  lastEval?: string;
  driftRisk?: "Low" | "Medium" | "High";
};

type DriftRisk = "Low" | "Medium" | "High" | "Unknown";

interface ProjectLiveMetrics {
  coverage: number;
  lastEval: string;
  driftRisk: DriftRisk;
}

const getProjectDisplayMetrics = (
  project: Project,
  live?: ProjectLiveMetrics,
): ProjectLiveMetrics => ({
  coverage: live?.coverage ?? project.coverage ?? 0,
  lastEval: live?.lastEval ?? project.lastEval ?? "Never",
  driftRisk: live?.driftRisk ?? project.driftRisk ?? "Unknown",
});

export default function ProjectsList() {
  const [_, setLocation] = useLocation();
  const [projectMetrics, setProjectMetrics] = useState<
    Record<string, ProjectLiveMetrics>
  >({});
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects(),
  });
  const projects = (projectsData?.projects || []) as Project[];

  useEffect(() => {
    const computeMetrics = async () => {
      if (!projects.length) {
        setProjectMetrics({});
        return;
      }
      try {
        const response = await api.listEvaluations(undefined, undefined, 2000);
        const allEvals = response.runs || [];
        const next: Record<string, ProjectLiveMetrics> = {};

        for (const project of projects) {
          try {
            const documentIds = project.document_ids || [];
            const docCount = documentIds.length || project.doc_count || 0;
            if (docCount === 0) {
              next[project.id] = {
                coverage: 0,
                lastEval: "Never",
                driftRisk: "Unknown",
              };
              continue;
            }

            // Primary path: strict project doc IDs.
            const docSet = new Set(documentIds);
            let evals = allEvals.filter((e: any) => docSet.has(e.document_id));

            // Fallback for legacy projects that tracked docCount but not documentIds.
            if (!documentIds.length) {
              evals = allEvals;
            }

            const evaluatedDocs = new Set(evals.map((e: any) => e.document_id));
            const coverage = Math.min(
              100,
              Math.round((evaluatedDocs.size / docCount) * 100),
            );
            const latestEval = evals
              .map((e: any) => e.evaluated_at)
              .filter(Boolean)
              .sort(
                (a: string, b: string) =>
                  new Date(b).getTime() - new Date(a).getTime(),
              )[0];

            const sortedByDate = [...evals].sort(
              (a: any, b: any) =>
                new Date(a.evaluated_at).getTime() -
                new Date(b.evaluated_at).getTime(),
            );
            const f1Series = sortedByDate
              .map((e: any) => Number(e.metrics?.f1_score ?? 0))
              .filter((v: number) => Number.isFinite(v));

            let driftRisk: DriftRisk = "Unknown";
            if (f1Series.length >= 2) {
              const recent = f1Series.slice(-5);
              const previous = f1Series.slice(-10, -5);
              const avg = (arr: number[]) =>
                arr.length ? arr.reduce((s, x) => s + x, 0) / arr.length : 0;
              const recentAvg = avg(recent);
              const previousAvg = previous.length ? avg(previous) : recentAvg;
              const delta = Math.abs(recentAvg - previousAvg);
              if (recentAvg < 0.75 || delta > 0.15) driftRisk = "High";
              else if (recentAvg < 0.9 || delta > 0.08) driftRisk = "Medium";
              else driftRisk = "Low";
            }

            next[project.id] = {
              coverage,
              lastEval: latestEval
                ? new Date(latestEval).toLocaleDateString()
                : "Never",
              driftRisk,
            };
          } catch {
            next[project.id] = getProjectDisplayMetrics(project);
          }
        }

        setProjectMetrics(next);
      } catch {
        // keep UI usable if metrics endpoint fails
      }
    };

    computeMetrics();

    const onFocus = () => {
      computeMetrics();
    };

    window.addEventListener("focus", onFocus);
    return () => {
      window.removeEventListener("focus", onFocus);
    };
  }, [projects]);

  const deleteProject = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const project = projects.find((p) => p.id === id);
    if (!project) return;

    if (project.document_ids && project.document_ids.length > 0) {
      const confirmed = window.confirm(
        `This will remove the project workspace. ${project.document_ids.length} document(s) will remain in the system. Continue?`,
      );
      if (!confirmed) return;
    }

    setDeletingId(id);

    try {
      await api.deleteProject(id);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });

      toast({
        title: "Project deleted",
        description: project.document_ids?.length
          ? `Removed project workspace. ${project.document_ids.length} document(s) remain available in the system.`
          : "Project removed successfully",
      });
    } catch (error) {
      console.error("Error deleting project:", error);
      toast({
        title: "Delete failed",
        description: "Failed to delete project",
        variant: "destructive",
      });
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Shell
      section="projects"
      pageTitle="Projects"
      pageDescription="Manage and monitor your document extraction pipelines."
      primaryAction={
        <Button className="gap-2" onClick={() => setLocation("/projects/new")}>
          <Plus className="h-4 w-4" />
          New Project
        </Button>
      }
    >
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-secondary)]">
            Active Workspaces
          </h2>
          <Badge variant="outline">{projects.length} projects</Badge>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {projects.map((project) => (
            <Card
              key={project.id}
              className="group hover:border-primary/25 transition-all bg-[var(--surface-panel)] border-[var(--border-subtle)] shadow-sm flex flex-col relative overflow-visible"
            >
              {(() => {
                const display = getProjectDisplayMetrics(
                  project,
                  projectMetrics[project.id],
                );
                return (
                  <>
                    <CardHeader className="pb-4">
                      <div className="flex items-start justify-between">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 mb-2">
                            <Badge
                              variant="outline"
                              className="text-xs font-normal border-muted-foreground/20 text-muted-foreground bg-muted/5"
                            >
                              {project.type || "Document Analysis"}
                            </Badge>
                            <Badge
                              variant={
                                display.driftRisk === "High"
                                  ? "destructive"
                                  : "secondary"
                              }
                              className="text-[10px]"
                            >
                              {display.driftRisk} Risk
                            </Badge>
                          </div>
                          <CardTitle className="text-xl font-bold text-foreground group-hover:text-primary transition-colors flex items-center gap-2">
                            <Link
                              href={`/project/${project.id}`}
                              className="hover:underline underline-offset-4 decoration-primary/30"
                            >
                              {project.name}
                            </Link>
                            <ArrowUpRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                          </CardTitle>
                          <p className="text-sm text-muted-foreground line-clamp-1">
                            {project.description || "No description"}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10 -mt-1 -mr-2"
                          onClick={(e) => deleteProject(project.id, e)}
                          disabled={deletingId === project.id}
                          title="Delete project"
                        >
                          {deletingId === project.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </CardHeader>

                    <CardContent className="py-4 border-t border-dashed border-muted">
                      <div className="grid grid-cols-3 gap-8">
                        <div className="space-y-1">
                          <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                            Docs
                          </p>
                          <div className="flex items-center gap-2 font-mono text-sm font-medium">
                            <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                            {(project.doc_count || 0).toLocaleString()}
                          </div>
                        </div>
                        <div className="space-y-1">
                          <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                            Coverage
                          </p>
                          <div className="flex items-center gap-2 font-mono text-sm font-medium">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            {display.coverage}%
                          </div>
                        </div>
                        <div className="space-y-1">
                          <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                            Model
                          </p>
                          <div
                            className="flex items-center gap-2 font-mono text-sm font-medium truncate"
                            title={project.model || undefined}
                          >
                            {(project.model || "OPENAI_MODEL").split(" ")[0]}
                          </div>
                        </div>
                      </div>
                    </CardContent>

                    <CardFooter className="pt-3 pb-3 bg-muted/5 flex justify-between items-center text-xs text-muted-foreground border-t border-muted">
                      <div className="flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5" />
                        {project.created_at
                          ? `Created: ${new Date(project.created_at).toLocaleDateString()}`
                          : `Last eval: ${display.lastEval}`}
                      </div>

                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setLocation(`/project/${project.id}`);
                        }}
                        className="h-8 gap-2 px-4"
                      >
                        <Play className="h-3.5 w-3.5 fill-current" />
                        Open
                      </Button>
                    </CardFooter>
                  </>
                );
              })()}
            </Card>
          ))}

          {/* Create New Project Card */}
          <button
            className="h-full min-h-[220px] border-2 border-dashed rounded-xl border-muted-foreground/10 flex flex-col items-center justify-center gap-3 text-muted-foreground hover:border-accent/50 hover:text-accent hover:bg-accent/5 transition-all group bg-white/50"
            onClick={() => setLocation("/projects/new")}
          >
            <div className="h-14 w-14 rounded-full bg-muted flex items-center justify-center group-hover:bg-accent/10 group-hover:text-accent transition-colors">
              <Plus className="h-6 w-6" />
            </div>
            <div className="text-center">
              <span className="font-semibold block">Create Project</span>
              <span className="text-xs text-muted-foreground mt-1">
                Start a new document analysis project
              </span>
            </div>
          </button>
        </div>

        {projects.length === 0 && (
          <div className="text-center py-12 rounded-xl border border-dashed border-[var(--border-strong)] bg-[var(--surface-panel)]">
            <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium">No projects yet</h3>
            <p className="text-muted-foreground mt-1">
              Create your first project to get started
            </p>
            <Button
              className="mt-4"
              variant="secondary"
              onClick={() => setLocation("/projects/new")}
            >
              Create Project
            </Button>
          </div>
        )}
      </div>
    </Shell>
  );
}
