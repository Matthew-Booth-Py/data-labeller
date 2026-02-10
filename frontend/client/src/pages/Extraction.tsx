import { Shell } from "@/components/layout/Shell";
import { useParams, useLocation } from "wouter";
import { MOCK_PROJECTS } from "@/lib/mockData";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { 
  Upload, 
  FileText, 
  Sparkles, 
  Save, 
  Play, 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  Maximize2,
  MousePointer2,
  Highlighter,
  Type,
  Download,
  ChevronDown
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export default function Extraction() {
  const { id } = useParams();
  const project = MOCK_PROJECTS.find(p => p.id === id) || MOCK_PROJECTS[0];
  const [step, setStep] = useState<'upload' | 'results'>('upload');
  const [isExtracting, setIsExtracting] = useState(false);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({
    'invoice_number': 'INV-2024-001',
    'total_amount': '1,250.00',
    'vendor_name': 'Acme Corp',
    'vendor_address': '123 Business Rd, Tech City',
    'issue_date': '2024-02-06',
    'due_date': '2024-03-06',
    'tax_amount': '125.00',
    'currency': 'USD',
    'po_number': 'PO-998877'
  });
  const [dirtyFields, setDirtyFields] = useState<Record<string, boolean>>({});

  const handleExtract = () => {
    setIsExtracting(true);
    setTimeout(() => {
      setIsExtracting(false);
      setStep('results');
    }, 1500);
  };

  const handleFieldChange = (key: string, value: string) => {
    setFieldValues(prev => ({ ...prev, [key]: value }));
    setDirtyFields(prev => ({ ...prev, [key]: true }));
  };

  if (step === 'upload') {
    return (
      <Shell>
        <div className="p-8 max-w-3xl mx-auto space-y-8">
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold tracking-tight text-primary">Extraction</h1>
            <p className="text-muted-foreground">Test the <span className="text-accent font-semibold">{project.name}</span> pipeline with a live document.</p>
          </div>

          <Card 
            className="border-2 border-dashed border-accent/20 bg-accent/5 py-16 flex flex-col items-center justify-center gap-6 cursor-pointer hover:bg-accent/10 transition-colors group"
            onClick={handleExtract}
          >
            <div className="h-20 w-20 rounded-full bg-white shadow-sm border border-accent/20 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Upload className="h-10 w-10 text-accent" />
            </div>
            <div className="text-center space-y-1">
              <p className="font-semibold text-lg">Drop your document here</p>
              <p className="text-sm text-muted-foreground">PDF, JPEG, or PNG up to 25MB</p>
            </div>
            <Button className="bg-accent hover:bg-accent/90" size="lg" disabled={isExtracting}>
              {isExtracting ? (
                <>
                  <Sparkles className="mr-2 h-5 w-5 animate-pulse" />
                  Extracting...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-5 w-5" />
                  Start Extraction
                </>
              )}
            </Button>
          </Card>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden">
        {/* Left: Advanced Document Previewer */}
        <div className="flex-1 bg-muted/20 border-r relative flex flex-col">
           {/* Preview Toolbar */}
           <div className="h-12 border-b bg-white flex items-center justify-between px-4">
              <div className="flex items-center gap-1 border-r pr-2 mr-2">
                 <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground"><MousePointer2 className="h-4 w-4" /></Button>
                 <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground"><Highlighter className="h-4 w-4" /></Button>
                 <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground"><Type className="h-4 w-4" /></Button>
              </div>
              
              <div className="flex items-center gap-2 bg-muted/10 rounded-md p-0.5">
                 <Button variant="ghost" size="icon" className="h-7 w-7"><ZoomOut className="h-3.5 w-3.5" /></Button>
                 <span className="text-xs font-mono w-12 text-center">100%</span>
                 <Button variant="ghost" size="icon" className="h-7 w-7"><ZoomIn className="h-3.5 w-3.5" /></Button>
              </div>

              <div className="flex items-center gap-1 border-l pl-2 ml-2">
                 <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground"><RotateCcw className="h-4 w-4" /></Button>
                 <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground"><Maximize2 className="h-4 w-4" /></Button>
              </div>
           </div>

           {/* Preview Canvas */}
           <div className="flex-1 overflow-auto p-8 bg-muted/10 flex items-center justify-center relative">
              <Card className="w-full max-w-2xl h-[800px] shadow-2xl relative bg-white border-muted overflow-hidden group">
                 <div className="absolute inset-0 p-12">
                    {/* Mock Document Content */}
                    <div className="w-full h-8 bg-muted/20 mb-8" /> {/* Logo */}
                    <div className="flex justify-between mb-12">
                       <div className="space-y-2 w-1/3">
                          <div className="h-4 bg-muted/30 w-full" />
                          <div className="h-4 bg-muted/30 w-2/3" />
                       </div>
                       <div className="space-y-2 w-1/4">
                          <div className="h-8 bg-muted/40 w-full mb-2" /> {/* Invoice # */}
                          <div className="h-4 bg-muted/30 w-full" />
                       </div>
                    </div>
                    {/* Table */}
                    <div className="w-full border rounded-sm h-64 bg-muted/5 mb-8" />
                    {/* Footer */}
                    <div className="flex justify-end">
                       <div className="w-1/3 space-y-2">
                          <div className="flex justify-between"><div className="w-16 h-4 bg-muted/30"/> <div className="w-12 h-4 bg-accent/20"/></div>
                          <div className="flex justify-between"><div className="w-16 h-4 bg-muted/30"/> <div className="w-12 h-4 bg-accent/20"/></div>
                          <div className="h-px bg-muted w-full my-2"/>
                          <div className="flex justify-between"><div className="w-20 h-6 bg-muted/50"/> <div className="w-24 h-6 bg-emerald-500/20 border border-emerald-500/30"/></div>
                       </div>
                    </div>
                 </div>

                 {/* Interactive Bounding Boxes */}
                 <div className="absolute top-[180px] right-[48px] w-[140px] h-[32px] bg-accent/10 border-2 border-accent/50 cursor-pointer hover:bg-accent/20" title="Invoice Number" />
                 <div className="absolute bottom-[100px] right-[48px] w-[100px] h-[32px] bg-emerald-500/10 border-2 border-emerald-500/50 cursor-pointer hover:bg-emerald-500/20" title="Total Amount" />
              </Card>
           </div>
        </div>

        {/* Right: Extracted Fields Panel */}
        <div className="w-[450px] bg-white flex flex-col border-l shadow-xl z-10">
           <div className="p-4 border-b flex items-center justify-between bg-muted/5">
              <div>
                <h3 className="font-semibold text-primary">Results</h3>
                <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
                   <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-600 bg-emerald-50">High Confidence</Badge>
                   <span className="font-mono">98.4%</span>
                </p>
              </div>
              <div className="flex gap-2">
                 <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                       <Button variant="outline" size="sm" className="h-8 gap-2">
                          <Download className="h-3.5 w-3.5" />
                          Export
                          <ChevronDown className="h-3 w-3 opacity-50" />
                       </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                       <DropdownMenuItem>Export as JSON</DropdownMenuItem>
                       <DropdownMenuItem>Export as CSV</DropdownMenuItem>
                       <DropdownMenuItem>Export as Excel</DropdownMenuItem>
                    </DropdownMenuContent>
                 </DropdownMenu>
                 <Button variant="ghost" size="sm" onClick={() => setStep('upload')}>New</Button>
              </div>
           </div>
           
           <div className="flex-1 overflow-auto p-6 space-y-6">
              {Object.entries(fieldValues).map(([key, value]) => (
                <div key={key} className="space-y-1.5 group">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest flex items-center gap-1">
                       {key.replace(/_/g, ' ')}
                       {dirtyFields[key] && <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />}
                    </label>
                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Badge variant="secondary" className="text-[9px] h-4 px-1">99%</Badge>
                    </div>
                  </div>
                  <div className="relative group/input">
                    <Input 
                      value={value} 
                      onChange={(e) => handleFieldChange(key, e.target.value)}
                      className={cn(
                        "font-medium border-muted focus-visible:ring-accent transition-all",
                        dirtyFields[key] && "border-accent/40 bg-accent/5 pr-8"
                      )}
                    />
                    {dirtyFields[key] && (
                       <Save className="h-3.5 w-3.5 text-accent absolute right-3 top-1/2 -translate-y-1/2 animate-in fade-in zoom-in" />
                    )}
                  </div>
                </div>
              ))}
           </div>
           
           <div className="p-4 border-t bg-muted/5 flex gap-3">
              <Button className="flex-1 bg-primary">Approve & Train</Button>
           </div>
        </div>
      </div>
    </Shell>
  );
}
