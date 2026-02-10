import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, Copy, ShieldCheck, Webhook } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState } from "react";

export function APIManagement() {
  const [backgroundProcessing, setBackgroundProcessing] = useState<Record<string, boolean>>({});
  const keys: Array<{ id: string; name: string; key: string; created: string }> = [];

  const toggleProcessing = (id: string, checked: boolean) => {
    setBackgroundProcessing(prev => ({ ...prev, [id]: checked }));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-primary">Project API Keys</h3>
          <p className="text-sm text-muted-foreground">Manage keys specifically for this project's extraction pipeline.</p>
        </div>
        <Button className="gap-2 bg-accent hover:bg-accent/90">
          <Plus className="h-4 w-4" />
          Create New Key
        </Button>
      </div>

      <div className="grid gap-4">
        {keys.map((key) => (
          <Card key={key.id} className="border-muted hover:border-accent/30 transition-all bg-white">
            <CardContent className="p-4 space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm">{key.name}</span>
                    <Badge variant="outline" className="text-[10px] uppercase border-emerald-500/20 text-emerald-600">Active</Badge>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <div className="bg-muted px-2 py-1 rounded font-mono text-xs text-muted-foreground flex items-center gap-2">
                      {key.key}
                      <Button variant="ghost" size="icon" className="h-4 w-4"><Copy className="h-3 w-3" /></Button>
                    </div>
                  </div>
                </div>
                <div className="text-right flex items-center gap-8 mr-4">
                  <div className="space-y-0.5">
                    <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">Created</p>
                    <p className="text-xs">{key.created}</p>
                  </div>
                  <div className="flex items-center gap-4 border-l pl-4">
                     <div className="flex flex-col items-end gap-1">
                       <Label className="text-[10px] uppercase font-bold text-muted-foreground">Background Processing</Label>
                       <Switch 
                         checked={backgroundProcessing[key.id]} 
                         onCheckedChange={(checked) => toggleProcessing(key.id, checked)}
                       />
                     </div>
                  </div>
                </div>
                <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive ml-2">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>

              {backgroundProcessing[key.id] && (
                <div className="pt-4 border-t border-dashed space-y-3 animate-in fade-in slide-in-from-top-2 duration-200">
                  <div className="flex items-center gap-2 text-xs font-semibold text-accent">
                    <Webhook className="h-3.5 w-3.5" />
                    Configure Webhook Endpoint
                  </div>
                  <div className="flex gap-2">
                    <Input placeholder="https://your-api.com/webhooks/ingestion" className="h-9 text-sm" />
                    <Button size="sm" variant="outline" className="border-accent text-accent">Test</Button>
                  </div>
                  <p className="text-[10px] text-muted-foreground">Events will be sent as POST requests with the extraction payload.</p>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
        {keys.length === 0 && (
          <Card className="border-muted bg-white">
            <CardContent className="p-4 text-sm text-muted-foreground">
              API key storage is not yet wired to backend persistence. No synthetic keys are shown.
            </CardContent>
          </Card>
        )}
      </div>

      <Card className="bg-primary/5 border-primary/20">
        <CardHeader className="py-3">
           <CardTitle className="text-xs flex items-center gap-2 text-primary font-bold uppercase tracking-wider">
             <ShieldCheck className="h-4 w-4" />
             Security Best Practices
           </CardTitle>
        </CardHeader>
        <CardContent className="text-[11px] text-muted-foreground space-y-2">
           <p>• Never share your API keys in public repositories or client-side code.</p>
           <p>• Use separate keys for staging and production environments to minimize blast radius.</p>
           <p>• Background processing requires a valid HTTPS endpoint for reliable delivery.</p>
        </CardContent>
      </Card>
    </div>
  );
}
