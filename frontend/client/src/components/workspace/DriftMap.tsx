import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    ScatterChart,
    Scatter,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
} from "recharts";

const DRIFT_DATA = [
    { x: 10, y: 30, z: 200, cluster: "Standard" },
    { x: 12, y: 35, z: 240, cluster: "Standard" },
    { x: 15, y: 28, z: 210, cluster: "Standard" },
    { x: 18, y: 32, z: 220, cluster: "Standard" },
    { x: 60, y: 70, z: 150, cluster: "Drift" }, // Outlier
    { x: 65, y: 68, z: 160, cluster: "Drift" }, // Outlier
    { x: 80, y: 20, z: 100, cluster: "New Format" }, // New cluster
    { x: 82, y: 22, z: 110, cluster: "New Format" }, // New cluster
    { x: 85, y: 25, z: 105, cluster: "New Format" }, // New cluster
];

const COLORS = {
    Standard: "hsl(var(--primary))",
    Drift: "hsl(var(--destructive))",
    "New Format": "hsl(var(--accent))",
};

export function DriftMap() {
    return (
        <div className="space-y-6">
            <div className="grid grid-cols-3 gap-6">
                <Card className="bg-white">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            Layout Drift
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-emerald-500">
                            2.4%
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            Within expected range
                        </p>
                    </CardContent>
                </Card>
                <Card className="bg-white">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            New Patterns
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-amber-500">
                            2 Clusters
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            Detected in last 24h
                        </p>
                    </CardContent>
                </Card>
                <Card className="bg-white">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            Field Coverage
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-primary">
                            98.1%
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            +0.5% from last week
                        </p>
                    </CardContent>
                </Card>
            </div>

            <Card className="h-[500px] bg-white border-muted">
                <CardHeader>
                    <CardTitle className="text-primary">
                        Document Embeddings Map
                    </CardTitle>
                    <CardDescription>
                        Visualizing semantic layout distance. Outliers indicate
                        drift.
                    </CardDescription>
                </CardHeader>
                <CardContent className="h-[400px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart
                            margin={{
                                top: 20,
                                right: 20,
                                bottom: 20,
                                left: 20,
                            }}
                        >
                            <CartesianGrid
                                stroke="hsl(var(--muted-foreground))"
                                strokeOpacity={0.25}
                                strokeWidth={1}
                                strokeDasharray="4 4"
                                vertical={true}
                                horizontal={true}
                            />
                            <XAxis
                                type="number"
                                dataKey="x"
                                name="Layout Vector X"
                                hide={false}
                                stroke="hsl(var(--muted-foreground))"
                                strokeOpacity={0.25}
                                fontSize={10}
                            />
                            <YAxis
                                type="number"
                                dataKey="y"
                                name="Layout Vector Y"
                                hide={false}
                                stroke="hsl(var(--muted-foreground))"
                                strokeOpacity={0.25}
                                fontSize={10}
                            />
                            <Tooltip
                                cursor={{ strokeDasharray: "3 3" }}
                                content={({ active, payload }) => {
                                    if (active && payload && payload.length) {
                                        const data = payload[0].payload;
                                        return (
                                            <div className="bg-popover border border-border p-2 rounded shadow-lg text-xs">
                                                <p className="font-semibold text-primary">
                                                    {data.cluster}
                                                </p>
                                                <p>Density: {data.z}</p>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Scatter
                                name="Documents"
                                data={DRIFT_DATA}
                                fill="#8884d8"
                            >
                                {DRIFT_DATA.map((entry, index) => (
                                    <Cell
                                        key={`cell-${index}`}
                                        fill={
                                            COLORS[
                                                entry.cluster as keyof typeof COLORS
                                            ] || "gray"
                                        }
                                    />
                                ))}
                            </Scatter>
                        </ScatterChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>
        </div>
    );
}
