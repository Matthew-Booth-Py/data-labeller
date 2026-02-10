import { Link, useLocation } from "wouter";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FolderOpen,
  Settings as SettingsIcon,
  LifeBuoy,
  Search,
  Bell,
  Sparkles,
  BookOpen,
  GraduationCap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const SidebarLogo = () => (
  <img 
    src="/logo.svg" 
    alt="Intelligent Ingestion Logo" 
    className="h-8 w-8"
  />
);

export function Sidebar() {
  const [location] = useLocation();

  const navItems = [
    { label: "Dashboard", icon: LayoutDashboard, href: "/" },
    { label: "Getting Started", icon: GraduationCap, href: "/getting-started", highlight: true },
    { label: "Projects", icon: FolderOpen, href: "/projects" },
    { label: "Fields Library", icon: BookOpen, href: "/fields-library" },
    { label: "Settings", icon: SettingsIcon, href: "/settings" },
  ];

  return (
    <aside className="w-64 border-r bg-sidebar text-sidebar-foreground flex flex-col h-screen fixed left-0 top-0 z-20">
      <div className="h-14 flex items-center px-4 border-b border-sidebar-border gap-3">
        <SidebarLogo />
        <span className="font-semibold tracking-tight">
          Intelligent Ingestion
        </span>
      </div>

      <div className="px-3 py-4 flex-1">
        <nav className="space-y-1">
          {navItems.map((item) => {
            const isActive = location === item.href ||
              (item.href === "/projects" && location.startsWith("/project/")) ||
              (item.href === "/getting-started" && location === "/getting-started");
            
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : item.highlight
                    ? "text-primary bg-primary/10 hover:bg-primary/20"
                    : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground",
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
                {item.highlight && !isActive && (
                  <Badge variant="outline" className="ml-auto text-xs py-0 px-1 border-primary/50">
                    New
                  </Badge>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="mt-8">
          <h4 className="px-3 text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wider">
            Recent Projects
          </h4>
          <nav className="space-y-1">
            <Link
              href="/project/p1"
              className="flex items-center gap-3 px-3 py-2 text-sm text-muted-foreground hover:text-foreground rounded-md hover:bg-sidebar-accent/50 truncate"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
              Slip Extraction
            </Link>
            <Link
              href="/project/p2"
              className="flex items-center gap-3 px-3 py-2 text-sm text-muted-foreground hover:text-foreground rounded-md hover:bg-sidebar-accent/50 truncate"
            >
              <span className="w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
              Sanctions Screening
            </Link>
          </nav>
        </div>
      </div>

      <div className="p-4 border-t border-sidebar-border">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-sidebar-accent flex items-center justify-center text-xs font-medium">
            JD
          </div>
          <div className="flex-1 overflow-hidden">
            <p className="text-sm font-medium truncate">Jane Doe</p>
            <p className="text-xs text-muted-foreground truncate">
              Operations Analyst
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 hover:bg-accent/20"
          >
            <LifeBuoy className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </aside>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground pl-64">
      <Sidebar />
      <header className="h-14 border-b px-6 flex items-center justify-between sticky top-0 bg-background/80 backdrop-blur-sm z-10">
        <div className="flex items-center gap-4 w-1/3">
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start text-muted-foreground bg-muted/20 border-transparent shadow-none hover:bg-muted/30"
          >
            <Search className="mr-2 h-3.5 w-3.5" />
            Search projects, docs...
            <kbd className="ml-auto pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground opacity-100">
              <span className="text-xs">⌘</span>K
            </kbd>
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 hover:bg-accent/20"
          >
            <Bell className="h-4 w-4" />
          </Button>
        </div>
      </header>
      <main className="min-h-[calc(100vh-3.5rem)] bg-muted/10">{children}</main>
    </div>
  );
}
