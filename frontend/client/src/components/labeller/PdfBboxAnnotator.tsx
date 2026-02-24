/**
 * PdfBboxAnnotator - Component for annotating PDFs with drawable bounding boxes
 * Keeps bbox annotations as user-provided coordinates.
 */

import { useState, useEffect, useRef, useLayoutEffect } from "react";
import { flushSync } from "react-dom";
import { Document, Page, pdfjs } from "react-pdf";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, ZoomIn, ZoomOut, Square } from "lucide-react";
import type { GroundTruthAnnotation, BoundingBoxData, AnnotationSuggestion } from "@/lib/api";
import { cn, formatAnnotationValue } from "@/lib/utils";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Set up PDF.js worker using cdnjs (more reliable than unpkg)
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.mjs`;

interface PdfBboxAnnotatorProps {
  documentId: string;
  pdfUrl: string;
  annotations: GroundTruthAnnotation[];
  suggestions?: AnnotationSuggestion[];
  selectedField: string | null;
  editingAnnotationId?: string | null;
  onAnnotationCreate: (fieldName: string, value: string, annotationData: BoundingBoxData) => void;
  onAnnotationDelete: (annotationId: string) => void;
  onAnnotationUpdate?: (annotationId: string, bbox: { x: number; y: number; width: number; height: number }) => void;
  onSuggestionApprove?: (suggestion: AnnotationSuggestion) => void;
  onSuggestionReject?: (suggestionId: string) => void;
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
  suggestions = [],
  selectedField,
  editingAnnotationId = null,
  onAnnotationCreate,
  onAnnotationDelete,
  onAnnotationUpdate,
  onSuggestionApprove,
  onSuggestionReject,
}: PdfBboxAnnotatorProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState(1.0);
  const [fieldColorMap, setFieldColorMap] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawingBox, setDrawingBox] = useState<DrawingBox | null>(null);
  const [resizingAnnotation, setResizingAnnotation] = useState<{ id: string; handle: string } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const canvasRefs = useRef<Map<number, HTMLCanvasElement>>(new Map());
  const containerRef = useRef<HTMLDivElement>(null);

  // Force browser repaint - workaround for rendering stall issue
  const forceRepaint = () => {
    if (containerRef.current) {
      // Force a reflow by reading offsetHeight
      void containerRef.current.offsetHeight;
      // Also try forcing a style recalculation
      containerRef.current.style.transform = 'translateZ(0)';
      requestAnimationFrame(() => {
        if (containerRef.current) {
          containerRef.current.style.transform = '';
        }
      });
    }
  };

  // Reset loading state when document changes
  useEffect(() => {
    setIsLoading(true);
    setNumPages(0);
    setError(null);
  }, [pdfUrl]);

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
    console.log('[PdfBboxAnnotator] PDF loaded successfully, numPages:', numPages);
    // Use flushSync to force synchronous state update and DOM commit
    flushSync(() => {
      setNumPages(numPages);
      setIsLoading(false);
    });
    // Force browser to repaint after state update
    forceRepaint();
    requestAnimationFrame(() => {
      forceRepaint();
    });
  };

  // Handle mouse down - start drawing or resizing
  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>, pageNumber: number) => {
    // Don't start drawing if clicking on an annotation
    if ((e.target as HTMLElement).closest('[data-annotation-id]')) {
      return;
    }
    
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
        text: "",
      };

      // Create annotation from user-drawn bbox.
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
      const isEditing = editingAnnotationId === annotation.id;

      return (
        <div
          key={annotation.id}
          data-annotation-id={annotation.id}
          className={cn(
            "absolute border-2 group transition-opacity",
            isEditing ? "cursor-move ring-2 ring-blue-500" : "cursor-pointer hover:opacity-70"
          )}
          style={{
            left: `${bbox.x * scale}px`,
            top: `${bbox.y * scale}px`,
            width: `${bbox.width * scale}px`,
            height: `${bbox.height * scale}px`,
            backgroundColor: color,
            borderColor: isEditing ? '#3b82f6' : color.replace('0.3', '1'),
          }}
          onClick={(e) => {
            e.stopPropagation();
            if (!isEditing) {
              onAnnotationDelete(annotation.id);
            }
          }}
          onMouseDown={(e) => {
            if (isEditing) {
              e.stopPropagation();
              const rect = e.currentTarget.getBoundingClientRect();
              const startX = e.clientX;
              const startY = e.clientY;
              const startLeft = bbox.x * scale;
              const startTop = bbox.y * scale;

              const handleMouseMove = (moveEvent: MouseEvent) => {
                const deltaX = moveEvent.clientX - startX;
                const deltaY = moveEvent.clientY - startY;
                
                const newX = (startLeft + deltaX) / scale;
                const newY = (startTop + deltaY) / scale;
                
                if (onAnnotationUpdate) {
                  onAnnotationUpdate(annotation.id, {
                    x: Math.max(0, newX),
                    y: Math.max(0, newY),
                    width: bbox.width,
                    height: bbox.height,
                  });
                }
              };

              const handleMouseUp = () => {
                document.removeEventListener('mousemove', handleMouseMove);
                document.removeEventListener('mouseup', handleMouseUp);
              };

              document.addEventListener('mousemove', handleMouseMove);
              document.addEventListener('mouseup', handleMouseUp);
            }
          }}
          title={isEditing ? "Drag to move, use handles to resize" : `${annotation.field_name}: ${annotation.value}\nClick to delete`}
        >
          <div className={cn(
            "absolute -top-6 left-0 bg-gray-800 text-white text-xs px-2 py-1 rounded whitespace-nowrap transition-opacity",
            isEditing ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          )}>
            {annotation.field_name}
          </div>
          
          {/* Resize handles - only show when editing */}
          {isEditing && (
            <>
              {/* Corner handles */}
              <div
                className="absolute w-3 h-3 bg-blue-500 border border-white rounded-full cursor-nwse-resize"
                style={{ left: -6, top: -6 }}
                onMouseDown={(e) => handleResizeStart(e, annotation.id, 'nw', bbox)}
              />
              <div
                className="absolute w-3 h-3 bg-blue-500 border border-white rounded-full cursor-nesw-resize"
                style={{ right: -6, top: -6 }}
                onMouseDown={(e) => handleResizeStart(e, annotation.id, 'ne', bbox)}
              />
              <div
                className="absolute w-3 h-3 bg-blue-500 border border-white rounded-full cursor-nwse-resize"
                style={{ right: -6, bottom: -6 }}
                onMouseDown={(e) => handleResizeStart(e, annotation.id, 'se', bbox)}
              />
              <div
                className="absolute w-3 h-3 bg-blue-500 border border-white rounded-full cursor-nesw-resize"
                style={{ left: -6, bottom: -6 }}
                onMouseDown={(e) => handleResizeStart(e, annotation.id, 'sw', bbox)}
              />
              
              {/* Edge handles */}
              <div
                className="absolute w-3 h-3 bg-blue-500 border border-white rounded-full cursor-ns-resize"
                style={{ left: '50%', top: -6, transform: 'translateX(-50%)' }}
                onMouseDown={(e) => handleResizeStart(e, annotation.id, 'n', bbox)}
              />
              <div
                className="absolute w-3 h-3 bg-blue-500 border border-white rounded-full cursor-ew-resize"
                style={{ right: -6, top: '50%', transform: 'translateY(-50%)' }}
                onMouseDown={(e) => handleResizeStart(e, annotation.id, 'e', bbox)}
              />
              <div
                className="absolute w-3 h-3 bg-blue-500 border border-white rounded-full cursor-ns-resize"
                style={{ left: '50%', bottom: -6, transform: 'translateX(-50%)' }}
                onMouseDown={(e) => handleResizeStart(e, annotation.id, 's', bbox)}
              />
              <div
                className="absolute w-3 h-3 bg-blue-500 border border-white rounded-full cursor-ew-resize"
                style={{ left: -6, top: '50%', transform: 'translateY(-50%)' }}
                onMouseDown={(e) => handleResizeStart(e, annotation.id, 'w', bbox)}
              />
            </>
          )}
        </div>
      );
    });
  };

  const handleResizeStart = (
    e: React.MouseEvent,
    annotationId: string,
    handle: string,
    bbox: BoundingBoxData
  ) => {
    e.stopPropagation();
    const startX = e.clientX;
    const startY = e.clientY;
    const startBbox = { ...bbox };

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaX = (moveEvent.clientX - startX) / scale;
      const deltaY = (moveEvent.clientY - startY) / scale;
      
      let newBbox = { ...startBbox };

      // Handle different resize directions
      if (handle.includes('n')) {
        newBbox.y = startBbox.y + deltaY;
        newBbox.height = startBbox.height - deltaY;
      }
      if (handle.includes('s')) {
        newBbox.height = startBbox.height + deltaY;
      }
      if (handle.includes('w')) {
        newBbox.x = startBbox.x + deltaX;
        newBbox.width = startBbox.width - deltaX;
      }
      if (handle.includes('e')) {
        newBbox.width = startBbox.width + deltaX;
      }

      // Ensure minimum size
      if (newBbox.width < 10) newBbox.width = 10;
      if (newBbox.height < 10) newBbox.height = 10;

      if (onAnnotationUpdate) {
        onAnnotationUpdate(annotationId, {
          x: Math.max(0, newBbox.x),
          y: Math.max(0, newBbox.y),
          width: newBbox.width,
          height: newBbox.height,
        });
      }
    };

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  // Render AI suggestion overlays (dashed border, different styling)
  const renderSuggestionOverlays = (pageNumber: number) => {
    const pageSuggestions = suggestions.filter(
      s => s.annotation_type === 'bbox' && (s.annotation_data as BoundingBoxData).page === pageNumber
    );

    return pageSuggestions.map(suggestion => {
      const bbox = suggestion.annotation_data as BoundingBoxData;

      return (
        <div
          key={suggestion.id}
          className="absolute cursor-pointer hover:opacity-90 transition-opacity group"
          style={{
            left: `${bbox.x * scale}px`,
            top: `${bbox.y * scale}px`,
            width: `${bbox.width * scale}px`,
            height: `${bbox.height * scale}px`,
            backgroundColor: "rgba(255, 165, 0, 0.15)",
            border: "2px dashed orange",
          }}
          title={`AI Suggestion: ${suggestion.field_name}: ${suggestion.value}`}
        >
          {/* Suggestion label */}
          <div className="absolute -top-7 left-0 bg-orange-500 text-white text-xs px-2 py-1 rounded whitespace-nowrap flex items-center gap-1">
            <span>AI: {suggestion.field_name}</span>
          </div>
          {/* Action buttons on hover */}
          <div className="absolute -bottom-8 left-0 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
            {onSuggestionApprove && (
              <button
                className="bg-green-500 text-white text-xs px-2 py-1 rounded hover:bg-green-600"
                onClick={(e) => {
                  e.stopPropagation();
                  onSuggestionApprove(suggestion);
                }}
              >
                Accept
              </button>
            )}
            {onSuggestionReject && (
              <button
                className="bg-red-500 text-white text-xs px-2 py-1 rounded hover:bg-red-600"
                onClick={(e) => {
                  e.stopPropagation();
                  onSuggestionReject(suggestion.id);
                }}
              >
                Reject
              </button>
            )}
          </div>
        </div>
      );
    });
  };

  return (
    <div ref={containerRef} style={{ willChange: 'transform' }}>
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
          key={pdfUrl}
          file={pdfUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={(error) => {
            console.error('PDF load error:', error);
            setError(error.message || 'Failed to load PDF');
            setIsLoading(false);
          }}
          loading={
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Loading PDF...</p>
              </div>
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
                {renderSuggestionOverlays(index + 1)}
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
                  {annotation.field_name}: {formatAnnotationValue(annotation.value, 30)}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
    </div>
  );
}
