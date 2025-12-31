"use client";

import * as React from "react";
import {
  Send,
  Loader2,
  Github,
  AlertTriangle,
  CheckCircle,
  FileCode2,
  MessageSquare,
  Shield,
  AlertCircle,
  Info,
  Code2,
  ExternalLink,
} from "lucide-react";
import { PageContainer } from "@/components/layout/dashboard-layout";
import { PageHeader } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// New deterministic finding format
interface Finding {
  severity: string;  // critical, warning, info
  category: string;
  file_path: string;
  line_number: number;
  code_snippet: string;  // Actual code from the file
  reason: string;  // Specific reason, not generic
  confidence: string;  // exact_match, structural, pattern
  suggested_fix?: string;
}

// New honest response format - no scores, just facts
interface AnalyzeResponse {
  repo: string;
  branch: string;
  files_analyzed: number;
  summary: string;  // Honest human-readable summary
  findings: Finding[];
  critical_count: number;
  warning_count: number;
  info_count: number;
}

interface AskResponse {
  answer: string;
  sources: Array<{ file_path: string; url: string }>;
}

// Simple markdown renderer for Q&A answers only
function MarkdownRenderer({ content }: { content: string }) {
  const lines = content.split('\n');

  return (
    <div className="space-y-2 text-sm">
      {lines.map((line, i) => {
        if (line.startsWith('### ')) {
          return <h3 key={i} className="font-semibold mt-4 mb-2">{line.slice(4)}</h3>;
        }
        if (line.startsWith('## ')) {
          return <h2 key={i} className="font-bold mt-4 mb-2">{line.slice(3)}</h2>;
        }
        if (line.startsWith('- ') || line.startsWith('* ')) {
          return <li key={i} className="ml-4">{line.slice(2)}</li>;
        }
        if (line.trim() === '') {
          return <div key={i} className="h-2" />;
        }
        // Handle inline code
        if (line.includes('`')) {
          const parts = line.split(/(`[^`]+`)/g);
          return (
            <p key={i}>
              {parts.map((part, j) => {
                if (part.startsWith('`') && part.endsWith('`')) {
                  return <code key={j} className="bg-muted px-1 rounded text-xs">{part.slice(1, -1)}</code>;
                }
                return part;
              })}
            </p>
          );
        }
        return <p key={i} className="text-muted-foreground">{line}</p>;
      })}
    </div>
  );
}

// Code snippet display with syntax highlighting simulation
function CodeSnippet({ code, filePath }: { code: string; filePath: string }) {
  const extension = filePath.split('.').pop() || '';

  return (
    <div className="bg-zinc-950 rounded-md overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900 border-b border-zinc-800">
        <span className="text-xs text-zinc-400 font-mono">{filePath}</span>
        <Badge variant="outline" className="text-xs h-5">{extension}</Badge>
      </div>
      <pre className="p-3 text-xs font-mono overflow-x-auto">
        <code className="text-zinc-300 whitespace-pre">{code}</code>
      </pre>
    </div>
  );
}

// Severity icon component
function SeverityIcon({ severity }: { severity: string }) {
  switch (severity) {
    case 'critical':
      return <AlertCircle className="h-4 w-4 text-destructive" />;
    case 'warning':
      return <AlertTriangle className="h-4 w-4 text-warning" />;
    default:
      return <Info className="h-4 w-4 text-blue-500" />;
  }
}

export default function TestPage() {
  const [repoUrl, setRepoUrl] = React.useState("");
  const [question, setQuestion] = React.useState("");
  const [isAnalyzing, setIsAnalyzing] = React.useState(false);
  const [isAsking, setIsAsking] = React.useState(false);
  const [analyzeResult, setAnalyzeResult] = React.useState<AnalyzeResponse | null>(null);
  const [askResult, setAskResult] = React.useState<AskResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const handleAnalyze = async () => {
    if (!repoUrl.trim()) return;

    setIsAnalyzing(true);
    setError(null);
    setAnalyzeResult(null);

    try {
      const response = await fetch(`${API_URL}/test/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setAnalyzeResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze repository");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleAsk = async () => {
    if (!repoUrl.trim() || !question.trim()) return;

    setIsAsking(true);
    setError(null);
    setAskResult(null);

    try {
      const response = await fetch(`${API_URL}/test/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl, question }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setAskResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to ask question");
    } finally {
      setIsAsking(false);
    }
  };

  const totalFindings = analyzeResult
    ? analyzeResult.critical_count + analyzeResult.warning_count + analyzeResult.info_count
    : 0;

  return (
    <PageContainer>
      <PageHeader
        title="Security Analysis"
        description="High-precision deterministic security scanning for GitHub repositories"
      />

      <div className="mt-6 space-y-6">
        {/* Repository Input */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Github className="h-5 w-5" />
              GitHub Repository
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3">
              <Input
                placeholder="https://github.com/owner/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                className="flex-1"
              />
            </div>
            <p className="text-sm text-muted-foreground mt-2">
              Enter any public GitHub repository URL. Analysis uses deterministic pattern matching - no guessing.
            </p>
          </CardContent>
        </Card>

        {error && (
          <Card className="border-destructive">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 text-destructive">
                <AlertTriangle className="h-5 w-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        <Tabs defaultValue="analyze">
          <TabsList>
            <TabsTrigger value="analyze" className="gap-2">
              <Shield className="h-4 w-4" />
              Security Scan
            </TabsTrigger>
            <TabsTrigger value="ask" className="gap-2">
              <MessageSquare className="h-4 w-4" />
              Ask Questions
            </TabsTrigger>
          </TabsList>

          <TabsContent value="analyze" className="space-y-4">
            <Card>
              <CardContent className="pt-6">
                <Button
                  onClick={handleAnalyze}
                  disabled={!repoUrl.trim() || isAnalyzing}
                  className="w-full"
                  variant="glow"
                  size="lg"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                      Scanning repository...
                    </>
                  ) : (
                    <>
                      <Shield className="h-5 w-5 mr-2" />
                      Run Security Scan
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {analyzeResult && (
              <>
                {/* Summary Banner */}
                <Card className={totalFindings === 0 ? "border-success/50 bg-success/5" : "border-warning/50 bg-warning/5"}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                      {totalFindings === 0 ? (
                        <CheckCircle className="h-6 w-6 text-success" />
                      ) : (
                        <AlertTriangle className="h-6 w-6 text-warning" />
                      )}
                      <div>
                        <p className="font-medium">{analyzeResult.summary}</p>
                        <p className="text-sm text-muted-foreground">
                          {analyzeResult.repo} @ {analyzeResult.branch}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Stats - Clean counts only, no scores */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="text-2xl font-bold">{analyzeResult.files_analyzed}</div>
                      <div className="text-xs text-muted-foreground">Files Scanned</div>
                    </CardContent>
                  </Card>
                  <Card className={analyzeResult.critical_count > 0 ? "border-destructive/50" : ""}>
                    <CardContent className="p-4 text-center">
                      <div className={`text-2xl font-bold ${analyzeResult.critical_count > 0 ? 'text-destructive' : ''}`}>
                        {analyzeResult.critical_count}
                      </div>
                      <div className="text-xs text-muted-foreground">Critical</div>
                    </CardContent>
                  </Card>
                  <Card className={analyzeResult.warning_count > 0 ? "border-warning/50" : ""}>
                    <CardContent className="p-4 text-center">
                      <div className={`text-2xl font-bold ${analyzeResult.warning_count > 0 ? 'text-warning' : ''}`}>
                        {analyzeResult.warning_count}
                      </div>
                      <div className="text-xs text-muted-foreground">Warnings</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="text-2xl font-bold text-blue-500">{analyzeResult.info_count}</div>
                      <div className="text-xs text-muted-foreground">Info</div>
                    </CardContent>
                  </Card>
                </div>

                {/* Findings with REAL evidence */}
                {analyzeResult.findings.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Code2 className="h-5 w-5" />
                        Findings ({analyzeResult.findings.length})
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {analyzeResult.findings.map((finding, i) => (
                        <div key={i} className="border rounded-lg overflow-hidden">
                          {/* Finding header */}
                          <div className="flex items-center justify-between p-3 bg-muted/50 border-b">
                            <div className="flex items-center gap-3">
                              <SeverityIcon severity={finding.severity} />
                              <div>
                                <div className="flex items-center gap-2">
                                  <Badge
                                    variant={
                                      finding.severity === "critical" ? "destructive" :
                                      finding.severity === "warning" ? "warning" :
                                      "secondary"
                                    }
                                  >
                                    {finding.severity}
                                  </Badge>
                                  <Badge variant="outline">
                                    {finding.category.replace(/_/g, ' ')}
                                  </Badge>
                                  <Badge variant="outline" className="text-xs">
                                    {finding.confidence}
                                  </Badge>
                                </div>
                              </div>
                            </div>
                            <a
                              href={`https://github.com/${analyzeResult.repo}/blob/${analyzeResult.branch}/${finding.file_path}#L${finding.line_number}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                            >
                              <FileCode2 className="h-3 w-3" />
                              {finding.file_path}:{finding.line_number}
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          </div>

                          {/* Reason */}
                          <div className="p-3 border-b">
                            <p className="text-sm">{finding.reason}</p>
                          </div>

                          {/* Actual code snippet */}
                          <CodeSnippet code={finding.code_snippet} filePath={finding.file_path} />

                          {/* Suggested fix */}
                          {finding.suggested_fix && (
                            <div className="p-3 bg-blue-500/5 border-t border-blue-500/20">
                              <p className="text-xs text-blue-500 font-medium mb-1">Suggested Fix:</p>
                              <p className="text-sm">{finding.suggested_fix}</p>
                            </div>
                          )}
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {/* Clean empty state */}
                {analyzeResult.findings.length === 0 && (
                  <Card className="border-success/30">
                    <CardContent className="p-8 text-center">
                      <CheckCircle className="h-12 w-12 text-success mx-auto mb-4" />
                      <p className="font-medium text-lg">No high-risk issues detected</p>
                      <p className="text-sm text-muted-foreground mt-2">
                        Scanned {analyzeResult.files_analyzed} files for: secrets, private keys,
                        .env exposure, destructive migrations, auth middleware removal.
                      </p>
                    </CardContent>
                  </Card>
                )}
              </>
            )}
          </TabsContent>

          <TabsContent value="ask" className="space-y-4">
            <Card>
              <CardContent className="pt-6 space-y-4">
                <Textarea
                  placeholder="Ask a question about this repository... (e.g., 'How does authentication work?' or 'What are the main components?')"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  className="min-h-[120px]"
                />
                <Button
                  onClick={handleAsk}
                  disabled={!repoUrl.trim() || !question.trim() || isAsking}
                  className="w-full"
                  variant="glow"
                  size="lg"
                >
                  {isAsking ? (
                    <>
                      <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                      Analyzing code and generating answer...
                    </>
                  ) : (
                    <>
                      <Send className="h-5 w-5 mr-2" />
                      Ask Question
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {askResult && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <MessageSquare className="h-5 w-5 text-primary" />
                    Answer
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="mb-6">
                    <MarkdownRenderer content={askResult.answer} />
                  </div>

                  {askResult.sources.length > 0 && (
                    <>
                      <div className="text-sm font-medium mb-3 flex items-center gap-2 border-t pt-4">
                        <FileCode2 className="h-4 w-4" />
                        Sources ({askResult.sources.length} files analyzed)
                      </div>
                      <div className="grid gap-2">
                        {askResult.sources.map((source, i) => (
                          <a
                            key={i}
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 p-2 text-sm font-mono bg-muted rounded hover:bg-muted/80 transition-colors"
                          >
                            <FileCode2 className="h-4 w-4 text-muted-foreground" />
                            <span className="truncate">{source.file_path}</span>
                            <ExternalLink className="h-3 w-3 text-muted-foreground ml-auto" />
                          </a>
                        ))}
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </PageContainer>
  );
}
