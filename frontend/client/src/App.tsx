import { Link, Route, Switch } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/components/ui/theme-provider";
import { Button } from "@/components/ui/button";
import Dashboard from "@/pages/Dashboard";
import ProjectsList from "@/pages/ProjectsList";
import ProjectWorkspace from "@/pages/ProjectWorkspace";
import CreateProject from "@/pages/CreateProject";
import Settings from "@/pages/Settings";
import FieldsLibrary from "@/pages/FieldsLibrary";
import Extraction from "@/pages/Extraction";

function Router() {
  return (
    <Switch>
      <Route path="/" component={Dashboard} />
      <Route path="/projects" component={ProjectsList} />
      <Route path="/projects/new" component={CreateProject} />
      <Route path="/project/:id" component={ProjectWorkspace} />
      <Route path="/fields-library" component={FieldsLibrary} />
      <Route path="/extraction/:id" component={Extraction} />
      <Route path="/settings" component={Settings} />
      <Route>
        <div className="flex min-h-screen items-center justify-center px-4 bg-gradient-to-br from-background via-[var(--surface-page)] to-muted/30">
          <div className="w-full max-w-lg rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-panel)] p-8 text-center shadow-sm">
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--text-secondary)]">
              intelligent ingestion
            </p>
            <h1 className="mt-3 text-3xl text-primary font-semibold">
              Page Not Found
            </h1>
            <p className="mt-3 text-sm text-[var(--text-secondary)]">
              The page you are trying to open is unavailable or has moved.
            </p>
            <div className="mt-6 flex justify-center gap-2">
              <Button asChild>
                <Link href="/">Return to Dashboard</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/projects">Open Projects</Link>
              </Button>
            </div>
          </div>
        </div>
      </Route>
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="light"
        enableSystem={false}
        forcedTheme="light"
        disableTransitionOnChange
      >
        <TooltipProvider>
          <Router />
          <Toaster />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
