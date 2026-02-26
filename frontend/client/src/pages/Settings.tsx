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
import { Cpu, Database, ExternalLink, Info } from "lucide-react";
import { useState } from "react";

type SettingsTab = "llm" | "engines";

export default function Settings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("llm");

  return (
    <Shell
      section="settings"
      pageTitle="Settings"
      pageDescription="Manage global LLM and extraction runtime configuration."
      showProjectRail
    >
      <div className="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-6">
        <aside className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-panel)] p-3 h-fit">
          <h2 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-2">
            Global Settings
          </h2>
          <div className="space-y-1">
            <Button
              variant={activeTab === "llm" ? "primary" : "quiet"}
              className="w-full justify-start gap-2"
              onClick={() => setActiveTab("llm")}
            >
              <Cpu className="h-4 w-4" />
              LLM Configuration
            </Button>
            <Button
              variant={activeTab === "engines" ? "primary" : "quiet"}
              className="w-full justify-start gap-2"
              onClick={() => setActiveTab("engines")}
            >
              <Database className="h-4 w-4" />
              Extraction Engines
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
                </div>
              </CardContent>
            </Card>
          )}
        </section>
      </div>
    </Shell>
  );
}
