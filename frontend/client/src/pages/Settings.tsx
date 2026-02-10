import { Shell } from "@/components/layout/Shell";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Plus, 
  Trash2, 
  Settings2, 
  Cpu, 
  Database, 
  MoreVertical,
  CheckCircle2,
  ChevronRight
} from "lucide-react";
import { useState } from "react";

const MOCK_MODELS = [
  { id: 'm1', name: 'GPT-4o', provider: 'OpenAI', status: 'active', tokens: '128k' },
  { id: 'm2', name: 'GPT-4o mini', provider: 'OpenAI', status: 'active', tokens: '128k' },
  { id: 'm3', name: 'Claude 3.5 Sonnet', provider: 'Anthropic', status: 'active', tokens: '200k' },
];

const MOCK_ENGINES = [
  { id: 'e1', name: 'Azure DI Prebuilt', type: 'OCR', region: 'East US', status: 'connected' },
  { id: 'e2', name: 'AWS Textract', type: 'OCR', region: 'Global', status: 'inactive' },
];

export default function Settings() {
  const [activeTab, setActiveTab] = useState('llm');

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
                  <Card className="border-accent/10 bg-white">
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
                        <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 uppercase text-[10px]">Connected</Badge>
                        <Button variant="ghost" size="icon"><MoreVertical className="h-4 w-4 text-muted-foreground" /></Button>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <div className="space-y-4">
                        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-muted-foreground border-b pb-2">
                          <span>Model Configuration</span>
                          <div className="flex gap-16">
                            <span className="w-24">Context</span>
                            <span className="w-20 text-right">Action</span>
                          </div>
                        </div>
                        {MOCK_MODELS.filter(m => m.provider === 'OpenAI').map(model => (
                          <div key={model.id} className="flex items-center justify-between group py-1">
                            <div className="flex items-center gap-2">
                              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                              <span className="font-medium text-sm">{model.name}</span>
                            </div>
                            <div className="flex items-center gap-16 text-xs">
                              <span className="font-mono text-muted-foreground w-24">{model.tokens}</span>
                              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity w-20 justify-end">
                                <Button variant="ghost" size="icon" className="h-7 w-7"><Settings2 className="h-3.5 w-3.5" /></Button>
                                <Button variant="ghost" size="icon" className="h-7 w-7 hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></Button>
                              </div>
                            </div>
                          </div>
                        ))}
                        <Button variant="ghost" size="sm" className="w-full border-dashed border h-9 text-xs text-muted-foreground hover:text-accent hover:border-accent/50">
                          <Plus className="h-3.5 w-3.5 mr-2" /> Register New Model
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
                  {MOCK_ENGINES.map(engine => (
                    <Card key={engine.id} className="border-accent/10 bg-white">
                      <CardHeader className="flex flex-row items-center justify-between space-y-0">
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 rounded border bg-muted/50 flex items-center justify-center">
                            <Database className="h-5 w-5 text-indigo-500" />
                          </div>
                          <div>
                            <CardTitle className="text-lg">{engine.name}</CardTitle>
                            <CardDescription>{engine.type} • {engine.region}</CardDescription>
                          </div>
                        </div>
                        <Badge variant={engine.status === 'connected' ? 'default' : 'outline'} className={engine.status === 'connected' ? 'bg-emerald-500' : ''}>
                          {engine.status}
                        </Badge>
                      </CardHeader>
                      <CardContent>
                        <div className="flex gap-2">
                           <Button variant="outline" size="sm" className="flex-1">Configure Endpoint</Button>
                           <Button variant="ghost" size="icon" className="h-9 w-9 text-muted-foreground hover:text-destructive"><Trash2 className="h-4 w-4" /></Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </Shell>
  );
}
