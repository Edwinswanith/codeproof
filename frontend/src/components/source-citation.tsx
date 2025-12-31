"use client";

import * as React from "react";
import { FileCode2, ExternalLink, Hash } from "lucide-react";
import { cn } from "@/lib/utils";
import { CodeBlock } from "@/components/code-block";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export interface Citation {
  id: string;
  sourceIndex: number;
  filePath: string;
  startLine: number;
  endLine: number;
  snippet: string;
  snippetSha?: string;
  symbolId?: string;
  symbolName?: string;
  relevanceScore?: number;
  retrievalSource?: "trigram" | "vector" | "both";
  githubUrl?: string;
}

interface CitationBadgeProps {
  sourceIndex: number;
  onClick?: () => void;
  className?: string;
}

export function CitationBadge({ sourceIndex, onClick, className }: CitationBadgeProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-primary/10 text-primary text-xs font-mono rounded border border-primary/20 hover:bg-primary/20 transition-colors cursor-pointer",
        className
      )}
    >
      <Hash className="h-2.5 w-2.5" />
      {sourceIndex}
    </button>
  );
}

interface SourceCitationProps {
  citation: Citation;
  variant?: "inline" | "card";
  className?: string;
}

export function SourceCitation({ citation, variant = "inline", className }: SourceCitationProps) {
  if (variant === "inline") {
    return (
      <Dialog>
        <DialogTrigger asChild>
          <CitationBadge sourceIndex={citation.sourceIndex} />
        </DialogTrigger>
        <DialogContent variant="terminal" className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-sm">
              <FileCode2 className="h-4 w-4" />
              {citation.filePath}
              <span className="text-muted-foreground">
                :{citation.startLine}-{citation.endLine}
              </span>
            </DialogTitle>
          </DialogHeader>
          <CodeBlock
            code={citation.snippet}
            filename={citation.filePath}
            startLine={citation.startLine}
            endLine={citation.endLine}
            githubUrl={citation.githubUrl}
            maxHeight={300}
          />
          {citation.symbolName && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="font-medium">Symbol:</span>
              <code className="px-1.5 py-0.5 bg-muted rounded font-mono text-xs">
                {citation.symbolName}
              </code>
            </div>
          )}
        </DialogContent>
      </Dialog>
    );
  }

  // Card variant
  return (
    <div
      className={cn(
        "group border border-border rounded-lg overflow-hidden hover:border-primary/30 transition-colors",
        className
      )}
    >
      <div className="flex items-center justify-between px-3 py-2 bg-muted/30 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="flex items-center justify-center w-5 h-5 rounded bg-primary/10 text-primary text-xs font-mono font-medium">
            {citation.sourceIndex}
          </div>
          <div className="font-mono text-sm truncate max-w-[300px]">
            {citation.filePath}
          </div>
          <span className="text-xs text-muted-foreground font-mono">
            :{citation.startLine}-{citation.endLine}
          </span>
        </div>
        {citation.githubUrl && (
          <a
            href={citation.githubUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-foreground transition-all"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
      </div>
      <pre className="p-3 text-sm font-mono overflow-x-auto bg-card max-h-32">
        <code>{citation.snippet}</code>
      </pre>
      {citation.symbolName && (
        <div className="px-3 py-2 border-t border-border bg-muted/20 text-xs text-muted-foreground">
          <span className="font-medium">Symbol:</span>{" "}
          <code className="text-foreground">{citation.symbolName}</code>
          {citation.retrievalSource && (
            <span className="ml-3 opacity-70">
              via {citation.retrievalSource}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// List of citations
interface CitationListProps {
  citations: Citation[];
  className?: string;
}

export function CitationList({ citations, className }: CitationListProps) {
  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <FileCode2 className="h-4 w-4" />
        <span>Sources ({citations.length})</span>
      </div>
      <div className="space-y-2">
        {citations.map((citation) => (
          <SourceCitation key={citation.id} citation={citation} variant="card" />
        ))}
      </div>
    </div>
  );
}
