import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface-page)] disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 hover-elevate active-elevate-2",
  {
    variants: {
      variant: {
        primary:
          "bg-primary text-primary-foreground border border-primary/90 shadow-sm hover:bg-[var(--interactive-primary-hover)] hover:border-[var(--interactive-primary-hover)]",
        secondary:
          "bg-[var(--surface-elevated)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:bg-[var(--state-hover)] hover:border-[var(--border-strong)]",
        quiet:
          "bg-transparent text-[var(--text-secondary)] border border-transparent hover:bg-[var(--state-hover)] hover:text-[var(--text-primary)]",
        "link-accent":
          "border-0 bg-transparent p-0 h-auto text-[var(--interactive-accent)] underline underline-offset-4 hover:text-[var(--interactive-accent-hover)]",
        danger:
          "bg-destructive text-destructive-foreground border border-destructive/85 shadow-sm hover:bg-destructive/90",
        ghost:
          "bg-transparent border border-transparent text-[var(--text-secondary)] hover:bg-[var(--state-hover)] hover:text-[var(--text-primary)]",
        outline:
          "border bg-[var(--surface-panel)] text-[var(--text-primary)] [border-color:var(--button-outline)] hover:bg-[var(--state-hover)] hover:[border-color:var(--border-strong)]",
        default:
          "bg-primary text-primary-foreground border border-primary/90 shadow-sm hover:bg-[var(--interactive-primary-hover)] hover:border-[var(--interactive-primary-hover)]",
        destructive:
          "bg-destructive text-destructive-foreground border border-destructive/85 shadow-sm hover:bg-destructive/90",
        link: "border-0 bg-transparent p-0 h-auto text-[var(--interactive-accent)] underline underline-offset-4 hover:text-[var(--interactive-accent-hover)]",
      },
      size: {
        default: "min-h-10 px-4 py-2",
        sm: "min-h-8 rounded-md px-3 text-xs",
        lg: "min-h-11 rounded-md px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
