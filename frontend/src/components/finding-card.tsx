"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ShieldAlert,
  Info,
  FileCode2,
  ExternalLink,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge, SeverityBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/code-block";

export type FindingSeverity = "critical" | "warning" | "info";

export interface Finding {
  id: string;
  severity: FindingSeverity;
  category: string;
  filePath: string;
  startLine?: number;
  endLine?: number;
  evidence: {
    snippet?: string;
    pattern?: string;
    match?: string;
    reason: string;
    confidence?: string;
  };
  explanation?: string;
  suggestedFix?: string;
  githubUrl?: string;
  status?: "open" | "resolved" | "ignored" | "false_positive";
}

interface FindingCardProps {
  finding: Finding;
  expanded?: boolean;
  onToggle?: () => void;
  className?: string;
}

const severityConfig = {
  critical: {
    icon: ShieldAlert,
    color: "text-critical",
    bgColor: "bg-critical/5",
    borderColor: "border-critical/30",
    label: "Critical",
  },
  warning: {
    icon: AlertTriangle,
    color: "text-warning",
    bgColor: "bg-warning/5",
    borderColor: "border-warning/30",
    label: "Warning",
  },
  info: {
    icon: Info,
    color: "text-info",
    bgColor: "bg-info/5",
    borderColor: "border-info/30",
    label: "Info",
  },
};

const categoryLabels: Record<string, string> = {
  secret_exposure: "Secret Exposure",
  migration_destructive: "Destructive Migration",
  auth_middleware_removed: "Auth Middleware Removed",
  dependency_changed: "Dependency Changed",
  env_leaked: "Environment Leaked",
  private_key_exposed: "Private Key Exposed",
};

export function FindingCard({ finding, expanded = false, onToggle, className }: FindingCardProps) {
  const [isExpanded, setIsExpanded] = React.useState(expanded);
  const config = severityConfig[finding.severity];
  const Icon = config.icon;

  const handleToggle = () => {
    setIsExpanded(!isExpanded);
    onToggle?.();
  };

  return (
    <Card
      className={cn(
        "overflow-hidden transition-all duration-200",
        config.bgColor,
        config.borderColor,
        "hover:border-opacity-60",
        className
      )}
    >
      <CardContent className="p-0">
        {/* Header - always visible */}
        <button
          onClick={handleToggle}
          className="w-full p-4 flex items-start gap-3 text-left hover:bg-black/5 transition-colors"
        >
          <div className={cn("mt-0.5 p-1.5 rounded-md", config.bgColor, config.color)}>
            <Icon className="h-4 w-4" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <SeverityBadge severity={finding.severity} />
              <Badge variant="outline" className="font-mono text-xs">
                {categoryLabels[finding.category] || finding.category}
              </Badge>
              {finding.status && finding.status !== "open" && (
                <Badge
                  variant={finding.status === "resolved" ? "success" : "secondary"}
                  className="text-xs"
                >
                  {finding.status}
                </Badge>
              )}
            </div>

            <p className={cn("mt-2 text-sm font-medium", config.color)}>
              {finding.evidence.reason}
            </p>

            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground font-mono">
              <FileCode2 className="h-3 w-3" />
              <span className="truncate">{finding.filePath}</span>
              {finding.startLine && (
                <span className="opacity-70">
                  :{finding.startLine}
                  {finding.endLine && finding.endLine !== finding.startLine && `-${finding.endLine}`}
                </span>
              )}
            </div>
          </div>

          <div className="shrink-0 p-1">
            {isExpanded ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
        </button>

        {/* Expanded content */}
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-border/50"
          >
            <div className="p-4 space-y-4">
              {/* Pattern match */}
              {finding.evidence.pattern && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Pattern Matched
                  </p>
                  <code className="block px-3 py-2 bg-muted/50 rounded text-sm font-mono text-primary">
                    {finding.evidence.pattern}
                  </code>
                </div>
              )}

              {/* Code snippet */}
              {finding.evidence.snippet && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Code Snippet
                  </p>
                  <CodeBlock
                    code={finding.evidence.snippet}
                    filename={finding.filePath}
                    startLine={finding.startLine}
                    endLine={finding.endLine}
                    githubUrl={finding.githubUrl}
                    maxHeight={200}
                  />
                </div>
              )}

              {/* Explanation */}
              {finding.explanation && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Explanation
                  </p>
                  <p className="text-sm text-foreground/80">{finding.explanation}</p>
                </div>
              )}

              {/* Suggested fix */}
              {finding.suggestedFix && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Suggested Fix
                  </p>
                  <p className="text-sm text-foreground/80">{finding.suggestedFix}</p>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2 pt-2">
                {finding.githubUrl && (
                  <Button variant="outline" size="sm" asChild>
                    <a href={finding.githubUrl} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                      View on GitHub
                    </a>
                  </Button>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </CardContent>
    </Card>
  );
}

// Finding list component
interface FindingListProps {
  findings: Finding[];
  className?: string;
}

export function FindingList({ findings, className }: FindingListProps) {
  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  // Sort by severity
  const sortedFindings = [...findings].sort((a, b) => {
    const order = { critical: 0, warning: 1, info: 2 };
    return order[a.severity] - order[b.severity];
  });

  return (
    <div className={cn("space-y-3", className)}>
      {sortedFindings.map((finding) => (
        <FindingCard
          key={finding.id}
          finding={finding}
          expanded={expandedId === finding.id}
          onToggle={() => setExpandedId(expandedId === finding.id ? null : finding.id)}
        />
      ))}
    </div>
  );
}
