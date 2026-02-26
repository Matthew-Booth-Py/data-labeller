import { Shell } from "@/components/layout/Shell";
import { useParams } from "wouter";
import { ExtractionRunner } from "@/components/workspace/ExtractionRunner";

export default function Extraction() {
  const { id } = useParams();
  return (
    <Shell
      section="workspace"
      pageTitle="Extraction Runner"
      pageDescription="Run live extraction for the current project and inspect structured output."
      projectId={id}
    >
      <div>
        <ExtractionRunner projectId={id} />
      </div>
    </Shell>
  );
}
