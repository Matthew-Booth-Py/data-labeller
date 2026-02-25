import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/components/layout/Shell";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  FileText,
  Building2,
} from "lucide-react";
import { api } from "@/lib/api";

export default function Dashboard() {
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth(),
    staleTime: 30000,
  });

  const { data: ingestStatus } = useQuery({
    queryKey: ["ingest-status"],
    queryFn: () => api.getIngestStatus(),
    staleTime: 30000,
  });

  const { data: documentTypes } = useQuery({
    queryKey: ["document-types"],
    queryFn: () => api.listDocumentTypes(),
    staleTime: 30000,
  });

  const totalDocs = ingestStatus?.documents || 0;
  const classifiedDocs = ingestStatus?.classified_documents || 0;
  
  const projects = (() => {
    const stored = localStorage.getItem("uu-projects");
    return stored ? JSON.parse(stored) : [];
  })();

  return (
    <Shell>
      <div className="p-8 max-w-7xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Observability Overview</h1>
          <p className="text-muted-foreground mt-1">System-wide performance and extraction health.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Classified Documents</CardTitle>
              <FileText className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{classifiedDocs.toLocaleString()}</div>
              {totalDocs > classifiedDocs && (
                <p className="text-xs text-muted-foreground mt-1">{totalDocs} total in system</p>
              )}
            </CardContent>
          </Card>
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Document Types</CardTitle>
              <FileText className="h-4 w-4 text-purple-500" />
            </CardHeader>
            <CardContent><div className="text-2xl font-bold">{documentTypes?.types?.length || 0}</div></CardContent>
          </Card>
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Projects</CardTitle>
              <Building2 className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent><div className="text-2xl font-bold">{projects.length}</div></CardContent>
          </Card>
        </div>

      </div>
    </Shell>
  );
}
