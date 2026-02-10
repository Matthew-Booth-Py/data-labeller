import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/components/layout/Shell";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { MOCK_PROJECTS, MOCK_EVALS } from "@/lib/mockData";
import { 
  Activity, 
  FileText, 
  AlertTriangle, 
  CheckCircle2, 
  TrendingUp, 
  Clock, 
  DollarSign,
  ArrowUpRight,
  ArrowDownRight,
  User,
  Building2,
  MapPin,
  Network,
  GraduationCap,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "wouter";
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar
} from "recharts";
import { api } from "@/lib/api";

export default function Dashboard() {
  // Fetch real stats from API
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

  const totalDocs = ingestStatus?.documents || MOCK_PROJECTS.reduce((acc, p) => acc + p.docCount, 0);
  const graphStats = ingestStatus?.graph || {};
  const avgAccuracy = MOCK_EVALS[0].accuracy;

  return (
    <Shell>
      <div className="p-8 max-w-7xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Observability Overview</h1>
          <p className="text-muted-foreground mt-1">System-wide performance and extraction health.</p>
        </div>

        {/* Getting Started Card */}
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
                    New to Unstructured Unlocked? Learn how to classify, annotate, and extract data 
                    from insurance documents with our interactive step-by-step guide.
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

        {/* Global Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Total Documents</CardTitle>
              <FileText className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalDocs.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground mt-1">
                {ingestStatus?.chunks || 0} chunks indexed
              </p>
            </CardContent>
          </Card>
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">People</CardTitle>
              <User className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{(graphStats as any).persons || 0}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Extracted from documents
              </p>
            </CardContent>
          </Card>
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Organizations</CardTitle>
              <Building2 className="h-4 w-4 text-purple-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{(graphStats as any).organizations || 0}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Companies and institutions
              </p>
            </CardContent>
          </Card>
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Relationships</CardTitle>
              <Network className="h-4 w-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{(graphStats as any).relationships || 0}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Connections discovered
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Secondary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Locations</CardTitle>
              <MapPin className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{(graphStats as any).locations || 0}</div>
            </CardContent>
          </Card>
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Events</CardTitle>
              <Activity className="h-4 w-4 text-amber-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{(graphStats as any).events || 0}</div>
            </CardContent>
          </Card>
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Vector DB</CardTitle>
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            </CardHeader>
            <CardContent>
              <div className="text-sm font-medium">{health?.services?.vector_db || "—"}</div>
            </CardContent>
          </Card>
          <Card className="bg-background border-muted-foreground/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Graph DB</CardTitle>
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            </CardHeader>
            <CardContent>
              <div className="text-sm font-medium">{health?.services?.neo4j || "—"}</div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Traffic Chart */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Extraction Volume</CardTitle>
              <CardDescription>Documents processed across all projects.</CardDescription>
            </CardHeader>
            <CardContent className="h-[300px] pl-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={MOCK_EVALS.reverse()}>
                  <defs>
                    <linearGradient id="colorVol" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted))" />
                  <XAxis dataKey="date" hide />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={10} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Area type="monotone" dataKey="accuracy" stroke="hsl(var(--primary))" fillOpacity={1} fill="url(#colorVol)" />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Project Health Table */}
          <Card>
            <CardHeader>
              <CardTitle>Project Health</CardTitle>
              <CardDescription>Risk and coverage by pipeline.</CardDescription>
            </CardHeader>
            <CardContent className="px-0">
              <div className="space-y-4">
                {MOCK_PROJECTS.map((p) => (
                  <div key={p.id} className="flex items-center justify-between px-6 py-2 hover:bg-muted/50 transition-colors">
                    <div className="space-y-0.5">
                      <p className="text-sm font-medium">{p.name}</p>
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${p.driftRisk === 'High' ? 'bg-rose-500' : 'bg-emerald-500'}`} />
                        <span className="text-[10px] text-muted-foreground uppercase">{p.driftRisk} Risk</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-mono font-bold">{p.coverage}%</p>
                      <p className="text-[10px] text-muted-foreground uppercase">Coverage</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </Shell>
  );
}
