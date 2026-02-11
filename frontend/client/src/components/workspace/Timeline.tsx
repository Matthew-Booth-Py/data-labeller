import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Calendar, FileText, RefreshCw } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import { format, parseISO } from "date-fns";

interface TimelineProps {
  onDocumentClick?: (documentId: string) => void;
  highlightedDocuments?: string[];
}

export function Timeline({ onDocumentClick, highlightedDocuments = [] }: TimelineProps) {
  // Fetch timeline data
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["timeline"],
    queryFn: () => api.getGraphTimeline(),
    staleTime: 30000, // 30 seconds
  });

  // Transform data for the chart
  const chartData = useMemo(() => {
    if (!data?.timeline) return [];
    
    return [...data.timeline]
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((entry) => ({
      date: entry.date,
      count: entry.document_count,
      label: format(parseISO(entry.date), "MMM d, yyyy"),
    }));
  }, [data]);

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
            Upload Histogram
          </h2>
          <p className="text-sm text-muted-foreground">
            {data?.total_documents || 0} documents uploaded from{" "}
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
                  fill="hsl(var(--primary) / 0.7)"
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default Timeline;
