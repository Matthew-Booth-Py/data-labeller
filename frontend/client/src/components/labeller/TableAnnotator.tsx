/**
 * TableAnnotator - Component for annotating array fields with multi-field rows
 * Simplified version - full implementation can be added later
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { GroundTruthAnnotation } from "@/lib/api";
import { formatAnnotationValue } from "@/lib/utils";

interface TableAnnotatorProps {
  annotations: GroundTruthAnnotation[];
  selectedField: string | null;
  onAnnotationDelete: (annotationId: string) => void;
}

export function TableAnnotator({
  annotations,
  selectedField,
  onAnnotationDelete,
}: TableAnnotatorProps) {
  return (
    <Card className="flex flex-col h-full">
      <CardHeader className="flex-shrink-0">
        <CardTitle>Table/Array Field Annotation</CardTitle>
        <CardDescription>
          {selectedField ? (
            <span className="text-green-600 font-medium">
              Annotating array field: "{selectedField}"
            </span>
          ) : (
            "Select an array field from the sidebar"
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto min-h-0">
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-800">
            <strong>Table Annotation:</strong> This feature allows you to annotate array fields like line items.
            For each row, you can annotate multiple sub-fields (e.g., item name, quantity, price).
          </p>
          <p className="text-sm text-blue-800 mt-2">
            Full table annotation UI will be implemented in a future update.
            For now, use regular field annotation for individual values.
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
                  {annotation.field_name}: {formatAnnotationValue(annotation.value, 30)}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
