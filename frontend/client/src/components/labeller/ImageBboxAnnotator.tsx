/**
 * ImageBboxAnnotator - Component for annotating images with bounding boxes
 * Supports drawing, moving, and resizing boxes
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { ZoomIn, ZoomOut, Square } from "lucide-react";
import type { GroundTruthAnnotation, BoundingBoxData, AnnotationSuggestion } from "@/lib/api";
import type { EntityType } from "./TextSpanAnnotator";

interface ImageBboxAnnotatorProps {
  documentId: string;
  imageUrl: string;
  annotations: GroundTruthAnnotation[];
  entityTypes: EntityType[];
  activeEntityTypeId: string | null;
  onAnnotationCreate: (fieldName: string, value: string, data: BoundingBoxData) => void;
  onAnnotationDelete: (annotationId: string) => void;
  onActiveEntityChange: (id: string | null) => void;
  suggestions?: AnnotationSuggestion[];
  onSuggestionApprove?: (suggestion: AnnotationSuggestion) => void;
  onSuggestionReject?: (id: string) => void;
}

interface DrawingBox {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
}

export function ImageBboxAnnotator({
  documentId,
  imageUrl,
  annotations,
  entityTypes,
  activeEntityTypeId,
  onAnnotationCreate,
  onAnnotationDelete,
  onActiveEntityChange,
  suggestions = [],
  onSuggestionApprove,
  onSuggestionReject,
}: ImageBboxAnnotatorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [scale, setScale] = useState(1.0);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawingBox, setDrawingBox] = useState<DrawingBox | null>(null);
  const [editingAnnotationId, setEditingAnnotationId] = useState<string | null>(null);

  // Get active entity type
  const activeEntityType = entityTypes.find(et => et.id === activeEntityTypeId);

  // Handle image load to get dimensions
  const handleImageLoad = useCallback(() => {
    if (imageRef.current) {
      setImageSize({
        width: imageRef.current.naturalWidth,
        height: imageRef.current.naturalHeight,
      });
    }
  }, []);

  // Get color for annotation
  const getAnnotationColor = useCallback((fieldName: string): string => {
    const et = entityTypes.find(e => e.name === fieldName);
    return et?.color || '#8b949e';
  }, [entityTypes]);

  // Handle mouse down - start drawing
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    // Don't start drawing if clicking on an annotation
    if ((e.target as HTMLElement).closest('[data-annotation-id]')) {
      return;
    }
    
    if (!activeEntityTypeId || !imageRef.current) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setIsDrawing(true);
    setDrawingBox({
      startX: x,
      startY: y,
      currentX: x,
      currentY: y,
    });
  }, [activeEntityTypeId]);

  // Handle mouse move - update drawing
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDrawing || !drawingBox) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setDrawingBox({
      ...drawingBox,
      currentX: x,
      currentY: y,
    });
  }, [isDrawing, drawingBox]);

  // Handle mouse up - finish drawing and create annotation
  const handleMouseUp = useCallback(() => {
    if (!isDrawing || !drawingBox || !activeEntityType || !imageSize.width) return;

    const { startX, startY, currentX, currentY } = drawingBox;

    // Calculate normalized bbox (relative to image size)
    const x = Math.min(startX, currentX) / scale;
    const y = Math.min(startY, currentY) / scale;
    const width = Math.abs(currentX - startX) / scale;
    const height = Math.abs(currentY - startY) / scale;

    // Only create annotation if box has meaningful size
    if (width > 10 && height > 10) {
      const bbox: BoundingBoxData = {
        page: 1, // Images don't have pages
        x,
        y,
        width,
        height,
        text: "", // No text extraction for images
      };

      onAnnotationCreate(activeEntityType.name, "", bbox);
    }

    setIsDrawing(false);
    setDrawingBox(null);
  }, [isDrawing, drawingBox, activeEntityType, imageSize, scale, onAnnotationCreate]);

  // Handle mouse leave
  const handleMouseLeave = useCallback(() => {
    if (isDrawing) {
      setIsDrawing(false);
      setDrawingBox(null);
    }
  }, [isDrawing]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      // Number keys 1-9 to select entity type
      if (e.key >= '1' && e.key <= '9' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const idx = parseInt(e.key) - 1;
        if (idx < entityTypes.length) {
          const entityType = entityTypes[idx];
          onActiveEntityChange(activeEntityTypeId === entityType.id ? null : entityType.id);
          e.preventDefault();
        }
      }

      // Escape to deselect
      if (e.key === 'Escape') {
        onActiveEntityChange(null);
        setEditingAnnotationId(null);
      }

      // Delete/Backspace to remove last annotation
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const bboxAnnotations = annotations.filter(a => a.annotation_type === 'bbox');
        if (bboxAnnotations.length > 0) {
          const lastAnnotation = bboxAnnotations[bboxAnnotations.length - 1];
          onAnnotationDelete(lastAnnotation.id);
          e.preventDefault();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [entityTypes, activeEntityTypeId, annotations, onActiveEntityChange, onAnnotationDelete]);

  // Render current drawing box
  const renderDrawingBox = () => {
    if (!isDrawing || !drawingBox) return null;

    const { startX, startY, currentX, currentY } = drawingBox;
    const x = Math.min(startX, currentX);
    const y = Math.min(startY, currentY);
    const width = Math.abs(currentX - startX);
    const height = Math.abs(currentY - startY);

    const color = activeEntityType?.color || '#8b949e';

    return (
      <div
        className="absolute border-2 pointer-events-none"
        style={{
          left: `${x}px`,
          top: `${y}px`,
          width: `${width}px`,
          height: `${height}px`,
          backgroundColor: `${color}30`,
          borderColor: color,
        }}
      />
    );
  };

  // Render suggestion overlays
  const renderSuggestionOverlays = () => {
    const bboxSuggestions = suggestions.filter(s => s.annotation_type === 'bbox');

    return bboxSuggestions.map(suggestion => {
      const bbox = suggestion.annotation_data as BoundingBoxData;
      const label = suggestion.field_name.split('.').pop() || suggestion.field_name;

      return (
        <div
          key={suggestion.id}
          className="absolute group"
          style={{
            left: `${bbox.x * scale}px`,
            top: `${bbox.y * scale}px`,
            width: `${bbox.width * scale}px`,
            height: `${bbox.height * scale}px`,
            backgroundColor: 'rgba(240, 136, 62, 0.15)',
            border: '2px dashed #f0883e',
            borderRadius: '2px',
          }}
          title={`AI suggestion: ${suggestion.field_name}\n"${suggestion.value}"`}
        >
          {/* Label with accept/reject */}
          <div style={{
            position: 'absolute',
            top: '-20px',
            left: 0,
            background: '#f0883e',
            color: '#0d1117',
            fontSize: '9px',
            fontWeight: 700,
            padding: '1px 4px',
            borderRadius: '3px',
            whiteSpace: 'nowrap',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            zIndex: 20,
          }}>
            ✦ {label}
            <button
              onClick={(e) => { e.stopPropagation(); onSuggestionApprove?.(suggestion); }}
              style={{ background: '#238636', border: 'none', color: '#fff', borderRadius: '2px', padding: '0 3px', cursor: 'pointer', fontSize: '9px' }}
              title="Approve"
            >✓</button>
            <button
              onClick={(e) => { e.stopPropagation(); onSuggestionReject?.(suggestion.id); }}
              style={{ background: '#f85149', border: 'none', color: '#fff', borderRadius: '2px', padding: '0 3px', cursor: 'pointer', fontSize: '9px' }}
              title="Reject"
            >✕</button>
          </div>
        </div>
      );
    });
  };

  // Render annotation overlays
  const renderAnnotationOverlays = () => {
    const bboxAnnotations = annotations.filter(a => a.annotation_type === 'bbox');

    return bboxAnnotations.map(annotation => {
      const bbox = annotation.annotation_data as BoundingBoxData;
      const color = getAnnotationColor(annotation.field_name);
      const isEditing = editingAnnotationId === annotation.id;

      return (
        <div
          key={annotation.id}
          data-annotation-id={annotation.id}
          className="absolute border-2 group transition-opacity cursor-pointer hover:opacity-70"
          style={{
            left: `${bbox.x * scale}px`,
            top: `${bbox.y * scale}px`,
            width: `${bbox.width * scale}px`,
            height: `${bbox.height * scale}px`,
            backgroundColor: `${color}30`,
            borderColor: isEditing ? '#58a6ff' : color,
            boxShadow: isEditing ? '0 0 0 2px #58a6ff' : undefined,
          }}
          onClick={(e) => {
            e.stopPropagation();
            if (!isEditing) {
              onAnnotationDelete(annotation.id);
            }
          }}
          title={`${annotation.field_name}\nClick to delete`}
        >
          {/* Label */}
          <div
            className="absolute -top-6 left-0 text-white text-xs px-2 py-1 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity"
            style={{ backgroundColor: color }}
          >
            {annotation.field_name}
          </div>
        </div>
      );
    });
  };

  return (
    <div className="flex flex-col h-full" style={{ background: '#0d1117' }}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-5 py-2 border-b" style={{ borderColor: '#30363d', background: '#161b22' }}>
        <div className="flex items-center gap-2 text-sm" style={{ color: '#8b949e' }}>
          {activeEntityType ? (
            <>
              <Square size={16} style={{ color: activeEntityType.color }} />
              <span>Draw a box to label as <strong style={{ color: '#c9d1d9' }}>{activeEntityType.name}</strong></span>
            </>
          ) : (
            <span>Select an entity type from the sidebar to start labeling</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            className="dl-btn dl-btn-sm"
            onClick={() => setScale(s => Math.max(0.5, s - 0.1))}
          >
            <ZoomOut size={14} />
          </button>
          <span className="text-sm" style={{ color: '#8b949e' }}>{Math.round(scale * 100)}%</span>
          <button
            className="dl-btn dl-btn-sm"
            onClick={() => setScale(s => Math.min(2.0, s + 0.1))}
          >
            <ZoomIn size={14} />
          </button>
        </div>
      </div>

      {/* Image container */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-6"
        style={{ background: '#0d1117' }}
      >
        <div
          className="relative inline-block"
          style={{
            cursor: activeEntityTypeId ? 'crosshair' : 'default',
            userSelect: 'none',
          }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseLeave}
        >
          <img
            ref={imageRef}
            src={imageUrl}
            alt="Document"
            onLoad={handleImageLoad}
            style={{
              display: 'block',
              width: imageSize.width ? `${imageSize.width * scale}px` : 'auto',
              height: imageSize.height ? `${imageSize.height * scale}px` : 'auto',
              maxWidth: 'none',
            }}
            draggable={false}
          />
          
          {/* Annotation overlays */}
          {renderAnnotationOverlays()}

          {/* Suggestion overlays */}
          {renderSuggestionOverlays()}
          
          {/* Current drawing box */}
          {renderDrawingBox()}
        </div>
      </div>

      {/* Annotations summary */}
      {annotations.filter(a => a.annotation_type === 'bbox').length > 0 && (
        <div className="px-5 py-3 border-t" style={{ borderColor: '#30363d', background: '#161b22' }}>
          <div className="flex flex-wrap gap-2">
            {annotations.filter(a => a.annotation_type === 'bbox').map(annotation => {
              const color = getAnnotationColor(annotation.field_name);
              return (
                <div
                  key={annotation.id}
                  className="flex items-center gap-2 px-2 py-1 rounded text-xs cursor-pointer hover:opacity-70"
                  style={{ background: `${color}20`, border: `1px solid ${color}40` }}
                  onClick={() => onAnnotationDelete(annotation.id)}
                  title="Click to delete"
                >
                  <div className="w-2 h-2 rounded-full" style={{ background: color }} />
                  <span style={{ color }}>{annotation.field_name}</span>
                  <span style={{ color: '#8b949e' }}>×</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
