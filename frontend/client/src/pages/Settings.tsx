import { Shell } from "@/components/layout/Shell";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, type SchemaField } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import {
  Cpu,
  Database,
  Download,
  ExternalLink,
  Info,
  RefreshCw,
  Upload,
} from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";

type SettingsTab = "llm" | "engines" | "workspace";

const PROJECT_STORAGE_KEY = "uu-projects";
const SELECTED_PROJECT_KEY = "selected-project";
const WORKSPACE_BUNDLE_VERSION = 1;

interface ProjectRecord {
  id: string;
  name: string;
  description?: string;
  type?: string;
  coverage?: number;
  lastEval?: string;
  driftRisk?: "Low" | "Medium" | "High" | "Unknown";
  docCount?: number;
  model?: string;
  createdAt?: string;
  documentIds?: string[];
}

interface WorkspaceBundleDocumentType {
  id: string;
  name: string;
  description?: string;
  schema_fields: SchemaField[];
  system_prompt?: string;
  post_processing?: string;
  extraction_model?: string;
  ocr_engine?: string;
}

interface WorkspaceBundleGlobalField {
  id: string;
  name: string;
  type: "string" | "number" | "date" | "boolean" | "object" | "array";
  prompt: string;
  description?: string;
  extraction_model?: string;
  ocr_engine?: string;
  created_by?: string;
}

interface WorkspaceBundle {
  version: number;
  exported_at: string;
  source_api_url: string;
  selected_project_id: string | null;
  selected_schema_by_project: Record<string, string>;
  projects: ProjectRecord[];
  document_types: WorkspaceBundleDocumentType[];
  global_fields: WorkspaceBundleGlobalField[];
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Unknown error";
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function assertValid(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(message);
  }
}

function normalizeName(name: string): string {
  return name.trim().toLowerCase();
}

function parseProjectsFromStorage(): ProjectRecord[] {
  const raw = localStorage.getItem(PROJECT_STORAGE_KEY);
  if (!raw) return [];
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed)) {
    throw new Error("Invalid local project storage format");
  }
  return parsed as ProjectRecord[];
}

function buildDownload(
  filename: string,
  payload: Record<string, unknown> | WorkspaceBundle,
) {
  const json = JSON.stringify(payload, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function parseWorkspaceBundle(raw: unknown): WorkspaceBundle {
  assertValid(isObject(raw), "Invalid workspace bundle format");
  assertValid(
    raw.version === WORKSPACE_BUNDLE_VERSION,
    `Unsupported workspace bundle version. Expected ${WORKSPACE_BUNDLE_VERSION}`,
  );
  assertValid(
    Array.isArray(raw.projects),
    "Invalid workspace bundle: projects must be an array",
  );
  assertValid(
    Array.isArray(raw.document_types),
    "Invalid workspace bundle: document_types must be an array",
  );
  assertValid(
    Array.isArray(raw.global_fields),
    "Invalid workspace bundle: global_fields must be an array",
  );
  assertValid(
    raw.selected_schema_by_project === undefined ||
      isObject(raw.selected_schema_by_project),
    "Invalid workspace bundle: selected_schema_by_project must be an object",
  );

  const selectedProjectIdRaw = raw.selected_project_id;
  assertValid(
    selectedProjectIdRaw === null || typeof selectedProjectIdRaw === "string",
    "Invalid selected_project_id in workspace bundle",
  );
  const rawSelectedSchemaMap = raw.selected_schema_by_project;
  const selectedSchemaByProject: Record<string, string> = {};
  if (isObject(rawSelectedSchemaMap)) {
    for (const [projectId, schemaId] of Object.entries(rawSelectedSchemaMap)) {
      assertValid(
        typeof projectId === "string" &&
          projectId.trim().length > 0 &&
          typeof schemaId === "string" &&
          schemaId.trim().length > 0,
        "Invalid selected schema mapping in workspace bundle",
      );
      selectedSchemaByProject[projectId] = schemaId;
    }
  }

  const projects = raw.projects.map((project, index) => {
    assertValid(isObject(project), `Invalid project at index ${index}`);
    assertValid(
      typeof project.id === "string" && project.id.trim().length > 0,
      `Project at index ${index} is missing a valid id`,
    );
    assertValid(
      typeof project.name === "string" && project.name.trim().length > 0,
      `Project at index ${index} is missing a valid name`,
    );

    return {
      id: project.id,
      name: project.name,
      description:
        typeof project.description === "string" ? project.description : "",
      type: typeof project.type === "string" ? project.type : "",
      coverage:
        typeof project.coverage === "number" ? project.coverage : undefined,
      lastEval: typeof project.lastEval === "string" ? project.lastEval : "",
      driftRisk:
        project.driftRisk === "Low" ||
        project.driftRisk === "Medium" ||
        project.driftRisk === "High" ||
        project.driftRisk === "Unknown"
          ? project.driftRisk
          : undefined,
      docCount: typeof project.docCount === "number" ? project.docCount : 0,
      model: typeof project.model === "string" ? project.model : "",
      createdAt:
        typeof project.createdAt === "string" ? project.createdAt : undefined,
      documentIds: Array.isArray(project.documentIds)
        ? project.documentIds.filter(
            (docId): docId is string => typeof docId === "string",
          )
        : [],
    } satisfies ProjectRecord;
  });

  const documentTypes = raw.document_types.map((documentType, index) => {
    assertValid(
      isObject(documentType),
      `Invalid document type at index ${index}`,
    );
    assertValid(
      typeof documentType.id === "string" && documentType.id.trim().length > 0,
      `Document type at index ${index} is missing a valid id`,
    );
    assertValid(
      typeof documentType.name === "string" &&
        documentType.name.trim().length > 0,
      `Document type at index ${index} is missing a valid name`,
    );
    assertValid(
      Array.isArray(documentType.schema_fields),
      `Document type at index ${index} is missing schema_fields`,
    );

    return {
      id: documentType.id,
      name: documentType.name,
      description:
        typeof documentType.description === "string"
          ? documentType.description
          : "",
      schema_fields: documentType.schema_fields as SchemaField[],
      system_prompt:
        typeof documentType.system_prompt === "string"
          ? documentType.system_prompt
          : "",
      post_processing:
        typeof documentType.post_processing === "string"
          ? documentType.post_processing
          : "",
      extraction_model:
        typeof documentType.extraction_model === "string"
          ? documentType.extraction_model
          : "",
      ocr_engine:
        typeof documentType.ocr_engine === "string"
          ? documentType.ocr_engine
          : "",
    } satisfies WorkspaceBundleDocumentType;
  });

  const globalFields = raw.global_fields.map((field, index) => {
    assertValid(isObject(field), `Invalid global field at index ${index}`);
    assertValid(
      typeof field.id === "string" && field.id.trim().length > 0,
      `Global field at index ${index} is missing a valid id`,
    );
    assertValid(
      typeof field.name === "string" && field.name.trim().length > 0,
      `Global field at index ${index} is missing a valid name`,
    );
    assertValid(
      field.type === "string" ||
        field.type === "number" ||
        field.type === "date" ||
        field.type === "boolean" ||
        field.type === "object" ||
        field.type === "array",
      `Global field at index ${index} has invalid type`,
    );
    assertValid(
      typeof field.prompt === "string" && field.prompt.trim().length > 0,
      `Global field at index ${index} is missing a valid prompt`,
    );

    return {
      id: field.id,
      name: field.name,
      type: field.type,
      prompt: field.prompt,
      description: typeof field.description === "string" ? field.description : "",
      extraction_model:
        typeof field.extraction_model === "string"
          ? field.extraction_model
          : "",
      ocr_engine: typeof field.ocr_engine === "string" ? field.ocr_engine : "",
      created_by: typeof field.created_by === "string" ? field.created_by : "",
    } satisfies WorkspaceBundleGlobalField;
  });

  const sourceApiUrl =
    typeof raw.source_api_url === "string" ? raw.source_api_url : "";
  const exportedAt = typeof raw.exported_at === "string" ? raw.exported_at : "";

  return {
    version: WORKSPACE_BUNDLE_VERSION,
    exported_at: exportedAt,
    source_api_url: sourceApiUrl,
    selected_project_id: selectedProjectIdRaw,
    selected_schema_by_project: selectedSchemaByProject,
    projects,
    document_types: documentTypes,
    global_fields: globalFields,
  };
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("llm");
  const [isExportingWorkspace, setIsExportingWorkspace] = useState(false);
  const [isImportingWorkspace, setIsImportingWorkspace] = useState(false);
  const importFileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const handleExportWorkspace = async () => {
    setIsExportingWorkspace(true);
    try {
      const projects = parseProjectsFromStorage();
      const selectedProjectId = localStorage.getItem(SELECTED_PROJECT_KEY);
      const selectedSchemaByProject: Record<string, string> = {};
      for (const project of projects) {
        const schemaTypeId = localStorage.getItem(
          `uu-schema-selected-type:${project.id}`,
        );
        if (schemaTypeId) {
          selectedSchemaByProject[project.id] = schemaTypeId;
        }
      }
      const [documentTypesResponse, globalFieldsResponse] = await Promise.all([
        api.listDocumentTypes(),
        api.listGlobalFields(),
      ]);

      const bundle: WorkspaceBundle = {
        version: WORKSPACE_BUNDLE_VERSION,
        exported_at: new Date().toISOString(),
        source_api_url: api.baseURL,
        selected_project_id: selectedProjectId,
        selected_schema_by_project: selectedSchemaByProject,
        projects,
        document_types: documentTypesResponse.types.map((documentType) => ({
          id: documentType.id,
          name: documentType.name,
          description: documentType.description || "",
          schema_fields: documentType.schema_fields || [],
          system_prompt: documentType.system_prompt || "",
          post_processing: documentType.post_processing || "",
          extraction_model: documentType.extraction_model || "",
          ocr_engine: documentType.ocr_engine || "",
        })),
        global_fields: globalFieldsResponse.fields.map((field) => ({
          id: field.id,
          name: field.name,
          type: field.type,
          prompt: field.prompt,
          description: field.description || "",
          extraction_model: field.extraction_model || "",
          ocr_engine: field.ocr_engine || "",
          created_by: field.created_by || "",
        })),
      };

      const datePart = new Date().toISOString().split("T")[0];
      buildDownload(`workspace-sync-${datePart}.json`, bundle);

      toast({
        title: "Workspace exported",
        description: `Exported ${bundle.projects.length} project(s), ${bundle.document_types.length} schema type(s), and ${bundle.global_fields.length} global field(s).`,
      });
    } catch (error) {
      toast({
        title: "Workspace export failed",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    } finally {
      setIsExportingWorkspace(false);
    }
  };

  const handleChooseImportFile = () => {
    importFileInputRef.current?.click();
  };

  const handleImportWorkspace = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setIsImportingWorkspace(true);
    try {
      const rawText = await file.text();
      const parsedJson = JSON.parse(rawText) as unknown;
      const bundle = parseWorkspaceBundle(parsedJson);

      const confirmed = window.confirm(
        `Import ${bundle.document_types.length} schema type(s), ${bundle.global_fields.length} global field(s), and ${bundle.projects.length} project(s) from this bundle?`,
      );
      if (!confirmed) {
        return;
      }

      const [existingDocumentTypes, existingGlobalFields] = await Promise.all([
        api.listDocumentTypes(),
        api.listGlobalFields(),
      ]);

      const documentTypesById = new Map(
        existingDocumentTypes.types.map((documentType) => [
          documentType.id,
          documentType,
        ]),
      );
      const documentTypesByName = new Map(
        existingDocumentTypes.types.map((documentType) => [
          normalizeName(documentType.name),
          documentType,
        ]),
      );

      let createdDocumentTypes = 0;
      let updatedDocumentTypes = 0;
      const importedTypeIdToResolvedId = new Map<string, string>();
      for (const documentType of bundle.document_types) {
        const existing =
          documentTypesById.get(documentType.id) ||
          documentTypesByName.get(normalizeName(documentType.name));

        const payload = {
          name: documentType.name,
          description: documentType.description,
          schema_fields: documentType.schema_fields,
          system_prompt: documentType.system_prompt,
          post_processing: documentType.post_processing,
          extraction_model: documentType.extraction_model,
          ocr_engine: documentType.ocr_engine,
        };

        if (existing) {
          await api.updateDocumentType(existing.id, payload);
          importedTypeIdToResolvedId.set(documentType.id, existing.id);
          updatedDocumentTypes += 1;
        } else {
          const created = await api.createDocumentType(payload);
          importedTypeIdToResolvedId.set(documentType.id, created.type.id);
          createdDocumentTypes += 1;
        }
      }

      const globalFieldsById = new Map(
        existingGlobalFields.fields.map((field) => [field.id, field]),
      );
      const globalFieldsByName = new Map(
        existingGlobalFields.fields.map((field) => [
          normalizeName(field.name),
          field,
        ]),
      );

      let createdGlobalFields = 0;
      let updatedGlobalFields = 0;
      for (const field of bundle.global_fields) {
        const existing =
          globalFieldsById.get(field.id) ||
          globalFieldsByName.get(normalizeName(field.name));
        const payload = {
          name: field.name,
          type: field.type,
          prompt: field.prompt,
          description: field.description,
          extraction_model: field.extraction_model,
          ocr_engine: field.ocr_engine,
          created_by: field.created_by,
        };

        if (existing) {
          await api.updateGlobalField(existing.id, payload);
          updatedGlobalFields += 1;
        } else {
          await api.createGlobalField(payload);
          createdGlobalFields += 1;
        }
      }

      const currentProjects = parseProjectsFromStorage();
      const mergedProjects = new Map<string, ProjectRecord>();
      for (const project of currentProjects) {
        mergedProjects.set(project.id, project);
      }
      for (const project of bundle.projects) {
        mergedProjects.set(project.id, project);
      }

      const finalProjects = Array.from(mergedProjects.values());
      localStorage.setItem(PROJECT_STORAGE_KEY, JSON.stringify(finalProjects));
      if (
        bundle.selected_project_id &&
        mergedProjects.has(bundle.selected_project_id)
      ) {
        localStorage.setItem(SELECTED_PROJECT_KEY, bundle.selected_project_id);
      }
      for (const [projectId, importedTypeId] of Object.entries(
        bundle.selected_schema_by_project,
      )) {
        const resolvedTypeId =
          importedTypeIdToResolvedId.get(importedTypeId) || importedTypeId;
        localStorage.setItem(`uu-schema-selected-type:${projectId}`, resolvedTypeId);
      }
      window.dispatchEvent(new Event("localStorageUpdate"));

      toast({
        title: "Workspace imported",
        description: `Schemas: ${createdDocumentTypes} created, ${updatedDocumentTypes} updated. Global fields: ${createdGlobalFields} created, ${updatedGlobalFields} updated. Projects merged: ${bundle.projects.length}.`,
      });
    } catch (error) {
      toast({
        title: "Workspace import failed",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    } finally {
      setIsImportingWorkspace(false);
    }
  };

  return (
    <Shell
      section="settings"
      pageTitle="Settings"
      pageDescription="Manage global LLM and extraction runtime configuration."
      showProjectRail
    >
      <div className="mb-4">
        <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-secondary)]">
          Configuration Domains
        </h2>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-6">
        <aside className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-panel)] p-3 h-fit">
          <h2 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-2">
            Global Settings
          </h2>
          <div className="space-y-1">
            <Button
              variant={activeTab === "llm" ? "secondary" : "quiet"}
              className="w-full justify-start gap-2"
              onClick={() => setActiveTab("llm")}
            >
              <Cpu className="h-4 w-4" />
              LLM Configuration
            </Button>
            <Button
              variant={activeTab === "engines" ? "secondary" : "quiet"}
              className="w-full justify-start gap-2"
              onClick={() => setActiveTab("engines")}
            >
              <Database className="h-4 w-4" />
              Extraction Engines
            </Button>
            <Button
              variant={activeTab === "workspace" ? "secondary" : "quiet"}
              className="w-full justify-start gap-2"
              onClick={() => setActiveTab("workspace")}
            >
              <Upload className="h-4 w-4" />
              Workspace Sync
            </Button>
          </div>
        </aside>

        <section className="space-y-6">
          {activeTab === "llm" && (
            <>
              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle className="text-xl">
                        LLM Configuration
                      </CardTitle>
                      <CardDescription className="mt-1">
                        Model provider settings are currently managed via
                        backend environment variables.
                      </CardDescription>
                    </div>
                    <Badge variant="primary">Configured</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-4">
                    <p className="text-sm text-muted-foreground">
                      Runtime source:
                      <code className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs">
                        backend/.env
                      </code>
                    </p>
                    <p className="text-sm mt-2">
                      Current model:
                      <Badge variant="outline" className="ml-2 font-mono">
                        OPENAI_MODEL
                      </Badge>
                    </p>
                  </div>

                  <div className="rounded-lg border border-dashed border-[var(--border-strong)] p-4 text-sm text-muted-foreground flex items-start gap-2">
                    <Info className="h-4 w-4 mt-0.5 text-primary" />
                    Update `OPENAI_MODEL` and provider credentials in backend
                    settings for production changes.
                  </div>
                </CardContent>
              </Card>
            </>
          )}

          {activeTab === "engines" && (
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-xl">
                      Extraction Engines
                    </CardTitle>
                    <CardDescription className="mt-1">
                      Configure OCR and engine profiles for specialized document
                      pipelines.
                    </CardDescription>
                  </div>
                  <Badge variant="outline">Not Configured</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-lg border border-dashed border-[var(--border-strong)] bg-muted/20 p-8 text-center">
                  <p className="text-base font-medium">
                    No engine profiles configured
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Backend persistence for custom extraction engines is not
                    wired yet.
                  </p>
                  <Button variant="outline" className="mt-4 gap-2" disabled>
                    Configure Engine
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                  <p className="mt-2 text-xs text-[var(--text-secondary)]">
                    Action disabled until backend engine profiles are available.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {activeTab === "workspace" && (
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-xl">Workspace Sync</CardTitle>
                    <CardDescription className="mt-1">
                      Move projects and schema configuration between machines
                      with a single JSON bundle.
                    </CardDescription>
                  </div>
                  <Badge variant="outline">Manual Sync</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                <input
                  ref={importFileInputRef}
                  type="file"
                  accept="application/json,.json"
                  className="hidden"
                  onChange={handleImportWorkspace}
                />

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-4">
                    <h3 className="font-medium">Export Workspace Bundle</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Downloads local projects plus all backend schema and
                      global field definitions.
                    </p>
                    <Button
                      className="mt-4 gap-2"
                      onClick={handleExportWorkspace}
                      disabled={isExportingWorkspace || isImportingWorkspace}
                    >
                      {isExportingWorkspace ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                      {isExportingWorkspace
                        ? "Exporting..."
                        : "Export Bundle"}
                    </Button>
                  </div>

                  <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-4">
                    <h3 className="font-medium">Import Workspace Bundle</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Applies schemas and global fields to this backend, then
                      merges projects into local storage.
                    </p>
                    <Button
                      variant="outline"
                      className="mt-4 gap-2"
                      onClick={handleChooseImportFile}
                      disabled={isExportingWorkspace || isImportingWorkspace}
                    >
                      {isImportingWorkspace ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Upload className="h-4 w-4" />
                      )}
                      {isImportingWorkspace
                        ? "Importing..."
                        : "Import Bundle"}
                    </Button>
                  </div>
                </div>

                <div className="rounded-lg border border-dashed border-[var(--border-strong)] p-4 text-sm text-muted-foreground space-y-1">
                  <p className="font-medium text-foreground">
                    Import behavior
                  </p>
                  <p>
                    Document types and global fields are upserted by ID, then
                    by name if ID is not found.
                  </p>
                  <p>
                    Projects are merged by project ID into{" "}
                    <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                      localStorage[{`"${PROJECT_STORAGE_KEY}"`}]
                    </code>
                    .
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </section>
      </div>
    </Shell>
  );
}
