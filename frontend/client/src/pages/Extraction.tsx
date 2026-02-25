import { Shell } from "@/components/layout/Shell";
import { useParams } from "wouter";
import { ExtractionRunner } from "@/components/workspace/ExtractionRunner";

export default function Extraction() {
  const { id } = useParams();
  return (
    <Shell>
      <div className="p-8">
        <ExtractionRunner projectId={id} />
      </div>
    </Shell>
  );
}
