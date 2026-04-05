import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import { Link, useLocation } from "wouter";
import { cn } from "@/lib/utils";
import {
  Bell,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  LayoutDashboard,
  LifeBuoy,
  Menu,
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
  {
    label: "Projects",
    icon: FolderOpen,
    href: "/projects",
    section: "projects",
  },
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

type DesktopRailMode = "expanded" | "compact" | "hidden";
const DESKTOP_RAIL_MODE_STORAGE_KEY = "shell:desktop-rail-mode";

const isDesktopRailMode = (value: string | null): value is DesktopRailMode =>
  value === "expanded" || value === "compact" || value === "hidden";

const SidebarLogo = () => (
  <img src="/logo.svg" alt="Intelligent Ingestion Logo" className="h-9 w-9" />
);

interface RailContentProps {
  location: string;
  section: AppSection;
  projectId?: string;
  onNavigate?: () => void;
  compact?: boolean;
}

function RailContent({
  location,
  section,
  projectId,
  onNavigate,
  compact = false,
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
      <div
        className={cn(
          "h-16 flex items-center border-b border-sidebar-border",
          compact ? "justify-center px-2" : "px-4 gap-3",
        )}
      >
        <SidebarLogo />
        {!compact && (
          <div className="min-w-0">
            <p className="text-sm font-semibold leading-tight truncate">
              Intelligent Ingestion
            </p>
            <p className="text-[11px] text-sidebar-foreground/70">
              Extraction Studio
            </p>
          </div>
        )}
      </div>

      <div
        className={cn("py-4 flex-1 overflow-y-auto", compact ? "px-2" : "px-3")}
      >
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
                aria-label={item.label}
                title={item.label}
                className={cn(
                  "flex items-center text-sm font-medium rounded-md border border-transparent",
                  compact ? "justify-center px-2 py-2.5" : "gap-3 px-3 py-2.5",
                  isActive
                    ? "bg-sidebar-accent/90 text-sidebar-accent-foreground border-sidebar-accent/50 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]"
                    : "text-sidebar-foreground/80 hover:text-sidebar-foreground hover:bg-sidebar-accent/35",
                )}
              >
                <item.icon className="h-4 w-4" />
                {!compact && item.label}
              </Link>
            );
          })}
        </nav>

        {workspaceLinks.length > 0 && !compact && (
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

      <div
        className={cn(
          "border-t border-sidebar-border",
          compact ? "p-2" : "p-4",
        )}
      >
        {compact ? (
          <div className="flex flex-col items-center gap-2">
            <div className="h-8 w-8 rounded-full bg-sidebar-accent/80 flex items-center justify-center text-xs font-semibold">
              JD
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-sidebar-foreground/80 hover:text-sidebar-foreground hover:bg-sidebar-accent/35"
              onClick={onNavigate}
              title="Support"
              aria-label="Support"
            >
              <LifeBuoy className="h-4 w-4" />
            </Button>
          </div>
        ) : (
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
        )}
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
  utilityRightContent?: ReactNode;
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
  utilityRightContent,
  projectId,
  showProjectRail = true,
  contentClassName,
  contentFullWidth = false,
}: ShellProps) {
  const [location] = useLocation();
  const [mobileRailOpen, setMobileRailOpen] = useState(false);
  const [desktopRailMode, setDesktopRailMode] = useState<DesktopRailMode>(
    () => {
      if (typeof window === "undefined") return "expanded";
      const storedValue = window.localStorage.getItem(
        DESKTOP_RAIL_MODE_STORAGE_KEY,
      );
      return isDesktopRailMode(storedValue) ? storedValue : "expanded";
    },
  );
  const lastVisibleRailModeRef =
    useRef<Exclude<DesktopRailMode, "hidden">>("expanded");
  const isDesktopRailCompact = desktopRailMode === "compact";

  useEffect(() => {
    if (!showProjectRail) return;
    window.localStorage.setItem(DESKTOP_RAIL_MODE_STORAGE_KEY, desktopRailMode);
  }, [desktopRailMode, showProjectRail]);

  useEffect(() => {
    if (desktopRailMode === "hidden") return;
    lastVisibleRailModeRef.current = desktopRailMode;
  }, [desktopRailMode]);

  const toggleDesktopRailCompact = () => {
    setDesktopRailMode((current) => {
      if (current === "hidden") return "compact";
      return current === "expanded" ? "compact" : "expanded";
    });
  };

  const toggleDesktopRailVisibility = () => {
    setDesktopRailMode((current) => {
      if (current === "hidden") {
        return lastVisibleRailModeRef.current;
      }
      lastVisibleRailModeRef.current = current;
      return "hidden";
    });
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-[var(--border-subtle)] backdrop-blur-xl bg-background/92">
        <div className="h-14 px-4 md:px-6 flex items-center gap-3 md:gap-6">
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

          {showProjectRail && (
            <div className="hidden lg:flex items-center gap-1">
              {desktopRailMode !== "hidden" && (
                <Button
                  variant="quiet"
                  size="icon"
                  className="h-9 w-9"
                  onClick={toggleDesktopRailCompact}
                  aria-label={
                    isDesktopRailCompact
                      ? "Expand navigation rail"
                      : "Shrink navigation rail"
                  }
                  title={
                    isDesktopRailCompact
                      ? "Expand navigation rail"
                      : "Shrink navigation rail"
                  }
                >
                  {isDesktopRailCompact ? (
                    <ChevronRight className="h-4 w-4" />
                  ) : (
                    <ChevronLeft className="h-4 w-4" />
                  )}
                </Button>
              )}
              <Button
                variant="quiet"
                size="icon"
                className="h-9 w-9"
                onClick={toggleDesktopRailVisibility}
                aria-label={
                  desktopRailMode === "hidden"
                    ? "Show navigation rail"
                    : "Hide navigation rail"
                }
                title={
                  desktopRailMode === "hidden"
                    ? "Show navigation rail"
                    : "Hide navigation rail"
                }
              >
                {desktopRailMode === "hidden" ? (
                  <Menu className="h-4 w-4" />
                ) : (
                  <X className="h-4 w-4" />
                )}
              </Button>
            </div>
          )}

          <div className="min-w-0">
            <p className="text-sm font-semibold tracking-wide text-primary uppercase">
              Beazley Studio
            </p>
            <p className="text-xs text-[var(--text-secondary)]">
              Intelligent Ingestion
            </p>
          </div>

          <div className="ml-auto md:ml-0 flex items-center gap-2">
            {utilityRightContent}
            <Button variant="quiet" size="icon" className="h-9 w-9">
              <Bell className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <div className="flex">
        {showProjectRail && desktopRailMode !== "hidden" && (
          <aside
            className={cn(
              "hidden lg:block shrink-0 sticky top-14 h-[calc(100vh-3.5rem)] transition-[width] duration-200 ease-out",
              isDesktopRailCompact ? "w-20" : "w-72",
            )}
          >
            <RailContent
              location={location}
              section={section}
              projectId={projectId}
              compact={isDesktopRailCompact}
            />
          </aside>
        )}

        <div className="flex-1 min-w-0">
          {(pageTitle || primaryAction || secondaryActions) && (
            <div className="px-4 md:px-8 py-3 border-b border-[var(--border-subtle)] bg-[var(--surface-elevated)]">
              <div className="w-full lg:max-w-[80vw] mx-auto">
                <div className="flex items-center justify-between gap-4">
                  {pageTitle && (
                    <h1 className="text-lg font-semibold text-primary tracking-tight truncate">
                      {pageTitle}
                    </h1>
                  )}
                  <div className="flex items-center gap-2 shrink-0">
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
              <div className="w-full lg:max-w-[80vw] mx-auto">{children}</div>
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
