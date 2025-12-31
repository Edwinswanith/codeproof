"use client";

import * as React from "react";
import { Copy, Check, ExternalLink, FileCode2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { SimpleTooltip } from "@/components/ui/tooltip";

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
  startLine?: number;
  endLine?: number;
  highlightLines?: number[];
  showLineNumbers?: boolean;
  maxHeight?: number;
  githubUrl?: string;
  className?: string;
}

export function CodeBlock({
  code,
  language = "php",
  filename,
  startLine = 1,
  endLine,
  highlightLines = [],
  showLineNumbers = true,
  maxHeight = 400,
  githubUrl,
  className,
}: CodeBlockProps) {
  const [copied, setCopied] = React.useState(false);
  const lines = code.split("\n");
  const actualEndLine = endLine ?? startLine + lines.length - 1;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={cn("group relative rounded-lg border border-border bg-card overflow-hidden", className)}>
      {/* Header */}
      {filename && (
        <div className="flex items-center justify-between px-4 py-2 bg-muted/50 border-b border-border">
          <div className="flex items-center gap-2 text-sm text-muted-foreground font-mono">
            <FileCode2 className="h-4 w-4" />
            <span className="truncate">{filename}</span>
            {startLine && (
              <span className="text-xs opacity-70">
                :{startLine}{actualEndLine !== startLine ? `-${actualEndLine}` : ""}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {githubUrl && (
              <SimpleTooltip content="View on GitHub">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="h-7 w-7"
                  asChild
                >
                  <a href={githubUrl} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </Button>
              </SimpleTooltip>
            )}
            <SimpleTooltip content={copied ? "Copied!" : "Copy code"}>
              <Button
                variant="ghost"
                size="icon-sm"
                className="h-7 w-7"
                onClick={handleCopy}
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-success" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
              </Button>
            </SimpleTooltip>
          </div>
        </div>
      )}

      {/* Code content */}
      <div
        className="overflow-auto"
        style={{ maxHeight }}
      >
        <pre className="p-4 text-sm leading-relaxed">
          <code className="font-mono">
            {lines.map((line, index) => {
              const lineNumber = startLine + index;
              const isHighlighted = highlightLines.includes(lineNumber);

              return (
                <div
                  key={index}
                  className={cn(
                    "flex",
                    isHighlighted && "bg-warning/10 -mx-4 px-4 border-l-2 border-warning"
                  )}
                >
                  {showLineNumbers && (
                    <span className="select-none w-12 pr-4 text-right text-muted-foreground/50 shrink-0">
                      {lineNumber}
                    </span>
                  )}
                  <span className="flex-1 whitespace-pre overflow-x-auto">
                    {line || " "}
                  </span>
                </div>
              );
            })}
          </code>
        </pre>
      </div>

      {/* Language badge */}
      {language && !filename && (
        <div className="absolute top-2 right-2 px-2 py-0.5 bg-muted rounded text-xs text-muted-foreground font-mono">
          {language}
        </div>
      )}
    </div>
  );
}

// Inline code component
export function InlineCode({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <code className={cn("px-1.5 py-0.5 bg-muted rounded text-sm font-mono", className)}>
      {children}
    </code>
  );
}

// Diff view component
interface DiffBlockProps {
  oldCode: string;
  newCode: string;
  filename?: string;
  className?: string;
}

export function DiffBlock({ oldCode, newCode, filename, className }: DiffBlockProps) {
  const oldLines = oldCode.split("\n");
  const newLines = newCode.split("\n");

  return (
    <div className={cn("rounded-lg border border-border bg-card overflow-hidden", className)}>
      {filename && (
        <div className="flex items-center gap-2 px-4 py-2 bg-muted/50 border-b border-border">
          <FileCode2 className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground font-mono">{filename}</span>
        </div>
      )}
      <div className="overflow-auto max-h-96">
        <pre className="p-4 text-sm leading-relaxed font-mono">
          {oldLines.map((line, i) => (
            <div key={`old-${i}`} className="flex bg-critical/5 text-critical/90">
              <span className="select-none w-8 pr-2 text-right opacity-50">-</span>
              <span>{line || " "}</span>
            </div>
          ))}
          {newLines.map((line, i) => (
            <div key={`new-${i}`} className="flex bg-success/5 text-success/90">
              <span className="select-none w-8 pr-2 text-right opacity-50">+</span>
              <span>{line || " "}</span>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
