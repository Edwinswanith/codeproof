"use client";

import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import { cn } from "@/lib/utils";

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & {
    variant?: "default" | "success" | "warning" | "critical";
    size?: "sm" | "default" | "lg";
  }
>(({ className, value, variant = "default", size = "default", ...props }, ref) => {
  const variantClasses = {
    default: "bg-primary",
    success: "bg-success",
    warning: "bg-warning",
    critical: "bg-critical",
  };

  const sizeClasses = {
    sm: "h-1",
    default: "h-2",
    lg: "h-3",
  };

  return (
    <ProgressPrimitive.Root
      ref={ref}
      className={cn(
        "relative w-full overflow-hidden rounded-full bg-muted",
        sizeClasses[size],
        className
      )}
      {...props}
    >
      <ProgressPrimitive.Indicator
        className={cn(
          "h-full w-full flex-1 transition-all duration-500 ease-out",
          variantClasses[variant]
        )}
        style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
      />
    </ProgressPrimitive.Root>
  );
});
Progress.displayName = ProgressPrimitive.Root.displayName;

// Circular progress indicator
interface CircularProgressProps {
  value: number;
  size?: number;
  strokeWidth?: number;
  variant?: "default" | "success" | "warning" | "critical";
  showValue?: boolean;
  className?: string;
}

function CircularProgress({
  value,
  size = 40,
  strokeWidth = 4,
  variant = "default",
  showValue = false,
  className,
}: CircularProgressProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;

  const variantClasses = {
    default: "stroke-primary",
    success: "stroke-success",
    warning: "stroke-warning",
    critical: "stroke-critical",
  };

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)}>
      <svg
        width={size}
        height={size}
        className="rotate-[-90deg]"
      >
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-muted"
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className={cn("transition-all duration-500 ease-out", variantClasses[variant])}
        />
      </svg>
      {showValue && (
        <span className="absolute text-xs font-medium">
          {Math.round(value)}%
        </span>
      )}
    </div>
  );
}

export { Progress, CircularProgress };
