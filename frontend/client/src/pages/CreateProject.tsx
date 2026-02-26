import { Shell } from "@/components/layout/Shell";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ArrowLeft, FolderPlus } from "lucide-react";
import { useLocation } from "wouter";
import { useState } from "react";

export default function CreateProject() {
  const [_, setLocation] = useLocation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) return;

    setIsCreating(true);

    // Generate a URL-friendly ID from the name
    const id = name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");

    // Store project in localStorage for persistence
    const existingProjects = JSON.parse(
      localStorage.getItem("uu-projects") || "[]",
    );
    const newProject = {
      id,
      name: name.trim(),
      description: description.trim(),
      type: "Document Analysis",
      coverage: 0,
      lastEval: "Never",
      driftRisk: "Low",
      docCount: 0,
      createdAt: new Date().toISOString(),
    };

    existingProjects.push(newProject);
    localStorage.setItem("uu-projects", JSON.stringify(existingProjects));

    // Navigate to the new project workspace
    setLocation(`/project/${id}`);
  };

  return (
    <Shell
      section="projects"
      pageTitle="Create New Project"
      pageDescription="Set up a project workspace for ingestion, schema definition, and extraction."
      showProjectRail
    >
      <div className="max-w-2xl mx-auto space-y-6">
        <Button
          variant="quiet"
          className="gap-2 -ml-2"
          onClick={() => setLocation("/projects")}
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Projects
        </Button>

        <Card className="bg-[var(--surface-panel)]">
          <CardHeader>
            <CardTitle className="flex items-center gap-3 text-2xl">
              <div className="h-10 w-10 rounded-lg bg-accent/10 flex items-center justify-center">
                <FolderPlus className="h-5 w-5 text-accent" />
              </div>
              Create New Project
            </CardTitle>
          </CardHeader>

          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="name" className="text-sm font-medium">
                Project Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="name"
                placeholder="e.g., Insurance Claims 2024"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-11"
              />
              <p className="text-xs text-muted-foreground">
                A unique name for your document analysis project
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description" className="text-sm font-medium">
                Description
              </Label>
              <Textarea
                id="description"
                placeholder="Describe the purpose and scope of this project..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                className="resize-none"
              />
            </div>

            <div className="rounded-lg bg-muted/50 p-4 space-y-2">
              <h4 className="font-medium text-sm">What happens next?</h4>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Upload documents to your project</li>
                <li>• Open Schema → Document Types → Fields Definition</li>
                <li>
                  • Click Add Field and use AI Field Assistant to generate field
                  + Extraction Prompt
                </li>
                <li>
                  • Classify one document manually to set a strong baseline
                </li>
                <li>• Classify remaining documents with the LLM</li>
                <li>• Annotate with AI suggestions and confirm labels</li>
                <li>• Run extraction and inspect raw output</li>
              </ul>
            </div>
          </CardContent>

          <CardFooter className="border-t border-[var(--border-subtle)] bg-muted/5 flex justify-end gap-3 pt-4">
            <Button variant="outline" onClick={() => setLocation("/projects")}>
              Cancel
            </Button>
            <Button
              className="gap-2"
              onClick={handleCreate}
              disabled={!name.trim() || isCreating}
            >
              <FolderPlus className="h-4 w-4" />
              {isCreating ? "Creating..." : "Create Project"}
            </Button>
          </CardFooter>
        </Card>
      </div>
    </Shell>
  );
}
