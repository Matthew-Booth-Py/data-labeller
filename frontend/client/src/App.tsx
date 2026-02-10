import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import Dashboard from "@/pages/Dashboard";
import ProjectsList from "@/pages/ProjectsList";
import ProjectWorkspace from "@/pages/ProjectWorkspace";
import CreateProject from "@/pages/CreateProject";
import Settings from "@/pages/Settings";
import FieldsLibrary from "@/pages/FieldsLibrary";
import Extraction from "@/pages/Extraction";
import GettingStarted from "@/pages/GettingStarted";

function Router() {
  return (
    <Switch>
      <Route path="/" component={Dashboard} />
      <Route path="/getting-started" component={GettingStarted} />
      <Route path="/projects" component={ProjectsList} />
      <Route path="/projects/new" component={CreateProject} />
      <Route path="/project/:id" component={ProjectWorkspace} />
      <Route path="/fields-library" component={FieldsLibrary} />
      <Route path="/extraction/:id" component={Extraction} />
      <Route path="/settings" component={Settings} />
      <Route>
        <div className="flex items-center justify-center min-h-screen">
          <h1 className="text-2xl font-bold">404 - Not Found</h1>
        </div>
      </Route>
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Router />
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
