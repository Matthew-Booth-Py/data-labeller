import { useState, useMemo, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Network,
  User,
  Building2,
  MapPin,
  CalendarDays,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Maximize2,
  FileText,
} from "lucide-react";
import { api, GraphNode, GraphEdge, EntityType, Entity } from "@/lib/api";

interface KnowledgeGraphProps {
  onDocumentClick?: (documentId: string) => void;
  onEntityClick?: (entityId: string) => void;
}

// Entity type colors and icons
const entityConfig: Record<
  EntityType,
  { color: string; bgColor: string; icon: React.ElementType }
> = {
  Person: { color: "text-blue-500", bgColor: "bg-blue-500", icon: User },
  Organization: { color: "text-purple-500", bgColor: "bg-purple-500", icon: Building2 },
  Location: { color: "text-green-500", bgColor: "bg-green-500", icon: MapPin },
  Event: { color: "text-orange-500", bgColor: "bg-orange-500", icon: CalendarDays },
};

export function KnowledgeGraph({ onDocumentClick, onEntityClick }: KnowledgeGraphProps) {
  const [selectedEntityType, setSelectedEntityType] = useState<EntityType | "all">("all");
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [maxNodes, setMaxNodes] = useState(50);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 400 });

  // Fetch graph data
  const { data: graphData, isLoading, error, refetch } = useQuery({
    queryKey: ["graph", selectedEntityType, maxNodes],
    queryFn: () =>
      api.getGraph(
        selectedEntityType === "all" ? undefined : [selectedEntityType as EntityType],
        maxNodes
      ),
    staleTime: 30000,
  });

  // Fetch entity details when selected
  const { data: entityDetails } = useQuery({
    queryKey: ["entity", selectedNode],
    queryFn: () => (selectedNode ? api.getEntity(selectedNode) : null),
    enabled: !!selectedNode,
  });

  // Calculate node positions using force-directed layout simulation
  const nodePositions = useMemo(() => {
    if (!graphData?.nodes) return new Map<string, { x: number; y: number }>();

    const positions = new Map<string, { x: number; y: number }>();
    const nodes = graphData.nodes;
    const edges = graphData.edges;

    // Initialize positions in a circle
    const centerX = dimensions.width / 2;
    const centerY = dimensions.height / 2;
    const radius = Math.min(dimensions.width, dimensions.height) * 0.35;

    nodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / nodes.length;
      positions.set(node.id, {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      });
    });

    // Simple force simulation (a few iterations)
    for (let iter = 0; iter < 50; iter++) {
      // Repulsion between all nodes
      nodes.forEach((nodeA) => {
        nodes.forEach((nodeB) => {
          if (nodeA.id === nodeB.id) return;
          const posA = positions.get(nodeA.id)!;
          const posB = positions.get(nodeB.id)!;
          const dx = posA.x - posB.x;
          const dy = posA.y - posB.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = 1000 / (dist * dist);
          posA.x += (dx / dist) * force;
          posA.y += (dy / dist) * force;
        });
      });

      // Attraction along edges
      edges.forEach((edge) => {
        const posA = positions.get(edge.source);
        const posB = positions.get(edge.target);
        if (!posA || !posB) return;
        const dx = posB.x - posA.x;
        const dy = posB.y - posA.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = dist * 0.01;
        posA.x += (dx / dist) * force;
        posA.y += (dy / dist) * force;
        posB.x -= (dx / dist) * force;
        posB.y -= (dy / dist) * force;
      });

      // Center gravity
      nodes.forEach((node) => {
        const pos = positions.get(node.id)!;
        pos.x += (centerX - pos.x) * 0.01;
        pos.y += (centerY - pos.y) * 0.01;
      });
    }

    // Clamp to bounds
    nodes.forEach((node) => {
      const pos = positions.get(node.id)!;
      pos.x = Math.max(50, Math.min(dimensions.width - 50, pos.x));
      pos.y = Math.max(50, Math.min(dimensions.height - 50, pos.y));
    });

    return positions;
  }, [graphData, dimensions]);

  // Draw graph on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !graphData) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    // Draw edges
    ctx.strokeStyle = "hsl(var(--muted-foreground) / 0.3)";
    ctx.lineWidth = 1;
    graphData.edges.forEach((edge) => {
      const sourcePos = nodePositions.get(edge.source);
      const targetPos = nodePositions.get(edge.target);
      if (!sourcePos || !targetPos) return;

      ctx.beginPath();
      ctx.moveTo(sourcePos.x, sourcePos.y);
      ctx.lineTo(targetPos.x, targetPos.y);
      ctx.stroke();
    });

    // Draw nodes
    graphData.nodes.forEach((node) => {
      const pos = nodePositions.get(node.id);
      if (!pos) return;

      const isSelected = node.id === selectedNode;
      const radius = isSelected ? 12 : 8;

      // Node circle
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, radius, 0, 2 * Math.PI);

      // Color based on type
      const colors: Record<EntityType, string> = {
        Person: "#3b82f6",
        Organization: "#a855f7",
        Location: "#22c55e",
        Event: "#f97316",
      };
      ctx.fillStyle = colors[node.type] || "#888";
      ctx.fill();

      if (isSelected) {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Label
      ctx.fillStyle = "hsl(var(--foreground))";
      ctx.font = isSelected ? "bold 11px sans-serif" : "10px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(node.label, pos.x, pos.y + radius + 4);
    });
  }, [graphData, nodePositions, selectedNode, dimensions]);

  // Handle canvas click
  const handleCanvasClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !graphData) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Find clicked node
    for (const node of graphData.nodes) {
      const pos = nodePositions.get(node.id);
      if (!pos) continue;

      const dx = x - pos.x;
      const dy = y - pos.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < 15) {
        setSelectedNode(node.id === selectedNode ? null : node.id);
        onEntityClick?.(node.id);
        return;
      }
    }

    setSelectedNode(null);
  };

  // Stats
  const stats = useMemo(() => {
    if (!graphData) return { nodes: 0, edges: 0, byType: {} as Record<EntityType, number> };
    
    const byType: Record<string, number> = {};
    graphData.nodes.forEach((node) => {
      byType[node.type] = (byType[node.type] || 0) + 1;
    });

    return {
      nodes: graphData.nodes.length,
      edges: graphData.edges.length,
      byType: byType as Record<EntityType, number>,
    };
  }, [graphData]);

  if (error) {
    return (
      <Card className="h-full">
        <CardContent className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <p className="text-destructive">Failed to load graph data</p>
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
    <div className="h-full flex gap-4">
      {/* Main Graph Area */}
      <div className="flex-1 flex flex-col gap-4">
        {/* Controls */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Network className="h-5 w-5 text-primary" />
              Knowledge Graph
            </h2>
            <Select
              value={selectedEntityType}
              onValueChange={(v) => setSelectedEntityType(v as EntityType | "all")}
            >
              <SelectTrigger className="w-[150px] h-8">
                <SelectValue placeholder="Filter type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="Person">People</SelectItem>
                <SelectItem value="Organization">Organizations</SelectItem>
                <SelectItem value="Location">Locations</SelectItem>
                <SelectItem value="Event">Events</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMaxNodes((n) => Math.max(10, n - 20))}
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span className="text-xs text-muted-foreground w-16 text-center">
              {maxNodes} nodes
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMaxNodes((n) => Math.min(200, n + 20))}
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Stats Bar */}
        <div className="flex items-center gap-4 text-sm">
          {Object.entries(stats.byType).map(([type, count]) => {
            const config = entityConfig[type as EntityType];
            const Icon = config?.icon || User;
            return (
              <div key={type} className="flex items-center gap-1.5">
                <Icon className={`h-4 w-4 ${config?.color}`} />
                <span className="text-muted-foreground">
                  {count} {type}
                  {count !== 1 ? "s" : ""}
                </span>
              </div>
            );
          })}
          <span className="text-muted-foreground">
            • {stats.edges} relationship{stats.edges !== 1 ? "s" : ""}
          </span>
        </div>

        {/* Canvas */}
        <Card className="flex-1 overflow-hidden">
          <CardContent className="p-0 h-full relative">
            {isLoading ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <Skeleton className="h-full w-full" />
              </div>
            ) : stats.nodes === 0 ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center space-y-2">
                  <Network className="h-12 w-12 text-muted-foreground mx-auto" />
                  <p className="text-muted-foreground">No entities found</p>
                  <p className="text-sm text-muted-foreground">
                    Ingest documents to build the knowledge graph
                  </p>
                </div>
              </div>
            ) : (
              <canvas
                ref={canvasRef}
                width={dimensions.width}
                height={dimensions.height}
                className="w-full h-full cursor-pointer"
                onClick={handleCanvasClick}
              />
            )}
          </CardContent>
        </Card>

        {/* Legend */}
        <div className="flex items-center justify-center gap-6 text-xs">
          {Object.entries(entityConfig).map(([type, config]) => {
            const Icon = config.icon;
            return (
              <div key={type} className="flex items-center gap-1.5">
                <div className={`w-3 h-3 rounded-full ${config.bgColor}`} />
                <span className="text-muted-foreground">{type}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Entity Details Sidebar */}
      {selectedNode && entityDetails && (
        <Card className="w-80 shrink-0">
          <CardHeader className="py-4">
            <CardTitle className="text-sm flex items-center gap-2">
              {(() => {
                const config = entityConfig[entityDetails.entity.type];
                const Icon = config?.icon || User;
                return <Icon className={`h-4 w-4 ${config?.color}`} />;
              })()}
              {entityDetails.entity.name}
            </CardTitle>
            <Badge variant="outline" className="w-fit">
              {entityDetails.entity.type}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Aliases */}
            {entityDetails.entity.aliases.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">
                  Also known as
                </p>
                <div className="flex flex-wrap gap-1">
                  {entityDetails.entity.aliases.map((alias, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">
                      {alias}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Related Documents */}
            {entityDetails.related_documents.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-2">
                  Mentioned in {entityDetails.related_documents.length} document
                  {entityDetails.related_documents.length !== 1 ? "s" : ""}
                </p>
                <ScrollArea className="h-[150px]">
                  <div className="space-y-1">
                    {entityDetails.related_documents.slice(0, 10).map((doc: any, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2 p-2 rounded hover:bg-muted cursor-pointer"
                        onClick={() => onDocumentClick?.(doc.id)}
                      >
                        <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="text-xs truncate">{doc.filename}</span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}

            {/* Relationships */}
            {entityDetails.relationships.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-2">
                  Relationships
                </p>
                <div className="space-y-1">
                  {entityDetails.relationships.slice(0, 5).map((rel, i) => (
                    <div
                      key={i}
                      className="text-xs p-2 rounded bg-muted/50"
                    >
                      <span className="text-muted-foreground">{rel.type}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default KnowledgeGraph;
