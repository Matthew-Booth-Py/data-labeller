import { Shell } from "@/components/layout/Shell";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Cpu, 
  Database
} from "lucide-react";
import { useState } from "react";

export default function Settings() {
  const [activeTab, setActiveTab] = useState('llm');

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
        <div className="w-64 border-r bg-muted/5 p-4 flex flex-col gap-1">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-2 text-primary">Global Settings</h2>
          <Button 
            variant="ghost" 
            className={`justify-start gap-2 ${activeTab === 'llm' ? 'bg-primary text-primary-foreground hover:bg-primary' : 'text-muted-foreground hover:bg-accent/10 hover:text-accent'}`}
            onClick={() => setActiveTab('llm')}
          >
            <Cpu className="h-4 w-4" />
            LLM Configuration
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

        <div className="flex-1 overflow-auto bg-background">
          <div className="p-8 max-w-5xl mx-auto space-y-8">
            {activeTab === 'llm' && (
              <>
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight text-primary">LLM Configuration</h1>
                  <p className="text-muted-foreground mt-1">LLM model is configured in backend settings.</p>
                </div>

                <div className="grid gap-6">
                  <Card className="border-accent/10 bg-card">
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded border bg-muted/50 flex items-center justify-center">
                          <img src="https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg" className="h-6 w-6 grayscale" alt="OpenAI" />
                        </div>
                        <div>
                          <CardTitle className="text-lg">Azure OpenAI</CardTitle>
                          <CardDescription>Centralized LLM configuration</CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="space-y-2">
                        <div className="text-sm text-muted-foreground">
                          <p>The LLM model is configured in the backend <code className="text-xs bg-muted px-1 py-0.5 rounded">.env</code> file.</p>
                          <p className="mt-2">Current model: <Badge variant="outline" className="ml-2 font-mono">gpt-5-mini</Badge></p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </>
            )}

            {activeTab === 'engines' && (
              <>
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight text-primary">Extraction Engines</h1>
                  <p className="text-muted-foreground mt-1">Manage OCR and document analysis services.</p>
                </div>

                <div className="grid gap-6">
                  <Card className="border-accent/10 bg-card">
                    <CardHeader>
                      <CardTitle className="text-lg">No Engines Configured</CardTitle>
                      <CardDescription>This section currently has no backend persistence.</CardDescription>
                    </CardHeader>
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
