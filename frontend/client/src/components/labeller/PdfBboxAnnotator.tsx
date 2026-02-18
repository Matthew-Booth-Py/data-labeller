/**
 * PdfBboxAnnotator - Component for annotating PDFs with drawable bounding boxes
 * Uses Azure Document Intelligence to extract text from drawn boxes
 */

import { useState, useEffect, useRef } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, ZoomIn, ZoomOut, Square } from "lucide-react";
import type { GroundTruthAnnotation, BoundingBoxData } from "@/lib/api";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfBboxAnnotatorProps {
  documentId: string;
  pdfUrl: string;
  annotations: GroundTruthAnnotation[];
  selectedField: string | null;
  onAnnotationCreate: (fieldName: string, value: string, annotationData: BoundingBoxData) => void;
  onAnnotationDelete: (annotationId: string) => void;
}

interface DrawingBox {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  pageNumber: number;
}

const FIELD_COLORS = [
  "rgba(255, 235, 59, 0.3)",
  "rgba(76, 175, 80, 0.3)",
  "rgba(33, 150, 243, 0.3)",
  "rgba(156, 39, 176, 0.3)",
  "rgba(233, 30, 99, 0.3)",
  "rgba(255, 152, 0, 0.3)",
  "rgba(0, 188, 212, 0.3)",
  "rgba(244, 67, 54, 0.3)",
];

export function PdfBboxAnnotator({
  documentId,
  pdfUrl,
  annotations,
  selectedField,
  onAnnotationCreate,
  onAnnotationDelete,
}: PdfBboxAnnotatorProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState(1.0);
  const [fieldColorMap, setFieldColorMap] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawingBox, setDrawingBox] = useState<DrawingBox | null>(null);
  const canvasRefs = useRef<Map<number, HTMLCanvasElement>>(new Map());

  // Assign colors to fields
  useEffect(() => {
    const uniqueFields = Array.from(new Set(annotations.map(a => a.field_name)));
    const colorMap: Record<string, string> = {};
    uniqueFields.forEach((field, index) => {
      colorMap[field] = FIELD_COLORS[index % FIELD_COLORS.length];
    });
    if (selectedField && !colorMap[selectedField]) {
      colorMap[selectedField] = FIELD_COLORS[uniqueFields.length % FIELD_COLORS.length];
    }
    setFieldColorMap(colorMap);
  }, [annotations, selectedField]);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
  };

  // Handle mouse down - start drawing
  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>, pageNumber: number) => {
    if (!selectedField) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setIsDrawing(true);
    setDrawingBox({
      startX: x,
      startY: y,
      currentX: x,
      currentY: y,
      pageNumber,
    });
  };

  // Handle mouse move - update drawing
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDrawing || !drawingBox) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setDrawingBox({
      ...drawingBox,
      currentX: x,
      currentY: y,
    });
  };

  // Handle mouse up - finish drawing and create annotation
  const handleMouseUp = async () => {
    if (!isDrawing || !drawingBox || !selectedField) return;

    const { startX, startY, currentX, currentY, pageNumber } = drawingBox;

    // Calculate normalized bbox
    const x = Math.min(startX, currentX) / scale;
    const y = Math.min(startY, currentY) / scale;
    const width = Math.abs(currentX - startX) / scale;
    const height = Math.abs(currentY - startY) / scale;

    // Only create annotation if box has meaningful size
    if (width > 10 && height > 10) {
      const bbox: BoundingBoxData = {
        page: pageNumber,
        x,
        y,
        width,
        height,
        text: "", // Will be filled by backend via Azure DI
      };

      // Call backend to extract text and create annotation
      onAnnotationCreate(selectedField, "", bbox);
    }

    setIsDrawing(false);
    setDrawingBox(null);
  };

  // Render current drawing box
  const renderDrawingBox = (pageNumber: number) => {
    if (!isDrawing || !drawingBox || drawingBox.pageNumber !== pageNumber) return null;

    const { startX, startY, currentX, currentY } = drawingBox;
    const x = Math.min(startX, currentX);
    const y = Math.min(startY, currentY);
    const width = Math.abs(currentX - startX);
    const height = Math.abs(currentY - startY);

    const color = selectedField ? fieldColorMap[selectedField] || "rgba(128, 128, 128, 0.3)" : "rgba(128, 128, 128, 0.3)";

    return (
      <div
        className="absolute border-2 pointer-events-none"
        style={{
          left: `${x}px`,
          top: `${y}px`,
          width: `${width}px`,
          height: `${height}px`,
          backgroundColor: color,
          borderColor: color.replace('0.3', '1'),
        }}
      />
    );
  };

  // Render saved annotation overlays
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
      <CardHeader className="flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>PDF Document</CardTitle>
            <CardDescription>
              {selectedField ? (
                <span className="text-green-600 font-medium flex items-center gap-2">
                  <Square className="h-4 w-4" />
                  Draw a box to label as "{selectedField}"
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
                style={{ 
                  cursor: selectedField ? 'crosshair' : 'default',
                  userSelect: 'none'
                }}
                onMouseDown={(e) => handleMouseDown(e, index + 1)}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={() => {
                  if (isDrawing) {
                    setIsDrawing(false);
                    setDrawingBox(null);
                  }
                }}
              >
                <Page
                  pageNumber={index + 1}
                  scale={scale}
                  renderTextLayer={false}
                  renderAnnotationLayer={false}
                  className="mx-auto"
                />
                {renderAnnotationOverlays(index + 1)}
                {renderDrawingBox(index + 1)}
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
