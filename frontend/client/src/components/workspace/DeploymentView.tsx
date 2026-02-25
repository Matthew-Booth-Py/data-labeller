import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Copy,
  Rocket,
  CheckCircle2,
  History,
  Upload,
  Loader2,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";

interface DeploymentViewProps {
  projectId?: string;
}

export function DeploymentView({ projectId }: DeploymentViewProps) {
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(
    null,
  );
  const [lastExtractedPayload, setLastExtractedPayload] = useState<Record<
    string,
    unknown
  > | null>(null);

  const {
    data: versionsData,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["deployment-versions", projectId],
    queryFn: () =>
      projectId
        ? api.listDeploymentVersions(projectId)
        : Promise.resolve({ versions: [], total: 0 }),
    enabled: !!projectId,
    staleTime: 0,
  });

  const versions = versionsData?.versions || [];
  const activeVersion = useMemo(
    () => versions.find((version) => version.is_active) || null,
    [versions],
  );

  const activateMutation = useMutation({
    mutationFn: async (versionId: string) => {
      if (!projectId) throw new Error("Project id missing");
      return api.activateDeploymentVersion(projectId, versionId);
    },
    onSuccess: async () => {
      await refetch();
      toast({
        title: "Deployment promoted",
        description: "Active extraction endpoint version updated.",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Failed to promote deployment",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const selectedVersion =
    versions.find((version) => version.id === selectedVersionId) || null;
  const selectedVersionName = selectedVersion?.version;
  const endpointPath = projectId
    ? selectedVersionName
      ? `/api/v1/deployments/projects/${projectId}/v/${selectedVersionName}/extract`
      : `/api/v1/deployments/projects/${projectId}/extract`
    : "";
  const endpointUrl = projectId ? `http://localhost:8000${endpointPath}` : "";

  const handleCopyEndpoint = async () => {
    if (!endpointUrl) return;
    await navigator.clipboard.writeText(endpointUrl);
    toast({ title: "Endpoint copied" });
  };

  const handleUploadForTest = () => {
    if (!activeVersion) {
      toast({
        title: "No active deployment",
        description: "Create or activate a version first.",
        variant: "destructive",
      });
      return;
    }
    fileInputRef.current?.click();
  };

  const extractMutation = useMutation({
    mutationFn: async (file: File) => {
      if (!projectId) throw new Error("Project id missing");
      if (selectedVersionId) {
        return api.extractWithDeploymentVersion(
          projectId,
          selectedVersionId,
          file,
        );
      }
      return api.extractWithActiveDeployment(projectId, file);
    },
    onSuccess: (result) => {
      setLastExtractedPayload(result.extracted_data);
      toast({
        title: "Endpoint extraction complete",
        description: `${result.filename} extracted with deployment v${result.deployment_version}`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Endpoint extraction failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  return (
    <div className="space-y-6">
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) extractMutation.mutate(file);
          if (event.target) event.target.value = "";
        }}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card className="border-accent/30 bg-accent/5">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Rocket className="h-5 w-5 text-accent" />
                    Active Deployment
                  </CardTitle>
                  <CardDescription>
                    Versioned extraction endpoint per project. Promote any saved
                    version.
                  </CardDescription>
                </div>
                {activeVersion ? (
                  <Badge className="bg-emerald-500">
                    v{activeVersion.version} Live
                  </Badge>
                ) : (
                  <Badge variant="outline">No Active Version</Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-md border bg-card overflow-hidden">
                <div className="grid grid-cols-6 p-3 bg-muted/30 border-b text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                  <div>Version</div>
                  <div className="col-span-2">Document Type</div>
                  <div>Schema</div>
                  <div>Created</div>
                  <div className="text-right">Action</div>
                </div>
                {isLoading ? (
                  <div className="p-4 text-sm text-muted-foreground">
                    Loading deployment versions…
                  </div>
                ) : versions.length === 0 ? (
                  <div className="p-4 text-sm text-muted-foreground">
                    No deployment versions yet. Use{" "}
                    <strong>Save as New Version</strong> to create your first
                    endpoint release.
                  </div>
                ) : (
                  versions.map((version) => (
                    <div
                      key={version.id}
                      className={`grid grid-cols-6 p-4 items-center border-b last:border-0 text-sm ${version.is_active ? "bg-accent/5" : ""}`}
                    >
                      <div className="font-mono">v{version.version}</div>
                      <div className="col-span-2">
                        <div className="font-medium">
                          {version.document_type_name}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {version.document_type_id}
                        </div>
                      </div>
                      <div className="font-mono text-xs">
                        {version.schema_version_id?.slice(0, 8) || "—"}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(version.created_at).toLocaleString()}
                      </div>
                      <div className="text-right">
                        {version.is_active ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-emerald-500 gap-2 pointer-events-none"
                          >
                            <CheckCircle2 className="h-3.5 w-3.5" /> Deployed
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-accent/30 text-accent hover:bg-accent/10"
                            onClick={() => activateMutation.mutate(version.id)}
                            disabled={activateMutation.isPending}
                          >
                            Promote
                          </Button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Endpoint</CardTitle>
              <CardDescription>
                Production extraction endpoint. Select a specific version to
                target a pinned URL.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-2 p-3 bg-black rounded-md border border-zinc-800 font-mono text-sm overflow-hidden text-zinc-300">
                <span className="text-accent font-bold">POST</span>
                <span className="truncate">{endpointUrl || "—"}</span>
                <Button
                  size="icon"
                  variant="ghost"
                  className="ml-auto h-6 w-6 text-zinc-500 hover:text-accent"
                  onClick={handleCopyEndpoint}
                >
                  <Copy className="h-3 w-3" />
                </Button>
              </div>

              <pre className="p-4 bg-black text-zinc-400 rounded-md font-mono text-xs overflow-x-auto border border-zinc-800">{`curl -X POST ${endpointUrl} \\
  -F "file=@invoice.pdf"`}</pre>

              <div className="flex items-center gap-2">
                <Button
                  onClick={handleUploadForTest}
                  disabled={!activeVersion || extractMutation.isPending}
                  className="gap-2"
                >
                  {extractMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4" />
                  )}
                  Test Endpoint
                </Button>
                <Button
                  variant="outline"
                  onClick={() =>
                    setSelectedVersionId(activeVersion?.id || null)
                  }
                  disabled={!activeVersion}
                >
                  Use Active Version
                </Button>
              </div>

              {lastExtractedPayload && (
                <pre className="p-4 bg-muted/20 rounded-md text-xs overflow-x-auto border">
                  {JSON.stringify(lastExtractedPayload, null, 2)}
                </pre>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="h-4 w-4" />
                Version History
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {versions.length === 0 ? (
                <p className="text-muted-foreground text-xs">
                  No versions saved yet.
                </p>
              ) : (
                versions.map((version) => (
                  <button
                    key={version.id}
                    className={`w-full text-left flex items-center justify-between rounded-md border px-3 py-2 ${
                      selectedVersionId === version.id
                        ? "border-accent bg-accent/10"
                        : "border-muted"
                    }`}
                    onClick={() => setSelectedVersionId(version.id)}
                  >
                    <div>
                      <p className="font-medium">v{version.version}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {new Date(version.created_at).toLocaleString()}
                      </p>
                    </div>
                    <Badge
                      variant={version.is_active ? "default" : "outline"}
                      className={version.is_active ? "bg-accent" : ""}
                    >
                      {version.is_active ? "Live" : "Saved"}
                    </Badge>
                  </button>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
