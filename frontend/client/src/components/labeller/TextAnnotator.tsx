/**
 * TextAnnotator - Component for annotating text documents with text span highlighting
 */

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { GroundTruthAnnotation, TextSpanData } from "@/lib/api";

interface TextAnnotatorProps {
  content: string;
  annotations: GroundTruthAnnotation[];
  selectedField: string | null;
  onAnnotationCreate: (fieldName: string, value: string, annotationData: TextSpanData) => void;
  onAnnotationDelete: (annotationId: string) => void;
}

// Color palette for different fields
const FIELD_COLORS = [
  "bg-yellow-200/70",
  "bg-green-200/70",
  "bg-blue-200/70",
  "bg-purple-200/70",
  "bg-pink-200/70",
  "bg-orange-200/70",
  "bg-teal-200/70",
  "bg-red-200/70",
];

export function TextAnnotator({
  content,
  annotations,
  selectedField,
  onAnnotationCreate,
  onAnnotationDelete,
}: TextAnnotatorProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [fieldColorMap, setFieldColorMap] = useState<Record<string, string>>({});

  // Assign colors to fields
  useEffect(() => {
    const uniqueFields = Array.from(new Set(annotations.map(a => a.field_name)));
    const colorMap: Record<string, string> = {};
    uniqueFields.forEach((field, index) => {
      colorMap[field] = FIELD_COLORS[index % FIELD_COLORS.length];
    });
    setFieldColorMap(colorMap);
  }, [annotations]);

  // Handle text selection
  const handleMouseUp = () => {
    if (!selectedField) return;

    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    const selectedText = selection.toString().trim();
    if (!selectedText) return;

    const range = selection.getRangeAt(0);
    
    // Get the start and end offsets relative to the content div
    const preSelectionRange = range.cloneRange();
    preSelectionRange.selectNodeContents(contentRef.current!);
    preSelectionRange.setEnd(range.startContainer, range.startOffset);
    const start = preSelectionRange.toString().length;
    const end = start + selectedText.length;

    // Create annotation
    const annotationData: TextSpanData = {
      start,
      end,
      text: selectedText,
    };

    onAnnotationCreate(selectedField, selectedText, annotationData);

    // Clear selection
    selection.removeAllRanges();
  };

  // Render content with highlights
  const renderHighlightedContent = () => {
    if (annotations.length === 0) {
      return <div className="whitespace-pre-wrap">{content}</div>;
    }

    // Sort annotations by start position
    const sortedAnnotations = [...annotations]
      .filter(a => a.annotation_type === 'text_span')
      .sort((a, b) => {
        const aData = a.annotation_data as TextSpanData;
        const bData = b.annotation_data as TextSpanData;
        return aData.start - bData.start;
      });

    const segments: JSX.Element[] = [];
    let lastIndex = 0;

    sortedAnnotations.forEach((annotation, idx) => {
      const data = annotation.annotation_data as TextSpanData;
      const color = fieldColorMap[annotation.field_name] || "bg-gray-200/70";

      // Add text before this annotation
      if (data.start > lastIndex) {
        segments.push(
          <span key={`text-${idx}`}>
            {content.substring(lastIndex, data.start)}
          </span>
        );
      }

      // Add highlighted annotation
      segments.push(
        <mark
          key={`annotation-${annotation.id}`}
          className={`${color} cursor-pointer hover:opacity-80 transition-opacity relative group`}
          onClick={() => onAnnotationDelete(annotation.id)}
          title={`${annotation.field_name}: ${annotation.value}\nClick to delete`}
        >
          {content.substring(data.start, data.end)}
          <span className="absolute -top-6 left-0 bg-gray-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
            {annotation.field_name}
          </span>
        </mark>
      );

      lastIndex = data.end;
    });

    // Add remaining text
    if (lastIndex < content.length) {
      segments.push(
        <span key="text-end">
          {content.substring(lastIndex)}
        </span>
      );
    }

    return <div className="whitespace-pre-wrap">{segments}</div>;
  };

  return (
    <Card className="flex flex-col h-full">
      <CardHeader className="flex-shrink-0">
        <CardTitle>Text Document</CardTitle>
        <CardDescription>
          {selectedField ? (
            <span className="text-green-600 font-medium">
              Select text to label as "{selectedField}"
            </span>
          ) : (
            "Select a field from the sidebar to start labeling"
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto min-h-0">
        <div
          ref={contentRef}
          className="p-4 bg-white border rounded-lg text-sm leading-relaxed select-text"
          onMouseUp={handleMouseUp}
        >
          {renderHighlightedContent()}
        </div>

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
