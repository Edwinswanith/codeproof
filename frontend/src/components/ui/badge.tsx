import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary/10 text-primary",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground",
        destructive:
          "border-transparent bg-destructive/10 text-destructive",
        outline:
          "text-foreground border-border",
        critical:
          "border-critical/20 bg-critical/10 text-critical",
        warning:
          "border-warning/20 bg-warning/10 text-warning",
        info:
          "border-info/20 bg-info/10 text-info",
        success:
          "border-success/20 bg-success/10 text-success",
        terminal:
          "border-primary/30 bg-primary/5 text-primary font-mono",
        confidence: {
          high: "border-success/20 bg-success/10 text-success",
          medium: "border-warning/20 bg-warning/10 text-warning",
          low: "border-critical/20 bg-critical/10 text-critical",
          none: "border-border bg-muted text-muted-foreground",
        },
      },
      size: {
        default: "text-xs px-2 py-0.5",
        sm: "text-2xs px-1.5 py-0",
        lg: "text-sm px-2.5 py-1",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {
  dot?: boolean;
  dotColor?: string;
}

function Badge({ className, variant, size, dot, dotColor, children, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant, size }), className)} {...props}>
      {dot && (
        <span
          className={cn("mr-1.5 h-1.5 w-1.5 rounded-full", dotColor || "bg-current")}
          style={{ boxShadow: "0 0 4px currentColor" }}
        />
      )}
      {children}
    </div>
  );
}

// Specialized badges for common use cases
function SeverityBadge({ severity, children, ...props }: { severity: "critical" | "warning" | "info" | "success" } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <Badge variant={severity} dot {...props}>
      {children || severity.charAt(0).toUpperCase() + severity.slice(1)}
    </Badge>
  );
}

function ConfidenceBadge({ tier, ...props }: { tier: "high" | "medium" | "low" | "none" } & React.HTMLAttributes<HTMLDivElement>) {
  const labels = {
    high: "High Confidence",
    medium: "Medium Confidence",
    low: "Low Confidence",
    none: "Insufficient Evidence",
  };

  const variants = {
    high: "success" as const,
    medium: "warning" as const,
    low: "critical" as const,
    none: "outline" as const,
  };

  return (
    <Badge variant={variants[tier]} {...props}>
      {labels[tier]}
    </Badge>
  );
}

function StatusBadge({ status, ...props }: { status: string } & React.HTMLAttributes<HTMLDivElement>) {
  const getVariant = (s: string) => {
    switch (s) {
      case "ready":
      case "completed":
        return "success" as const;
      case "indexing":
      case "analyzing":
      case "pending":
        return "warning" as const;
      case "failed":
        return "critical" as const;
      default:
        return "secondary" as const;
    }
  };

  return (
    <Badge variant={getVariant(status)} dot {...props}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
}

export { Badge, badgeVariants, SeverityBadge, ConfidenceBadge, StatusBadge };
