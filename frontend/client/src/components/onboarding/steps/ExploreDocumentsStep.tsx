import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  FileText,
  CheckCircle2,
  Lightbulb,
  Eye,
  FileSearch,
} from "lucide-react";
import { api } from "@/lib/api";

interface ExploreDocumentsStepProps {
  onSelectDocument: (id: string) => void;
  selectedDocumentId: string | null;
}

const SAMPLE_DOCS_INFO = [
  {
    filename: "claim_form_auto_2024.pdf",
    type: "Insurance Claim Form",
    highlights: ["Auto collision claim", "Damage estimate: $3,950", "Police report included"],
  },
  {
    filename: "claim_form_property_2024.pdf",
    type: "Insurance Claim Form",
    highlights: ["Property damage - water", "Burst pipe incident", "Multiple rooms affected"],
  },
  {
    filename: "policy_homeowners_2024.pdf",
    type: "Policy Document",
    highlights: ["HO-3 Special Form", "Coverage limits detailed", "Premium breakdown"],
  },
  {
    filename: "loss_report_theft_2024.pdf",
    type: "Loss Report",
    highlights: ["Burglary incident", "Police report referenced", "Itemized loss valuation"],
  },
  {
    filename: "vendor_invoice_repairs_2024.pdf",
    type: "Vendor Invoice",
    highlights: ["Auto body repair", "Parts and labor itemized", "Tax included"],
  },
  {
    filename: "vendor_invoice_medical_2024.pdf",
    type: "Vendor Invoice",
    highlights: ["Emergency medical services", "CPT codes listed", "ICD-10 diagnosis codes"],
  },
];

export function ExploreDocumentsStep({ onSelectDocument, selectedDocumentId }: ExploreDocumentsStepProps) {
  // Fetch sample documents
  const { data: sampleDocs } = useQuery({
    queryKey: ["sample-documents"],
    queryFn: async () => {
      try {
        return await api.getSampleDocuments();
      } catch (error) {
        console.error("Failed to fetch sample documents:", error);
        return { documents: [], total: 0, expected_total: 6 };
      }
    },
    retry: false,
  });

  // Fetch all documents
  const { data: documentsResponse } = useQuery({
    queryKey: ["documents"],
    queryFn: async () => {
      try {
        return await api.listDocuments();
      } catch (error) {
        console.error("Failed to fetch documents:", error);
        return { documents: [], total: 0 };
      }
    },
    retry: false,
  });

  const documents = documentsResponse?.documents ?? [];

  // Find documents that match our sample docs
  const getDocumentInfo = (filename: string) => {
    const doc = documents.find(d => d.filename === filename);
    const info = SAMPLE_DOCS_INFO.find(s => s.filename === filename);
    return { doc, info };
  };

  return (
    <div className="space-y-6">
      <Alert className="bg-blue-500/10 border-blue-500/20">
        <Lightbulb className="h-4 w-4 text-blue-500" />
        <AlertDescription className="text-blue-700 dark:text-blue-300">
          Review the sample documents below. Each represents a different type of insurance document
          with distinct characteristics. Select one to use in the next steps.
        </AlertDescription>
      </Alert>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {SAMPLE_DOCS_INFO.map((docInfo, i) => {
          const { doc } = getDocumentInfo(docInfo.filename);
          const isSelected = doc?.id === selectedDocumentId;

          return (
            <Card
              key={i}
              className={`cursor-pointer transition-all hover:shadow-md ${
                isSelected ? "border-primary ring-2 ring-primary/20" : ""
              }`}
              onClick={() => doc && onSelectDocument(doc.id)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <CardTitle className="text-base">
                        {docInfo.filename.replace(/_/g, " ").replace(".pdf", "")}
                      </CardTitle>
                      <Badge variant="secondary" className="mt-1">
                        {docInfo.type}
                      </Badge>
                    </div>
                  </div>
                  {isSelected && (
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1">
                  {docInfo.highlights.map((highlight, j) => (
                    <li key={j} className="text-sm text-muted-foreground flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-primary/50" />
                      {highlight}
                    </li>
                  ))}
                </ul>
                {doc ? (
                  <div className="mt-3 flex gap-2">
                    <Button
                      variant={isSelected ? "default" : "outline"}
                      size="sm"
                      className="gap-1"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectDocument(doc.id);
                      }}
                    >
                      {isSelected ? (
                        <>
                          <CheckCircle2 className="h-4 w-4" />
                          Selected
                        </>
                      ) : (
                        <>
                          <Eye className="h-4 w-4" />
                          Select
                        </>
                      )}
                    </Button>
                  </div>
                ) : (
                  <Badge variant="outline" className="mt-3">Not ingested</Badge>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {selectedDocumentId && (
        <div className="flex items-center justify-center gap-2 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          <span className="font-medium text-emerald-700 dark:text-emerald-300">
            Document selected! Click "Next" to classify it.
          </span>
        </div>
      )}
    </div>
  );
}
