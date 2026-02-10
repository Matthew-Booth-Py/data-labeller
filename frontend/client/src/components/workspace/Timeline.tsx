import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Calendar, FileText, ZoomIn, ZoomOut, RefreshCw } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { api, TimelineEntry, TimelineDocument } from "@/lib/api";
import { format, parseISO } from "date-fns";

interface TimelineProps {
  onDocumentClick?: (documentId: string) => void;
  highlightedDocuments?: string[];
}

export function Timeline({ onDocumentClick, highlightedDocuments = [] }: TimelineProps) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<{ start?: string; end?: string }>({});

  // Fetch timeline data
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["timeline", dateRange.start, dateRange.end],
    queryFn: () => api.getGraphTimeline(dateRange.start, dateRange.end),
    staleTime: 30000, // 30 seconds
  });

  // Transform data for the chart
  const chartData = useMemo(() => {
    if (!data?.timeline) return [];
    
    return data.timeline.map((entry) => ({
      date: entry.date,
      count: entry.document_count,
      documents: entry.documents,
      label: format(parseISO(entry.date), "MMM d, yyyy"),
    }));
  }, [data]);

  // Get documents for selected date
  const selectedDocuments = useMemo(() => {
    if (!selectedDate || !data?.timeline) return [];
    const entry = data.timeline.find((e) => e.date === selectedDate);
    return entry?.documents || [];
  }, [selectedDate, data]);

  // Check if a document is highlighted
  const isHighlighted = (docId: string) => highlightedDocuments.includes(docId);

  const handleBarClick = (data: any) => {
    if (data?.date) {
      setSelectedDate(data.date === selectedDate ? null : data.date);
    }
  };

  if (error) {
    return (
      <Card className="h-full">
        <CardContent className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <p className="text-destructive">Failed to load timeline data</p>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Calendar className="h-5 w-5 text-primary" />
            Document Timeline
          </h2>
          <p className="text-sm text-muted-foreground">
            {data?.total_documents || 0} documents from{" "}
            {data?.date_range.earliest
              ? format(parseISO(data.date_range.earliest), "MMM yyyy")
              : "—"}{" "}
            to{" "}
            {data?.date_range.latest
              ? format(parseISO(data.date_range.latest), "MMM yyyy")
              : "—"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Chart */}
      <Card className="flex-1 min-h-[300px]">
        <CardContent className="h-full p-4">
          {isLoading ? (
            <div className="h-full flex items-center justify-center">
              <div className="space-y-4 w-full">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-[200px] w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            </div>
          ) : chartData.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center space-y-2">
                <FileText className="h-12 w-12 text-muted-foreground mx-auto" />
                <p className="text-muted-foreground">No documents with dates found</p>
                <p className="text-sm text-muted-foreground">
                  Ingest documents to see them on the timeline
                </p>
              </div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                margin={{ top: 10, right: 30, left: 0, bottom: 30 }}
                onClick={(e) => e?.activePayload?.[0] && handleBarClick(e.activePayload[0].payload)}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted))" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10 }}
                  angle={-45}
                  textAnchor="end"
                  height={60}
                  stroke="hsl(var(--muted-foreground))"
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 10 }}
                  stroke="hsl(var(--muted-foreground))"
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.[0]) return null;
                    const data = payload[0].payload;
                    return (
                      <div className="bg-background border rounded-lg shadow-lg p-3">
                        <p className="font-medium">{data.label}</p>
                        <p className="text-sm text-muted-foreground">
                          {data.count} document{data.count !== 1 ? "s" : ""}
                        </p>
                      </div>
                    );
                  }}
                />
                <Bar
                  dataKey="count"
                  radius={[4, 4, 0, 0]}
                  cursor="pointer"
                >
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        entry.date === selectedDate
                          ? "hsl(var(--primary))"
                          : "hsl(var(--primary) / 0.6)"
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Document List for Selected Date */}
      {selectedDate && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm flex items-center justify-between">
              <span>
                Documents from {format(parseISO(selectedDate), "MMMM d, yyyy")}
              </span>
              <Badge variant="secondary">{selectedDocuments.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="py-2">
            <div className="space-y-2 max-h-[200px] overflow-auto">
              {selectedDocuments.map((doc) => (
                <div
                  key={doc.id}
                  className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
                    isHighlighted(doc.id)
                      ? "bg-primary/10 border border-primary/20"
                      : "hover:bg-muted"
                  }`}
                  onClick={() => onDocumentClick?.(doc.id)}
                >
                  <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{doc.filename}</p>
                    {doc.excerpt && (
                      <p className="text-xs text-muted-foreground truncate">
                        {doc.excerpt}
                      </p>
                    )}
                  </div>
                  <Badge variant="outline" className="text-[10px] shrink-0">
                    {doc.file_type}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default Timeline;
