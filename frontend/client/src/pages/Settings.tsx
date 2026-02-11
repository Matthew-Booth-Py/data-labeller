import { Shell } from "@/components/layout/Shell";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { 
  Plus, 
  Cpu, 
  Database, 
  MoreVertical,
  Loader2,
  Trash2
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

export default function Settings() {
  const [activeTab, setActiveTab] = useState('llm');
  const [providerLoading, setProviderLoading] = useState(false);
  const [providerSaving, setProviderSaving] = useState(false);
  const [providerTesting, setProviderTesting] = useState(false);
  const [maskedKey, setMaskedKey] = useState("");
  const [keyInput, setKeyInput] = useState("");
  const [lastStatus, setLastStatus] = useState<"unknown" | "connected" | "failed">("unknown");
  const [source, setSource] = useState<"override" | "env" | "none">("none");
  const [hasKey, setHasKey] = useState(false);
  const [lastTestedAt, setLastTestedAt] = useState<string | null>(null);
  const [providerModels, setProviderModels] = useState<Array<{ model_id: string; display_name?: string | null; is_enabled: boolean }>>([]);
  const [newModelId, setNewModelId] = useState("");
  const [newModelName, setNewModelName] = useState("");
  const [modelSaving, setModelSaving] = useState(false);
  const [modelTesting, setModelTesting] = useState<Record<string, boolean>>({});
  const { toast } = useToast();

  const keyChanged = useMemo(() => keyInput !== maskedKey, [keyInput, maskedKey]);

  const loadProvider = async () => {
    setProviderLoading(true);
    try {
      const [status, models] = await Promise.all([
        api.getOpenAIProviderStatus(),
        api.listOpenAIProviderModels(false),
      ]);
      setMaskedKey(status.masked_api_key || "");
      setKeyInput(status.masked_api_key || "");
      setLastStatus(status.last_test_status);
      setSource(status.source);
      setHasKey(status.has_key);
      setLastTestedAt(status.last_tested_at || null);
      setProviderModels(models.models || []);
    } catch (error: any) {
      toast({
        title: "Failed to load provider settings",
        description: error.message || "Could not load OpenAI provider config.",
        variant: "destructive",
      });
    } finally {
      setProviderLoading(false);
    }
  };

  const addModel = async () => {
    const modelId = newModelId.trim();
    if (!modelId) return;
    setModelSaving(true);
    try {
      await api.createOpenAIProviderModel({
        model_id: modelId,
        display_name: newModelName.trim() || undefined,
        is_enabled: true,
      });
      setNewModelId("");
      setNewModelName("");
      const models = await api.listOpenAIProviderModels(false);
      setProviderModels(models.models || []);
      toast({ title: "Model added", description: `${modelId} is now available in schema model choices.` });
    } catch (error: any) {
      toast({
        title: "Failed to add model",
        description: error.message || "Could not register model.",
        variant: "destructive",
      });
    } finally {
      setModelSaving(false);
    }
  };

  const toggleModel = async (modelId: string, isEnabled: boolean) => {
    try {
      await api.updateOpenAIProviderModel(modelId, { is_enabled: !isEnabled });
      const models = await api.listOpenAIProviderModels(false);
      setProviderModels(models.models || []);
    } catch (error: any) {
      toast({
        title: "Failed to update model",
        description: error.message || "Could not update model status.",
        variant: "destructive",
      });
    }
  };

  const deleteModel = async (modelId: string) => {
    try {
      await api.deleteOpenAIProviderModel(modelId);
      const models = await api.listOpenAIProviderModels(false);
      setProviderModels(models.models || []);
      toast({ title: "Model removed", description: `${modelId} removed from available model list.` });
    } catch (error: any) {
      toast({
        title: "Failed to remove model",
        description: error.message || "Could not delete model.",
        variant: "destructive",
      });
    }
  };

  const testModel = async (modelId: string) => {
    setModelTesting((prev) => ({ ...prev, [modelId]: true }));
    try {
      const result = await api.testOpenAIProviderModel(modelId);
      setLastStatus(result.connected ? "connected" : "failed");
      setLastTestedAt(result.tested_at);
      toast({
        title: result.connected ? "Model connected" : "Model connection failed",
        description: result.message,
        variant: result.connected ? "default" : "destructive",
      });
    } catch (error: any) {
      setLastStatus("failed");
      toast({
        title: "Model test failed",
        description: error.message || `Could not test model ${modelId}.`,
        variant: "destructive",
      });
    } finally {
      setModelTesting((prev) => ({ ...prev, [modelId]: false }));
    }
  };

  useEffect(() => {
    if (activeTab === "llm") {
      loadProvider();
    }
  }, [activeTab]);

  const handleSaveKey = async () => {
    const trimmed = keyInput.trim();
    // If still masked + unchanged, do nothing.
    if (!keyChanged) return;
    setProviderSaving(true);
    try {
      const response = await api.updateOpenAIProvider({ api_key: trimmed });
      setMaskedKey(response.masked_api_key || "");
      setKeyInput(response.masked_api_key || "");
      setLastStatus(response.last_test_status);
      setSource(response.source);
      setHasKey(response.has_key);
      setLastTestedAt(response.last_tested_at || null);
      toast({
        title: "OpenAI key updated",
        description: "Provider key was saved successfully.",
      });
    } catch (error: any) {
      toast({
        title: "Failed to update key",
        description: error.message || "Could not save provider key.",
        variant: "destructive",
      });
    } finally {
      setProviderSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setProviderTesting(true);
    try {
      // If user edited key input, test that value directly.
      const testPayload = keyChanged ? { api_key: keyInput.trim() } : undefined;
      const result = await api.testOpenAIProvider(testPayload);
      setLastStatus(result.connected ? "connected" : "failed");
      setLastTestedAt(result.tested_at);
      if (result.connected) {
        setHasKey(true);
      }
      toast({
        title: result.connected ? "Connected" : "Connection failed",
        description: result.message,
        variant: result.connected ? "default" : "destructive",
      });
    } catch (error: any) {
      setLastStatus("failed");
      toast({
        title: "Connection failed",
        description: error.message || "Could not connect to OpenAI.",
        variant: "destructive",
      });
    } finally {
      setProviderTesting(false);
    }
  };

  return (
    <Shell>
      <div className="flex h-[calc(100vh-3.5rem)]">
        {/* Settings Sidebar */}
        <div className="w-64 border-r bg-muted/5 p-4 flex flex-col gap-1">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-2 text-primary">Global Settings</h2>
          <Button 
            variant="ghost" 
            className={`justify-start gap-2 ${activeTab === 'llm' ? 'bg-primary text-primary-foreground hover:bg-primary' : 'text-muted-foreground hover:bg-accent/10 hover:text-accent'}`}
            onClick={() => setActiveTab('llm')}
          >
            <Cpu className="h-4 w-4" />
            LLM Providers
          </Button>
          <Button 
            variant="ghost" 
            className={`justify-start gap-2 ${activeTab === 'engines' ? 'bg-primary text-primary-foreground hover:bg-primary' : 'text-muted-foreground hover:bg-accent/10 hover:text-accent'}`}
            onClick={() => setActiveTab('engines')}
          >
            <Database className="h-4 w-4" />
            Extraction Engines
          </Button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-auto bg-background">
          <div className="p-8 max-w-5xl mx-auto space-y-8">
            {activeTab === 'llm' && (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <h1 className="text-2xl font-semibold tracking-tight text-primary">LLM Providers</h1>
                    <p className="text-muted-foreground mt-1">Configure models and endpoints for Intelligent Ingestion.</p>
                  </div>
                  <Button className="gap-2 bg-accent hover:bg-accent/90">
                    <Plus className="h-4 w-4" />
                    Add Provider
                  </Button>
                </div>

                <div className="grid gap-6">
                  <Card className="border-accent/10 bg-card">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded border bg-muted/50 flex items-center justify-center">
                          <img src="https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg" className="h-6 w-6 grayscale" alt="OpenAI" />
                        </div>
                        <div>
                          <CardTitle className="text-lg">OpenAI</CardTitle>
                          <CardDescription>Primary extraction backbone</CardDescription>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          className={
                            lastStatus === "connected"
                              ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20 uppercase text-[10px]"
                              : "bg-muted text-muted-foreground border-border uppercase text-[10px]"
                          }
                        >
                          {lastStatus === "connected" ? "Connected" : "Not Connected"}
                        </Badge>
                        <Button variant="ghost" size="icon"><MoreVertical className="h-4 w-4 text-muted-foreground" /></Button>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                          <span>API Key</span>
                          <span>Source: {source}</span>
                        </div>
                        <Input
                          value={keyInput}
                          onChange={(e) => setKeyInput(e.target.value)}
                          placeholder="SK_****"
                          autoComplete="off"
                          spellCheck={false}
                          disabled={providerLoading}
                        />
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            onClick={handleSaveKey}
                            disabled={providerSaving || providerLoading || !keyChanged}
                          >
                            {providerSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Save Key
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={handleTestConnection}
                            disabled={providerTesting || providerLoading || (!hasKey && !keyInput.trim())}
                          >
                            {providerTesting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Test Connection
                          </Button>
                          {lastTestedAt && (
                            <span className="text-xs text-muted-foreground">
                              Last tested: {new Date(lastTestedAt).toLocaleString()}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="space-y-4">
                        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-muted-foreground border-b pb-2">
                          <span>Model Configuration (Available in Schema)</span>
                          <div className="flex gap-16">
                            <span className="w-24">Status</span>
                            <span className="w-20 text-right">Action</span>
                          </div>
                        </div>
                        <div className="space-y-2">
                          {providerModels.map((model) => (
                            <div
                              key={model.model_id}
                              className="flex items-center justify-between border rounded-md px-3 py-2 text-sm"
                            >
                              <div className="min-w-0">
                                <div className="font-mono truncate">{model.model_id}</div>
                                {model.display_name && (
                                  <div className="text-xs text-muted-foreground truncate">{model.display_name}</div>
                                )}
                              </div>
                              <div className="flex items-center gap-2">
                                <Badge variant={model.is_enabled ? "default" : "secondary"}>
                                  {model.is_enabled ? "Enabled" : "Disabled"}
                                </Badge>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => testModel(model.model_id)}
                                  disabled={!model.is_enabled || !!modelTesting[model.model_id]}
                                >
                                  {modelTesting[model.model_id] && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                  Test
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => toggleModel(model.model_id, model.is_enabled)}
                                >
                                  {model.is_enabled ? "Disable" : "Enable"}
                                </Button>
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="text-destructive"
                                  onClick={() => deleteModel(model.model_id)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <Input
                            value={newModelId}
                            onChange={(e) => setNewModelId(e.target.value)}
                            placeholder="Model ID (e.g. gpt-5-mini)"
                          />
                          <Input
                            value={newModelName}
                            onChange={(e) => setNewModelName(e.target.value)}
                            placeholder="Display name (optional)"
                          />
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="w-full border-dashed border h-9 text-xs text-muted-foreground hover:text-accent hover:border-accent/50"
                          onClick={addModel}
                          disabled={modelSaving || !newModelId.trim()}
                        >
                          {modelSaving ? <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" /> : <Plus className="h-3.5 w-3.5 mr-2" />}
                          Register New Model
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </>
            )}

            {activeTab === 'engines' && (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <h1 className="text-2xl font-semibold tracking-tight text-primary">Extraction Engines</h1>
                    <p className="text-muted-foreground mt-1">Manage OCR and document analysis services.</p>
                  </div>
                  <Button className="gap-2 bg-accent hover:bg-accent/90">
                    <Plus className="h-4 w-4" />
                    New Engine
                  </Button>
                </div>

                <div className="grid gap-6">
                  <Card className="border-accent/10 bg-card">
                    <CardHeader>
                      <CardTitle className="text-lg">No Engines Configured</CardTitle>
                      <CardDescription>This section currently has no backend persistence and shows no synthetic rows.</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Button variant="outline" size="sm" className="w-full">Configure First Engine</Button>
                    </CardContent>
                  </Card>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </Shell>
  );
}
