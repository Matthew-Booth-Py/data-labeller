import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/components/layout/Shell";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import {
  FileText,
  Building2,
  GraduationCap,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "wouter";
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
  
  // Get projects from localStorage
  const projects = (() => {
    try {
      const stored = localStorage.getItem("uu-projects");
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  })();

  return (
    <Shell>
      <div className="p-8 max-w-7xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Observability Overview</h1>
          <p className="text-muted-foreground mt-1">System-wide performance and extraction health.</p>
        </div>

        <Card className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent border-primary/20">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-xl bg-primary/10">
                  <GraduationCap className="h-8 w-8 text-primary" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    Getting Started Tutorial
                    <Sparkles className="h-4 w-4 text-amber-500" />
                  </h3>
                  <p className="text-sm text-muted-foreground max-w-xl">
                    Learn how to define schemas, classify documents, and extract structured data from real documents.
                  </p>
                </div>
              </div>
              <Link href="/getting-started">
                <Button className="gap-2">
                  Start Tutorial
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Total Documents</CardTitle>
              <FileText className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalDocs.toLocaleString()}</div>
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
