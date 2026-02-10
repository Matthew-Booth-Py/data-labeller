import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Copy, Terminal, PlayCircle, Rocket, CheckCircle2, History } from "lucide-react";
import { useEffect, useState } from "react";

export function DeploymentView() {
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await fetch("/api/v1/evaluation?limit=10");
        if (!response.ok) return;
        const data = await response.json();
        setRuns(data.evaluations || []);
      } catch {
        setRuns([]);
      }
    };
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Promotion Panel */}
        <div className="lg:col-span-2 space-y-6">
            <Card className="border-accent/30 bg-accent/5">
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-lg flex items-center gap-2">
                                <Rocket className="h-5 w-5 text-accent" />
                                Active Deployment
                            </CardTitle>
                            <CardDescription>Select a validated evaluation run to promote to production.</CardDescription>
                        </div>
                        <Badge className="bg-emerald-500">v2.4 Live</Badge>
                    </div>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="rounded-md border bg-background overflow-hidden">
                        <div className="grid grid-cols-6 p-3 bg-muted/30 border-b text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                            <div className="col-span-2">Run / Version</div>
                            <div>Accuracy</div>
                            <div>Completeness</div>
                            <div className="col-span-2 text-right">Action</div>
                        </div>
                        {runs.map((run, i) => (
                            <div key={run.id} className={`grid grid-cols-6 p-4 items-center border-b last:border-0 text-sm ${i === 0 ? 'bg-accent/5' : ''}`}>
                                <div className="col-span-2">
                                    <div className="font-medium flex items-center gap-2">
                                        {run.prompt_version_name || "default"}
                                        {i === 0 && <Badge className="bg-accent h-4 text-[9px] px-1 uppercase">Current</Badge>}
                                    </div>
                                    <div className="text-xs text-muted-foreground">{new Date(run.evaluated_at).toLocaleString()}</div>
                                </div>
                                <div className="font-mono text-emerald-500">{((run.metrics?.accuracy || 0) * 100).toFixed(1)}%</div>
                                <div className="font-mono">{((run.metrics?.recall || 0) * 100).toFixed(1)}%</div>
                                <div className="col-span-2 text-right">
                                    {i === 0 ? (
                                        <Button size="sm" variant="ghost" className="text-emerald-500 gap-2 pointer-events-none">
                                            <CheckCircle2 className="h-3.5 w-3.5" /> Deployed
                                        </Button>
                                    ) : (
                                        <Button size="sm" variant="outline" className="border-accent/30 text-accent hover:bg-accent/10">
                                            Promote to Production
                                        </Button>
                                    )}
                                </div>
                            </div>
                        ))}
                        {runs.length === 0 && (
                            <div className="p-4 text-sm text-muted-foreground">No evaluation runs found.</div>
                        )}
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                        API Endpoint
                        <Badge variant="outline" className="text-emerald-500 border-emerald-500/30 bg-emerald-500/10 uppercase text-[10px]">Production ready</Badge>
                    </CardTitle>
                    <CardDescription>Production endpoint for this project's extraction pipeline.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center gap-2 p-3 bg-black rounded-md border border-zinc-800 font-mono text-sm overflow-hidden text-zinc-300">
                        <span className="text-accent font-bold">POST</span>
                        <span className="truncate">https://api.intelligent-ingestion.ai/v1/extract</span>
                        <Button size="icon" variant="ghost" className="ml-auto h-6 w-6 text-zinc-500 hover:text-accent"><Copy className="h-3 w-3" /></Button>
                    </div>

                    <div className="space-y-2 pt-2">
                        <label className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">Example CURL</label>
                        <pre className="p-4 bg-black text-zinc-400 rounded-md font-mono text-xs overflow-x-auto border border-zinc-800">
{`curl -X POST https://api.intelligent-ingestion.ai/v1/extract \\
  -H "Authorization: Bearer $II_API_KEY" \\
  -H "X-Project-ID: p1" \\
  -F "file=@invoice.pdf"`}
                        </pre>
                    </div>
                </CardContent>
            </Card>
        </div>

        {/* Status / Config */}
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <History className="h-4 w-4" />
                        Version History
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 text-sm">
                    {[
                        { v: 'v2.4', date: '2h ago', user: 'Jane D.', status: 'Live' },
                        { v: 'v2.3', date: '1d ago', user: 'Jane D.', status: 'Archived' },
                        { v: 'v2.2', date: '3d ago', user: 'System', status: 'Archived' },
                    ].map(v => (
                        <div key={v.v} className="flex justify-between items-center py-2 border-b last:border-0">
                            <div className="space-y-0.5">
                                <span className="font-medium">{v.v}</span>
                                <p className="text-[10px] text-muted-foreground">{v.date} by {v.user}</p>
                            </div>
                            <Badge variant={v.status === 'Live' ? 'default' : 'outline'} className={v.status === 'Live' ? 'bg-accent' : ''}>
                                {v.status}
                            </Badge>
                        </div>
                    ))}
                    <Button className="w-full mt-2" variant="outline">View Full Changelog</Button>
                </CardContent>
            </Card>
            
            <div className="rounded-lg border bg-accent/5 p-4 border-accent/20">
                <div className="flex items-start gap-3">
                    <Terminal className="h-5 w-5 text-accent mt-0.5" />
                    <div>
                        <h4 className="text-sm font-medium">Version Sandbox</h4>
                        <p className="text-xs text-muted-foreground mt-1">Dry run the current staging config before promoting.</p>
                        <Button size="sm" className="mt-3 gap-2 bg-accent hover:bg-accent/90">
                            <PlayCircle className="h-3.5 w-3.5" />
                            Open Sandbox
                        </Button>
                    </div>
                </div>
            </div>
        </div>
      </div>
    </div>
  );
}
