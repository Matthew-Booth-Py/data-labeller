import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, Copy, ShieldCheck, Webhook } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState } from "react";

export function APIManagement() {
  const apiKeysEnabled = false;
  const [backgroundProcessing, setBackgroundProcessing] = useState<
    Record<string, boolean>
  >({});
  const keys: Array<{
    id: string;
    name: string;
    key: string;
    created: string;
  }> = [];

  const toggleProcessing = (id: string, checked: boolean) => {
    setBackgroundProcessing((prev) => ({ ...prev, [id]: checked }));
  };

  return (
    <div className="w-full max-w-full min-w-0 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-medium text-primary">Project API Keys</h3>
          <p className="text-sm text-muted-foreground break-words">
            Manage keys specifically for this project's extraction pipeline.
          </p>
        </div>
        <Button className="gap-2 shrink-0" variant="secondary" disabled>
          <Plus className="h-4 w-4" />
          Create New Key (Coming Soon)
        </Button>
      </div>

      <div className="grid gap-4 min-w-0">
        {keys.map((key) => (
          <Card
            key={key.id}
            className="border-muted hover:border-primary/25 transition-all bg-[var(--surface-panel)] min-w-0"
          >
            <CardContent className="p-4 space-y-4 min-w-0">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-1 flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm">{key.name}</span>
                    <Badge
                      variant="outline"
                      className="text-[10px] uppercase border-emerald-500/20 text-emerald-600"
                    >
                      Active
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2 mt-1 min-w-0">
                    <div className="bg-muted px-2 py-1 rounded font-mono text-xs text-muted-foreground flex items-center gap-2 min-w-0 max-w-full">
                      <span className="truncate">{key.key}</span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-4 w-4 shrink-0"
                        disabled={!apiKeysEnabled}
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                </div>
                <div className="text-right flex items-center gap-4 sm:gap-8 shrink-0 flex-wrap">
                  <div className="space-y-0.5">
                    <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                      Created
                    </p>
                    <p className="text-xs">{key.created}</p>
                  </div>
                  <div className="flex items-center gap-4 border-l pl-4">
                    <div className="flex flex-col items-end gap-1">
                      <Label className="text-[10px] uppercase font-bold text-muted-foreground">
                        Background Processing
                      </Label>
                      <Switch
                        checked={backgroundProcessing[key.id]}
                        onCheckedChange={(checked) =>
                          toggleProcessing(key.id, checked)
                        }
                        disabled={!apiKeysEnabled}
                      />
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-muted-foreground hover:text-destructive shrink-0"
                    disabled={!apiKeysEnabled}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              {backgroundProcessing[key.id] && (
                <div className="pt-4 border-t border-dashed space-y-3 animate-in fade-in slide-in-from-top-2 duration-200 min-w-0">
                  <div className="flex items-center gap-2 text-xs font-semibold text-accent">
                    <Webhook className="h-3.5 w-3.5 shrink-0" />
                    Configure Webhook Endpoint
                  </div>
                  <div className="flex gap-2 min-w-0 flex-wrap">
                    <Input
                      placeholder="https://your-api.com/webhooks/ingestion"
                      className="h-9 text-sm min-w-0 flex-1"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-primary/30 text-primary shrink-0"
                      disabled={!apiKeysEnabled}
                    >
                      Test
                    </Button>
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Events will be sent as POST requests with the extraction
                    payload.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
        {keys.length === 0 && (
          <Card className="border-muted bg-[var(--surface-panel)] min-w-0">
            <CardContent className="p-4 text-sm text-muted-foreground break-words">
              API key storage is not yet wired to backend persistence. No
              synthetic keys are shown, and key actions remain disabled until
              persistence is enabled.
            </CardContent>
          </Card>
        )}
      </div>

      <Card className="bg-primary/5 border-primary/20 min-w-0">
        <CardHeader className="py-3">
          <CardTitle className="text-xs flex items-center gap-2 text-primary font-bold uppercase tracking-wider">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            Security Best Practices
          </CardTitle>
        </CardHeader>
        <CardContent className="text-[11px] text-muted-foreground space-y-2 break-words">
          <p>
            • Never share your API keys in public repositories or client-side
            code.
          </p>
          <p>
            • Use separate keys for staging and production environments to
            minimize blast radius.
          </p>
          <p>
            • Background processing requires a valid HTTPS endpoint for reliable
            delivery.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
