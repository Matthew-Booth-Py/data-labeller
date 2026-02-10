import { useLocation } from "wouter";
import { Shell } from "@/components/layout/Shell";
import { GettingStartedWizard } from "@/components/onboarding";

export default function GettingStarted() {
  const [, setLocation] = useLocation();

  return (
    <Shell>
      <GettingStartedWizard
        onComplete={() => setLocation("/project/tutorial")}
      />
    </Shell>
  );
}
