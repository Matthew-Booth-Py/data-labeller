import { useMemo, useState, type ComponentType, type ReactNode } from "react";
import { Link, useLocation } from "wouter";
import { cn } from "@/lib/utils";
import {
  Bell,
  BookOpen,
  FolderOpen,
  LayoutDashboard,
  LifeBuoy,
  Menu,
  Search,
  Settings as SettingsIcon,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export type AppSection =
  | "dashboard"
  | "projects"
  | "workspace"
  | "library"
  | "settings";

interface NavItem {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  section: AppSection;
}

const NAV_ITEMS: NavItem[] = [
  {
    label: "Dashboard",
    icon: LayoutDashboard,
    href: "/",
    section: "dashboard",
  },
  { label: "Projects", icon: FolderOpen, href: "/projects", section: "projects" },
  {
    label: "Fields Library",
    icon: BookOpen,
    href: "/fields-library",
    section: "library",
  },
  {
    label: "Settings",
    icon: SettingsIcon,
    href: "/settings",
    section: "settings",
  },
];

const SidebarLogo = () => (
  <img src="/logo.svg" alt="Intelligent Ingestion Logo" className="h-9 w-9" />
);

interface RailContentProps {
  location: string;
  section: AppSection;
  projectId?: string;
  onNavigate?: () => void;
}

function RailContent({
  location,
  section,
  projectId,
  onNavigate,
}: RailContentProps) {
  const workspaceLinks = useMemo(() => {
    if (!projectId) return [];
    return [
      { label: "Schema", href: `/project/${projectId}#schema` },
      { label: "Documents", href: `/project/${projectId}#documents` },
      { label: "Extraction", href: `/project/${projectId}#extraction` },
      { label: "Data Labeller", href: `/project/${projectId}#labeller` },
      { label: "Evaluate", href: `/project/${projectId}#evaluate` },
      { label: "Deployment", href: `/project/${projectId}#deployment` },
    ];
  }, [projectId]);

  return (
    <div className="h-full bg-sidebar text-sidebar-foreground border-r border-sidebar-border flex flex-col">
      <div className="h-16 flex items-center px-4 border-b border-sidebar-border gap-3">
        <SidebarLogo />
        <div className="min-w-0">
          <p className="text-sm font-semibold leading-tight truncate">
            Intelligent Ingestion
          </p>
          <p className="text-[11px] text-sidebar-foreground/70">Extraction Studio</p>
        </div>
      </div>

      <div className="px-3 py-4 flex-1 overflow-y-auto">
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              section === item.section ||
              location === item.href ||
              (item.href === "/projects" && location.startsWith("/project/"));

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-md border border-transparent",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground border-sidebar-accent/35"
                    : "text-sidebar-foreground/80 hover:text-sidebar-foreground hover:bg-sidebar-accent/35",
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {workspaceLinks.length > 0 && (
          <div className="mt-8">
            <h4 className="px-3 text-[11px] font-semibold text-sidebar-foreground/65 mb-2 uppercase tracking-wider">
              Current Project
            </h4>
            <nav className="space-y-1">
              {workspaceLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={onNavigate}
                  className="block px-3 py-2 text-sm rounded-md text-sidebar-foreground/80 hover:text-sidebar-foreground hover:bg-sidebar-accent/25"
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-sidebar-border">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-sidebar-accent/80 flex items-center justify-center text-xs font-semibold">
            JD
          </div>
          <div className="flex-1 overflow-hidden">
            <p className="text-sm font-medium truncate">Jane Doe</p>
            <p className="text-xs text-sidebar-foreground/70 truncate">
              Operations Analyst
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-sidebar-foreground/80 hover:text-sidebar-foreground hover:bg-sidebar-accent/35"
            onClick={onNavigate}
          >
            <LifeBuoy className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

interface ShellProps {
  children: ReactNode;
  section: AppSection;
  pageTitle?: string;
  pageDescription?: string;
  primaryAction?: React.ReactNode;
  secondaryActions?: React.ReactNode;
  projectId?: string;
  showProjectRail?: boolean;
  contentClassName?: string;
  /** When true, children are not wrapped in max-w-[1300px]; use for pages that need full-width sections (e.g. tab bar) */
  contentFullWidth?: boolean;
}

export function Shell({
  children,
  section,
  pageTitle,
  pageDescription,
  primaryAction,
  secondaryActions,
  projectId,
  showProjectRail = true,
  contentClassName,
  contentFullWidth = false,
}: ShellProps) {
  const [location] = useLocation();
  const [mobileRailOpen, setMobileRailOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-[var(--border-subtle)] backdrop-blur-xl bg-background/92">
        <div className="hidden md:flex items-center justify-between h-9 px-6 text-xs border-b border-[var(--border-subtle)] text-[var(--text-secondary)]">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            System healthy
          </div>
          <div className="flex items-center gap-4">
            <span>US region</span>
            <span>Claims ops</span>
            <span>Support</span>
          </div>
        </div>

        <div className="h-16 px-4 md:px-6 flex items-center gap-3 md:gap-6">
          {showProjectRail && (
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setMobileRailOpen(true)}
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </Button>
          )}

          <div className="min-w-0">
            <p className="text-sm font-semibold tracking-wide text-primary uppercase">
              Beazley Studio
            </p>
            <p className="text-xs text-[var(--text-secondary)]">
              Intelligent Ingestion
            </p>
          </div>

          <div className="hidden md:flex ml-auto max-w-lg w-full">
            <div className="relative w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value=""
                readOnly
                aria-label="Search"
                placeholder="Search projects, documents, schemas..."
                className="w-full h-10 rounded-full bg-[var(--surface-panel)] border border-[var(--border-strong)] pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground"
              />
            </div>
          </div>

          <div className="ml-auto md:ml-0 flex items-center gap-2">
            <Button variant="quiet" size="icon" className="h-9 w-9">
              <Bell className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <div className="flex">
        {showProjectRail && (
          <aside className="hidden lg:block w-72 shrink-0 sticky top-[6.25rem] h-[calc(100vh-6.25rem)]">
            <RailContent location={location} section={section} projectId={projectId} />
          </aside>
        )}

        <div className="flex-1 min-w-0">
          {(pageTitle || primaryAction || secondaryActions) && (
            <div className="px-4 md:px-8 py-6 border-b border-[var(--border-subtle)] bg-[var(--surface-elevated)]">
              <div className="max-w-[1300px] mx-auto">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    {pageTitle && (
                      <h1 className="text-2xl md:text-3xl text-primary font-semibold tracking-tight">
                        {pageTitle}
                      </h1>
                    )}
                    {pageDescription && (
                      <p className="mt-1 text-sm md:text-base text-[var(--text-secondary)]">
                        {pageDescription}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2 md:justify-end">
                    {secondaryActions}
                    {primaryAction}
                  </div>
                </div>
              </div>
            </div>
          )}

          <main className={cn("px-4 md:px-8 py-6", contentClassName)}>
            {contentFullWidth ? (
              children
            ) : (
              <div className="max-w-[1300px] mx-auto">{children}</div>
            )}
          </main>
        </div>
      </div>

      {showProjectRail && mobileRailOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/40"
            aria-label="Close navigation"
            onClick={() => setMobileRailOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-[86%] max-w-sm shadow-2xl">
            <div className="absolute right-3 top-3 z-10">
              <Button
                variant="quiet"
                size="icon"
                className="h-8 w-8 bg-white/85"
                onClick={() => setMobileRailOpen(false)}
                aria-label="Close menu"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <RailContent
              location={location}
              section={section}
              projectId={projectId}
              onNavigate={() => setMobileRailOpen(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
