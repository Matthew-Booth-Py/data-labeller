/**
 * ImageAnnotator - Component for annotating images with bounding boxes
 * Note: Full Annotorious integration can be added later
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { GroundTruthAnnotation } from "@/lib/api";

interface ImageAnnotatorProps {
  imageUrl: string;
  annotations: GroundTruthAnnotation[];
  selectedField: string | null;
  onAnnotationCreate: (fieldName: string, value: string, annotationData: any) => void;
  onAnnotationDelete: (annotationId: string) => void;
}

export function ImageAnnotator({
  imageUrl,
  annotations,
  selectedField,
  onAnnotationDelete,
}: ImageAnnotatorProps) {
  return (
    <Card className="flex flex-col h-full">
      <CardHeader className="flex-shrink-0">
        <CardTitle>Image Document</CardTitle>
        <CardDescription>
          {selectedField ? (
            <span className="text-green-600 font-medium">
              Image annotation coming soon - use PDF mode for now
            </span>
          ) : (
            "Select a field from the sidebar"
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto min-h-0">
        <div className="flex items-center justify-center p-4 bg-muted rounded-lg">
          <img
            src={imageUrl}
            alt="Document"
            className="max-w-full h-auto"
          />
        </div>

        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-800">
            <strong>Note:</strong> Image annotation with bounding boxes will be implemented using Annotorious library.
            For now, please convert images to PDF for annotation support.
          </p>
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
