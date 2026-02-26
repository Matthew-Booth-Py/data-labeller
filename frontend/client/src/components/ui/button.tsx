import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 hover-elevate active-elevate-2",
  {
    variants: {
      variant: {
        primary:
          "bg-primary text-primary-foreground border border-primary/85 hover:bg-[var(--interactive-primary-hover)]",
        secondary:
          "bg-secondary text-secondary-foreground border border-[var(--button-outline)] hover:bg-secondary/85",
        quiet:
          "bg-transparent text-foreground border border-transparent hover:bg-muted/70",
        "link-accent":
          "border-0 bg-transparent p-0 h-auto text-accent underline underline-offset-4 hover:text-[var(--interactive-accent-hover)]",
        danger:
          "bg-destructive text-destructive-foreground border border-destructive/80 hover:bg-destructive/90",
        ghost: "bg-transparent border border-transparent hover:bg-muted/60",
        outline:
          "border bg-background text-foreground [border-color:var(--button-outline)] hover:bg-muted/55",
        default:
          "bg-primary text-primary-foreground border border-primary/85 hover:bg-[var(--interactive-primary-hover)]",
        destructive:
          "bg-destructive text-destructive-foreground border border-destructive/80 hover:bg-destructive/90",
        link: "border-0 bg-transparent p-0 h-auto text-accent underline underline-offset-4 hover:text-[var(--interactive-accent-hover)]",
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
