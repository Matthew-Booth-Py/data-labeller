import { LucideIcon, FileText, LayoutDashboard, Settings, Layers, Database, Activity, Code, ShieldCheck } from "lucide-react";

export type Project = {
  id: string;
  name: string;
  description: string;
  type: "Invoice" | "Receipt" | "ID Card" | "Contract" | "Financial Statement" | "Slip" | "Screening" | "Claims";
  coverage: number;
  lastEval: string;
  driftRisk: "Low" | "Medium" | "High";
  docCount: number;
  model: string;
};

export type Document = {
  id: string;
  filename: string;
  uploadDate: string;
  status: "Unlabelled" | "Labeled" | "Evaluated" | "Production";
  confidence: number;
  completeness: number;
  thumbnail: string;
  source: "API" | "Manual" | "Email";
};

export type EvaluationRun = {
  id: string;
  date: string;
  model: string;
  promptVersion: string;
  accuracy: number;
  completeness: number;
  cost: number; // per 1k docs
  latency: number; // ms
};

export const MOCK_PROJECTS: Project[] = [
  {
    id: "p1",
    name: "Slip Extraction",
    description: "Automated extraction of Market Reform Contracts and MRC slips for underwriting.",
    type: "Slip",
    coverage: 84,
    lastEval: "2 hours ago",
    driftRisk: "Low",
    docCount: 1240,
    model: "GPT-4o + Azure DI",
  },
  {
    id: "p2",
    name: "Sanctions Screening",
    description: "Screening of policyholders and claimants against global sanctions lists.",
    type: "Screening",
    coverage: 92,
    lastEval: "1 day ago",
    driftRisk: "Low",
    docCount: 8500,
    model: "Claude 3.5 Sonnet",
  },
  {
    id: "p3",
    name: "Claims Extraction",
    description: "Processing of FNOL documents and supporting claim evidence.",
    type: "Claims",
    coverage: 65,
    lastEval: "5 days ago",
    driftRisk: "High",
    docCount: 320,
    model: "GPT-4-Turbo",
  },
];

export const MOCK_DOCUMENTS: Document[] = Array.from({ length: 12 }).map((_, i) => ({
  id: `doc-${i}`,
  filename: `INV-${2024001 + i}_${["Acme", "Globex", "Soylent", "Umbrella"][i % 4]}.pdf`,
  uploadDate: "2024-02-05",
  status: i < 4 ? "Evaluated" : i < 8 ? "Labeled" : "Unlabelled",
  confidence: i < 4 ? 0.95 : i < 8 ? 1.0 : 0.0,
  completeness: i < 4 ? 1.0 : 0.8,
  thumbnail: "/images/doc-preview-invoice.png",
  source: i % 3 === 0 ? "API" : "Manual",
}));

export const MOCK_SCHEMA = {
  invoice_number: { type: "string", description: "Unique identifier for the invoice" },
  invoice_date: { type: "date", format: "YYYY-MM-DD" },
  vendor: {
    type: "object",
    properties: {
      name: { type: "string" },
      address: { type: "string" },
      tax_id: { type: "string" },
    },
  },
  line_items: {
    type: "array",
    items: {
      description: { type: "string" },
      quantity: { type: "number" },
      unit_price: { type: "number" },
      total: { type: "number" },
    },
  },
  total_amount: { type: "number", currency: "USD" },
};

export const MOCK_EVALS: EvaluationRun[] = [
  { id: "run-103", date: "Today, 10:42 AM", model: "GPT-4o", promptVersion: "v2.1", accuracy: 94.2, completeness: 98.5, cost: 0.42, latency: 1200 },
  { id: "run-102", date: "Yesterday, 4:15 PM", model: "GPT-4o", promptVersion: "v2.0", accuracy: 91.8, completeness: 97.0, cost: 0.41, latency: 1150 },
  { id: "run-101", date: "Feb 3, 09:20 AM", model: "GPT-3.5", promptVersion: "v1.5", accuracy: 82.5, completeness: 88.0, cost: 0.05, latency: 600 },
];
