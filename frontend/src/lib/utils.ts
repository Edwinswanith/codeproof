import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatRelativeTime(date: Date | string): string {
  const now = new Date();
  const then = new Date(date);
  const diffInSeconds = Math.floor((now.getTime() - then.getTime()) / 1000);

  if (diffInSeconds < 60) return "just now";
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`;

  return then.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + "...";
}

export function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
}

export function getConfidenceColor(tier: "high" | "medium" | "low" | "none"): string {
  switch (tier) {
    case "high": return "text-success";
    case "medium": return "text-warning";
    case "low": return "text-critical";
    case "none": return "text-muted-foreground";
    default: return "text-muted-foreground";
  }
}

export function getSeverityColor(severity: "critical" | "warning" | "info"): string {
  switch (severity) {
    case "critical": return "severity-critical";
    case "warning": return "severity-warning";
    case "info": return "severity-info";
    default: return "";
  }
}

export function getStatusColor(status: string): string {
  switch (status) {
    case "ready":
    case "completed":
      return "text-success bg-success/10";
    case "indexing":
    case "analyzing":
    case "pending":
      return "text-warning bg-warning/10";
    case "failed":
      return "text-critical bg-critical/10";
    default:
      return "text-muted-foreground bg-muted";
  }
}
