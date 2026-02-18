/**
 * PdfAnnotator - Component for annotating PDFs with text selection and bounding boxes
 */

import { useState, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, ZoomIn, ZoomOut, CheckCircle2 } from "lucide-react";
import type { GroundTruthAnnotation, BoundingBoxData } from "@/lib/api";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Set up PDF.js worker - use version-matched worker from CDN
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfAnnotatorProps {
  documentId: string;
  pdfUrl: string;
  annotations: GroundTruthAnnotation[];
  selectedField: string | null;
  onAnnotationCreate: (fieldName: string, value: string, annotationData: BoundingBoxData) => void;
  onAnnotationDelete: (annotationId: string) => void;
}

const FIELD_COLORS = [
  "rgba(255, 235, 59, 0.3)",   // yellow
  "rgba(76, 175, 80, 0.3)",    // green
  "rgba(33, 150, 243, 0.3)",   // blue
  "rgba(156, 39, 176, 0.3)",   // purple
  "rgba(233, 30, 99, 0.3)",    // pink
  "rgba(255, 152, 0, 0.3)",    // orange
  "rgba(0, 188, 212, 0.3)",    // cyan
  "rgba(244, 67, 54, 0.3)",    // red
];

export function PdfAnnotator({
  documentId,
  pdfUrl,
  annotations,
  selectedField,
  onAnnotationCreate,
  onAnnotationDelete,
}: PdfAnnotatorProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState(1.0);
  const [fieldColorMap, setFieldColorMap] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  // Assign colors to fields
  useEffect(() => {
    const uniqueFields = Array.from(new Set(annotations.map(a => a.field_name)));
    const colorMap: Record<string, string> = {};
    uniqueFields.forEach((field, index) => {
      colorMap[field] = FIELD_COLORS[index % FIELD_COLORS.length];
    });
    setFieldColorMap(colorMap);
  }, [annotations]);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
  };

  // Handle text selection in PDF
  const handleTextSelection = (pageNumber: number) => {
    if (!selectedField) return;

    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    const selectedText = selection.toString().trim();
    if (!selectedText) return;

    try {
      const range = selection.getRangeAt(0);
      const rects = Array.from(range.getClientRects());
      
      if (rects.length === 0) return;

      // Get the page element to calculate relative coordinates
      const pageElement = (range.commonAncestorContainer as Element).closest('[data-page-number]');
      if (!pageElement) return;

      const pageRect = pageElement.getBoundingClientRect();
      
      // Calculate bounding box in PDF coordinates
      const firstRect = rects[0];
      const lastRect = rects[rects.length - 1];
      
      const bbox: BoundingBoxData = {
        page: pageNumber,
        x: (firstRect.left - pageRect.left) / scale,
        y: (firstRect.top - pageRect.top) / scale,
        width: (firstRect.right - firstRect.left) / scale,
        height: (lastRect.bottom - firstRect.top) / scale,
        text: selectedText,
      };

      onAnnotationCreate(selectedField, selectedText, bbox);

      // Clear selection
      selection.removeAllRanges();
    } catch (error) {
      console.error("Error creating annotation:", error);
    }
  };

  // Render annotation overlays
  const renderAnnotationOverlays = (pageNumber: number) => {
    const pageAnnotations = annotations.filter(
      a => a.annotation_type === 'bbox' && (a.annotation_data as BoundingBoxData).page === pageNumber
    );

    return pageAnnotations.map(annotation => {
      const bbox = annotation.annotation_data as BoundingBoxData;
      const color = fieldColorMap[annotation.field_name] || "rgba(128, 128, 128, 0.3)";

      return (
        <div
          key={annotation.id}
          className="absolute border-2 cursor-pointer hover:opacity-70 transition-opacity"
          style={{
            left: `${bbox.x * scale}px`,
            top: `${bbox.y * scale}px`,
            width: `${bbox.width * scale}px`,
            height: `${bbox.height * scale}px`,
            backgroundColor: color,
            borderColor: color.replace('0.3', '1'),
          }}
          onClick={() => onAnnotationDelete(annotation.id)}
          title={`${annotation.field_name}: ${annotation.value}\nClick to delete`}
        >
          <div className="absolute -top-6 left-0 bg-gray-800 text-white text-xs px-2 py-1 rounded whitespace-nowrap opacity-0 hover:opacity-100 transition-opacity">
            {annotation.field_name}
          </div>
        </div>
      );
    });
  };

  return (
    <Card className="flex flex-col h-full">
      {/* OCR Status Banner */}
      {pdfUrl.includes('ocr=true') && (
        <div className="bg-green-50 border-b border-green-200 px-4 py-2 text-sm flex items-center">
          <CheckCircle2 className="h-4 w-4 text-green-600 mr-2" />
          <span className="text-green-800 font-medium">Viewing OCR'd PDF - Text selection enabled</span>
        </div>
      )}
      <CardHeader className="flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>PDF Document</CardTitle>
            <CardDescription>
              {selectedField ? (
                <span className="text-green-600 font-medium">
                  Select text to label as "{selectedField}"
                </span>
              ) : (
                "Select a field from the sidebar to start labeling"
              )}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setScale(s => Math.max(0.5, s - 0.1))}
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span className="text-sm text-muted-foreground">{Math.round(scale * 100)}%</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setScale(s => Math.min(2.0, s + 0.1))}
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto min-h-0">
        <Document
          file={pdfUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={(error) => {
            console.error('PDF load error:', error);
            setError(error.message || 'Failed to load PDF');
          }}
          loading={
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          }
          error={
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <p className="text-red-500 font-medium mb-2">Failed to load PDF file</p>
              {error && <p className="text-sm text-muted-foreground mb-4">{error}</p>}
              <p className="text-xs text-muted-foreground break-all">
                URL: {pdfUrl}
              </p>
            </div>
          }
        >
          <div className="space-y-4">
            {Array.from(new Array(numPages), (_, index) => (
              <div 
                key={`page_${index + 1}`} 
                className="relative border rounded-lg overflow-hidden"
                style={{ userSelect: 'text', cursor: 'text' }}
              >
                <Page
                  pageNumber={index + 1}
                  scale={scale}
                  renderTextLayer={true}
                  renderAnnotationLayer={false}
                  onMouseUp={() => handleTextSelection(index + 1)}
                  className="mx-auto"
                  data-page-number={index + 1}
                />
                {renderAnnotationOverlays(index + 1)}
              </div>
            ))}
          </div>
        </Document>

        {annotations.length > 0 && (
          <div className="mt-4 space-y-2">
            <h4 className="text-sm font-medium">Annotations ({annotations.length})</h4>
            <div className="flex flex-wrap gap-2">
              {annotations.map(annotation => (
                <Badge
                  key={annotation.id}
                  variant="secondary"
                  className="cursor-pointer hover:bg-destructive hover:text-destructive-foreground"
                  onClick={() => onAnnotationDelete(annotation.id)}
                >
                  {annotation.field_name}: {String(annotation.value).substring(0, 30)}
                  {String(annotation.value).length > 30 && "..."}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
