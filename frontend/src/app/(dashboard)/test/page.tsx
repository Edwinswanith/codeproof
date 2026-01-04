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
  Zap,
  GitBranch,
  Database,
  Network,
  Box,
  Search,
  Globe,
  Building2,
  Scale,
  FileText,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Target,
  TrendingUp,
  Lock,
  Eye,
  Sparkles,
} from "lucide-react";
import { PageContainer } from "@/components/layout/dashboard-layout";
import { PageHeader } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// Types
interface Finding {
  severity: string;
  category: string;
  file_path: string;
  line_number: number;
  code_snippet: string;
  reason: string;
  confidence: string;
  suggested_fix?: string;
}

interface AnalyzeResponse {
  repo: string;
  branch: string;
  files_analyzed: number;
  summary: string;
  findings: Finding[];
  critical_count: number;
  warning_count: number;
  info_count: number;
}

interface SymbolInfo {
  type: string;
  name: string;
  file_path: string;
  line_start: number;
  line_end: number;
  signature?: string;
}

interface DeepAnalyzeResponse {
  repo: string;
  branch: string;
  commit_sha: string;
  detected_framework: string;
  files_parsed: number;
  total_symbols: number;
  total_functions: number;
  total_classes: number;
  parse_errors: string[];
  findings: Finding[];
  critical_count: number;
  warning_count: number;
  info_count: number;
  top_level_symbols: SymbolInfo[];
  entry_points: SymbolInfo[];
  qa_ready: boolean;
  chunks_indexed: number;
}

interface CitedSource {
  index: number;
  file_path: string;
  line_start: number;
  line_end: number;
  symbol_name?: string;
  code_snippet: string;
  url: string;
}

interface DeepAskResponse {
  answer_text: string;
  sections: Array<{ text: string; source_indices: number[] }>;
  unknowns: string[];
  sources: CitedSource[];
  confidence: string;
  call_graph_context?: string[];
}

interface AskResponse {
  answer: string;
  sources: Array<{ file_path: string; url: string }>;
}

// Compliance types
interface RegulationInfo {
  code: string;
  name: string;
  description: string;
  key_requirements: string[];
  penalties: string;
  official_url: string;
}

interface ComplianceFinding {
  check_id: string;
  regulation: string;
  category: string;
  severity: string;
  title: string;
  description: string;
  file_path: string;
  line_start: number;
  line_end: number;
  code_snippet: string;
  recommendation: string;
  reference_url: string;
}

interface ComplianceResponse {
  region: string;
  sector: string;
  applicable_regulations: RegulationInfo[];
  findings: ComplianceFinding[];
  summary: {
    total_findings: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  ai_analysis: string;
  recommendations: string[];
  compliance_score: number;
  risk_level: string;
}

// Region/Sector options
const REGIONS = [
  { code: "eu", name: "European Union", flag: "EU" },
  { code: "us", name: "United States", flag: "US" },
  { code: "uk", name: "United Kingdom", flag: "UK" },
  { code: "india", name: "India", flag: "IN" },
  { code: "australia", name: "Australia", flag: "AU" },
  { code: "canada", name: "Canada", flag: "CA" },
  { code: "brazil", name: "Brazil", flag: "BR" },
  { code: "singapore", name: "Singapore", flag: "SG" },
  { code: "uae", name: "UAE", flag: "AE" },
  { code: "global", name: "Global", flag: "GL" },
];

const SECTORS = [
  { code: "healthcare", name: "Healthcare", icon: "+" },
  { code: "finance", name: "Finance & Banking", icon: "$" },
  { code: "ecommerce", name: "E-Commerce", icon: "S" },
  { code: "education", name: "Education", icon: "E" },
  { code: "government", name: "Government", icon: "G" },
  { code: "saas", name: "SaaS / Software", icon: "C" },
  { code: "social_media", name: "Social Media", icon: "@" },
  { code: "iot", name: "IoT / Hardware", icon: "I" },
  { code: "ai_ml", name: "AI / Machine Learning", icon: "A" },
  { code: "general", name: "General", icon: "*" },
];

// Components
function MarkdownRenderer({ content }: { content: string }) {
  const lines = content.split('\n');

  return (
    <div className="space-y-2 text-sm">
      {lines.map((line, i) => {
        if (line.startsWith('### ')) {
          return <h3 key={i} className="font-semibold mt-4 mb-2">{line.slice(4)}</h3>;
        }
        if (line.startsWith('## ')) {
          return <h2 key={i} className="font-bold mt-4 mb-2 text-lg">{line.slice(3)}</h2>;
        }
        if (line.startsWith('- ') || line.startsWith('* ')) {
          return <li key={i} className="ml-4">{line.slice(2)}</li>;
        }
        if (line.match(/^\d+\./)) {
          return <li key={i} className="ml-4 list-decimal">{line.replace(/^\d+\.\s*/, '')}</li>;
        }
        if (line.trim() === '') {
          return <div key={i} className="h-2" />;
        }
        if (line.includes('`')) {
          const parts = line.split(/(`[^`]+`)/g);
          return (
            <p key={i}>
              {parts.map((part, j) => {
                if (part.startsWith('`') && part.endsWith('`')) {
                  return <code key={j} className="bg-muted px-1 rounded text-xs font-mono">{part.slice(1, -1)}</code>;
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

function CodeSnippet({ code, filePath }: { code: string; filePath: string }) {
  const extension = filePath.split('.').pop() || '';

  return (
    <div className="bg-zinc-950 rounded-md overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900 border-b border-zinc-800">
        <span className="text-xs text-zinc-400 font-mono">{filePath}</span>
        <Badge variant="outline" className="text-xs h-5">{extension}</Badge>
      </div>
      <pre className="p-3 text-xs font-mono overflow-x-auto max-h-48">
        <code className="text-zinc-300 whitespace-pre">{code}</code>
      </pre>
    </div>
  );
}

function SeverityIcon({ severity }: { severity: string }) {
  switch (severity) {
    case 'critical':
      return <AlertCircle className="h-4 w-4 text-destructive" />;
    case 'high':
      return <AlertCircle className="h-4 w-4 text-orange-500" />;
    case 'warning':
    case 'medium':
      return <AlertTriangle className="h-4 w-4 text-warning" />;
    default:
      return <Info className="h-4 w-4 text-blue-500" />;
  }
}

function ProgressStep({
  icon: Icon,
  label,
  status
}: {
  icon: React.ElementType;
  label: string;
  status: 'pending' | 'active' | 'complete'
}) {
  return (
    <div className={`flex items-center gap-2 ${status === 'active' ? 'text-primary' : status === 'complete' ? 'text-success' : 'text-muted-foreground'}`}>
      {status === 'active' ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : status === 'complete' ? (
        <CheckCircle className="h-4 w-4" />
      ) : (
        <Icon className="h-4 w-4" />
      )}
      <span className="text-sm">{label}</span>
    </div>
  );
}

function StatCard({
  value,
  label,
  variant = "default",
  icon: Icon
}: {
  value: number | string;
  label: string;
  variant?: "default" | "success" | "warning" | "destructive" | "primary";
  icon?: React.ElementType;
}) {
  const colorClasses = {
    default: "",
    success: "border-success/50 bg-success/5",
    warning: "border-warning/50 bg-warning/5",
    destructive: "border-destructive/50 bg-destructive/5",
    primary: "border-primary/50 bg-primary/5",
  };

  const textClasses = {
    default: "",
    success: "text-success",
    warning: "text-warning",
    destructive: "text-destructive",
    primary: "text-primary",
  };

  return (
    <Card className={colorClasses[variant]}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className={`text-2xl font-bold ${textClasses[variant]}`}>{value}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>
          {Icon && <Icon className={`h-5 w-5 ${textClasses[variant]} opacity-50`} />}
        </div>
      </CardContent>
    </Card>
  );
}

function ComplianceScoreRing({ score, riskLevel }: { score: number; riskLevel: string }) {
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  const getColor = () => {
    if (score >= 80) return "text-success stroke-success";
    if (score >= 60) return "text-warning stroke-warning";
    return "text-destructive stroke-destructive";
  };

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg className="w-32 h-32 transform -rotate-90">
        <circle
          cx="64"
          cy="64"
          r="45"
          stroke="currentColor"
          strokeWidth="8"
          fill="none"
          className="text-muted/30"
        />
        <circle
          cx="64"
          cy="64"
          r="45"
          strokeWidth="8"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          className={getColor()}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className={`text-2xl font-bold ${getColor().split(' ')[0]}`}>{Math.round(score)}</span>
        <span className="text-xs text-muted-foreground uppercase">{riskLevel}</span>
      </div>
    </div>
  );
}

function ExpandableCard({
  title,
  children,
  defaultExpanded = false,
  badge,
  icon: Icon
}: {
  title: string;
  children: React.ReactNode;
  defaultExpanded?: boolean;
  badge?: React.ReactNode;
  icon?: React.ElementType;
}) {
  const [isExpanded, setIsExpanded] = React.useState(defaultExpanded);

  return (
    <Card>
      <CardHeader
        className="cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            {Icon && <Icon className="h-4 w-4" />}
            {title}
          </CardTitle>
          <div className="flex items-center gap-2">
            {badge}
            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </div>
        </div>
      </CardHeader>
      {isExpanded && <CardContent>{children}</CardContent>}
    </Card>
  );
}

export default function TestPage() {
  const [repoUrl, setRepoUrl] = React.useState("");
  const [question, setQuestion] = React.useState("");
  const [isAnalyzing, setIsAnalyzing] = React.useState(false);
  const [isAsking, setIsAsking] = React.useState(false);
  const [isCheckingCompliance, setIsCheckingCompliance] = React.useState(false);
  const [analysisMode, setAnalysisMode] = React.useState<'quick' | 'deep'>('deep');
  const [analyzeResult, setAnalyzeResult] = React.useState<AnalyzeResponse | null>(null);
  const [deepResult, setDeepResult] = React.useState<DeepAnalyzeResponse | null>(null);
  const [askResult, setAskResult] = React.useState<AskResponse | null>(null);
  const [deepAskResult, setDeepAskResult] = React.useState<DeepAskResponse | null>(null);
  const [complianceResult, setComplianceResult] = React.useState<ComplianceResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [analysisStep, setAnalysisStep] = React.useState<string>('');

  // Compliance state
  const [selectedRegion, setSelectedRegion] = React.useState("us");
  const [selectedSector, setSelectedSector] = React.useState("saas");

  const handleAnalyze = async () => {
    if (!repoUrl.trim()) return;

    setIsAnalyzing(true);
    setError(null);
    setAnalyzeResult(null);
    setDeepResult(null);
    setComplianceResult(null);

    try {
      if (analysisMode === 'deep') {
        setAnalysisStep('cloning');
        const response = await fetch(`${API_URL}/test/deep-analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repo_url: repoUrl, include_embeddings: true }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        setDeepResult(data);
        setAnalysisStep('complete');
      } else {
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
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze repository");
    } finally {
      setIsAnalyzing(false);
      setAnalysisStep('');
    }
  };

  const handleAsk = async () => {
    if (!repoUrl.trim() || !question.trim()) return;

    setIsAsking(true);
    setError(null);
    setAskResult(null);
    setDeepAskResult(null);

    try {
      if (analysisMode === 'deep' && deepResult?.qa_ready) {
        const response = await fetch(`${API_URL}/test/deep-ask`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repo_url: repoUrl, question }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        setDeepAskResult(data);
      } else {
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
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to ask question");
    } finally {
      setIsAsking(false);
    }
  };

  const handleComplianceCheck = async () => {
    if (!repoUrl.trim() || !deepResult) return;

    setIsCheckingCompliance(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/test/compliance/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: repoUrl,
          region: selectedRegion,
          sector: selectedSector,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setComplianceResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to check compliance");
    } finally {
      setIsCheckingCompliance(false);
    }
  };

  const currentResult = analysisMode === 'deep' ? deepResult : analyzeResult;
  const hasAnalysis = deepResult || analyzeResult;

  return (
    <PageContainer>
      <PageHeader
        title="Code Analysis"
        description="Security scanning, compliance checking, and deep code understanding"
      />

      <div className="mt-6 space-y-6">
        {/* Repository Input Card */}
        <Card className="border-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Github className="h-5 w-5" />
              Analyze GitHub Repository
            </CardTitle>
            <CardDescription>
              Enter a public GitHub repository URL to analyze
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="https://github.com/owner/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                className="flex-1"
              />
              <Button
                onClick={handleAnalyze}
                disabled={!repoUrl.trim() || isAnalyzing}
                variant="glow"
              >
                {isAnalyzing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
              </Button>
            </div>

            {/* Analysis Mode Toggle */}
            <div className="flex gap-2">
              <Button
                variant={analysisMode === 'quick' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setAnalysisMode('quick')}
                className="flex-1"
              >
                <Zap className="h-4 w-4 mr-2" />
                Quick Scan
              </Button>
              <Button
                variant={analysisMode === 'deep' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setAnalysisMode('deep')}
                className="flex-1"
              >
                <Database className="h-4 w-4 mr-2" />
                Deep Analysis
              </Button>
            </div>

            <p className="text-sm text-muted-foreground">
              {analysisMode === 'quick'
                ? "Fast security scan via GitHub API. Best for quick checks."
                : "Full AST parsing with symbol table, call graph, and semantic Q&A. Best for comprehensive analysis."}
            </p>

            {/* Deep analysis progress */}
            {isAnalyzing && analysisMode === 'deep' && (
              <div className="p-4 bg-muted/50 rounded-lg space-y-2">
                <ProgressStep icon={GitBranch} label="Cloning repository" status={analysisStep === 'cloning' ? 'active' : 'pending'} />
                <ProgressStep icon={Code2} label="Parsing with tree-sitter" status="pending" />
                <ProgressStep icon={Network} label="Building symbol table & call graph" status="pending" />
                <ProgressStep icon={Search} label="Generating embeddings" status="pending" />
              </div>
            )}
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

        {/* Results Section */}
        {hasAnalysis && (
          <Tabs defaultValue="overview" className="space-y-4">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="overview" className="gap-2">
                <TrendingUp className="h-4 w-4" />
                Overview
              </TabsTrigger>
              <TabsTrigger value="security" className="gap-2">
                <Shield className="h-4 w-4" />
                Security
              </TabsTrigger>
              <TabsTrigger value="compliance" className="gap-2">
                <Scale className="h-4 w-4" />
                Compliance
              </TabsTrigger>
              <TabsTrigger value="ask" className="gap-2">
                <MessageSquare className="h-4 w-4" />
                Ask AI
              </TabsTrigger>
            </TabsList>

            {/* Overview Tab */}
            <TabsContent value="overview" className="space-y-4">
              {deepResult && (
                <>
                  {/* Summary Banner */}
                  <Card className="border-primary/50 bg-gradient-to-r from-primary/10 to-transparent">
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="p-3 bg-primary/20 rounded-lg">
                            <Database className="h-8 w-8 text-primary" />
                          </div>
                          <div>
                            <h2 className="text-xl font-bold">{deepResult.repo}</h2>
                            <p className="text-sm text-muted-foreground">
                              {deepResult.branch} @ {deepResult.commit_sha.slice(0, 8)}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge variant="outline">{deepResult.detected_framework}</Badge>
                              {deepResult.qa_ready && (
                                <Badge variant="default" className="bg-success">
                                  <Sparkles className="h-3 w-3 mr-1" />
                                  AI Ready
                                </Badge>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Stats Grid */}
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <StatCard value={deepResult.files_parsed} label="Files Parsed" icon={FileCode2} />
                    <StatCard value={deepResult.total_symbols} label="Symbols" icon={Box} />
                    <StatCard value={deepResult.total_classes} label="Classes" icon={Code2} />
                    <StatCard value={deepResult.total_functions} label="Functions" icon={Target} />
                    <StatCard
                      value={deepResult.chunks_indexed}
                      label="AI Chunks"
                      variant="primary"
                      icon={Sparkles}
                    />
                  </div>

                  {/* Code Structure */}
                  {deepResult.entry_points.length > 0 && (
                    <ExpandableCard
                      title="Entry Points"
                      defaultExpanded={true}
                      icon={Target}
                      badge={<Badge variant="secondary">{deepResult.entry_points.length}</Badge>}
                    >
                      <div className="grid gap-2">
                        {deepResult.entry_points.slice(0, 10).map((ep, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between p-2 bg-muted/50 rounded-md hover:bg-muted transition-colors"
                          >
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="font-mono text-xs">
                                {ep.type === 'function' ? 'fn' : ep.type === 'method' ? 'method' : 'class'}
                              </Badge>
                              <span className="font-mono text-sm">{ep.name}</span>
                            </div>
                            <span className="text-xs text-muted-foreground font-mono">
                              {ep.file_path}:{ep.line_start}
                            </span>
                          </div>
                        ))}
                      </div>
                    </ExpandableCard>
                  )}

                  {deepResult.top_level_symbols.length > 0 && (
                    <ExpandableCard
                      title="Top Level Symbols"
                      icon={Box}
                      badge={<Badge variant="secondary">{deepResult.top_level_symbols.length}</Badge>}
                    >
                      <div className="grid gap-2 md:grid-cols-2">
                        {deepResult.top_level_symbols.slice(0, 12).map((sym, i) => (
                          <div
                            key={i}
                            className="flex items-center gap-2 p-2 bg-muted/50 rounded-md"
                          >
                            <Badge variant={sym.type === 'class' ? 'default' : 'secondary'} className="font-mono text-xs">
                              {sym.type}
                            </Badge>
                            <span className="font-mono text-sm truncate">{sym.name}</span>
                          </div>
                        ))}
                      </div>
                    </ExpandableCard>
                  )}
                </>
              )}

              {analyzeResult && analysisMode === 'quick' && (
                <Card>
                  <CardContent className="p-6">
                    <div className="flex items-center gap-3">
                      <Shield className="h-6 w-6 text-primary" />
                      <div>
                        <p className="font-medium">{analyzeResult.summary}</p>
                        <p className="text-sm text-muted-foreground">
                          {analyzeResult.repo} @ {analyzeResult.branch}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Security Tab */}
            <TabsContent value="security" className="space-y-4">
              {/* Security Stats */}
              <div className="grid grid-cols-3 gap-4">
                <StatCard
                  value={currentResult?.critical_count || 0}
                  label="Critical"
                  variant={currentResult?.critical_count ? "destructive" : "default"}
                  icon={AlertCircle}
                />
                <StatCard
                  value={currentResult?.warning_count || 0}
                  label="Warnings"
                  variant={currentResult?.warning_count ? "warning" : "default"}
                  icon={AlertTriangle}
                />
                <StatCard
                  value={currentResult?.info_count || 0}
                  label="Info"
                  icon={Info}
                />
              </div>

              {/* Findings */}
              {currentResult?.findings && currentResult.findings.length > 0 ? (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Shield className="h-5 w-5" />
                      Security Findings
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {currentResult.findings.map((finding, i) => (
                      <div key={i} className="border rounded-lg overflow-hidden">
                        <div className="flex items-center justify-between p-3 bg-muted/50 border-b">
                          <div className="flex items-center gap-3">
                            <SeverityIcon severity={finding.severity} />
                            <div className="flex items-center gap-2">
                              <Badge variant={finding.severity === "critical" ? "destructive" : finding.severity === "warning" ? "warning" : "secondary"}>
                                {finding.severity}
                              </Badge>
                              <Badge variant="outline">{finding.category.replace(/_/g, ' ')}</Badge>
                            </div>
                          </div>
                          <a
                            href={`https://github.com/${currentResult.repo || deepResult?.repo}/blob/${currentResult.branch || deepResult?.branch}/${finding.file_path}#L${finding.line_number}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                          >
                            <FileCode2 className="h-3 w-3" />
                            {finding.file_path}:{finding.line_number}
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </div>
                        <div className="p-3 border-b">
                          <p className="text-sm">{finding.reason}</p>
                        </div>
                        <CodeSnippet code={finding.code_snippet} filePath={finding.file_path} />
                        {finding.suggested_fix && (
                          <div className="p-3 bg-success/5 border-t border-success/20">
                            <p className="text-xs text-success font-medium mb-1">Suggested Fix:</p>
                            <p className="text-sm">{finding.suggested_fix}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : (
                <Card className="border-success/30">
                  <CardContent className="p-8 text-center">
                    <CheckCircle className="h-12 w-12 text-success mx-auto mb-4" />
                    <p className="font-medium text-lg">No high-risk security issues detected</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Scanned for secrets, private keys, .env files, destructive migrations, and auth bypass
                    </p>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Compliance Tab */}
            <TabsContent value="compliance" className="space-y-4">
              {!deepResult ? (
                <Card>
                  <CardContent className="p-8 text-center">
                    <Database className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <p className="font-medium">Deep Analysis Required</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Run Deep Analysis first to enable compliance checking
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <>
                  {/* Region & Sector Selection */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Globe className="h-5 w-5" />
                        Deployment Context
                      </CardTitle>
                      <CardDescription>
                        Select your target market and industry for compliance analysis
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {/* Region Selection */}
                      <div>
                        <label className="text-sm font-medium mb-2 block">Target Region</label>
                        <div className="grid grid-cols-5 gap-2">
                          {REGIONS.map((region) => (
                            <Button
                              key={region.code}
                              variant={selectedRegion === region.code ? "default" : "outline"}
                              size="sm"
                              onClick={() => setSelectedRegion(region.code)}
                              className="flex-col h-auto py-2"
                            >
                              <span className="text-lg">{region.flag}</span>
                              <span className="text-xs">{region.name}</span>
                            </Button>
                          ))}
                        </div>
                      </div>

                      {/* Sector Selection */}
                      <div>
                        <label className="text-sm font-medium mb-2 block">Industry Sector</label>
                        <div className="grid grid-cols-5 gap-2">
                          {SECTORS.map((sector) => (
                            <Button
                              key={sector.code}
                              variant={selectedSector === sector.code ? "default" : "outline"}
                              size="sm"
                              onClick={() => setSelectedSector(sector.code)}
                              className="flex-col h-auto py-2"
                            >
                              <Building2 className="h-4 w-4" />
                              <span className="text-xs">{sector.name}</span>
                            </Button>
                          ))}
                        </div>
                      </div>

                      <Button
                        onClick={handleComplianceCheck}
                        disabled={isCheckingCompliance}
                        className="w-full"
                        variant="glow"
                        size="lg"
                      >
                        {isCheckingCompliance ? (
                          <>
                            <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                            Analyzing Compliance...
                          </>
                        ) : (
                          <>
                            <Scale className="h-5 w-5 mr-2" />
                            Check Compliance
                          </>
                        )}
                      </Button>
                    </CardContent>
                  </Card>

                  {/* Compliance Results */}
                  {complianceResult && (
                    <>
                      {/* Compliance Score */}
                      <Card className="overflow-hidden">
                        <div className="grid md:grid-cols-3 divide-y md:divide-y-0 md:divide-x">
                          <div className="p-6 flex flex-col items-center justify-center">
                            <ComplianceScoreRing
                              score={complianceResult.compliance_score}
                              riskLevel={complianceResult.risk_level}
                            />
                            <p className="text-sm text-muted-foreground mt-2">Compliance Score</p>
                          </div>
                          <div className="p-6 space-y-3">
                            <h4 className="font-medium flex items-center gap-2">
                              <FileText className="h-4 w-4" />
                              Applicable Regulations
                            </h4>
                            <div className="space-y-2">
                              {complianceResult.applicable_regulations.map((reg, i) => (
                                <div key={i} className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <Badge variant="outline">{reg.code}</Badge>
                                    <span className="text-sm">{reg.name}</span>
                                  </div>
                                  <a
                                    href={reg.official_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-muted-foreground hover:text-foreground"
                                  >
                                    <ExternalLink className="h-3 w-3" />
                                  </a>
                                </div>
                              ))}
                            </div>
                          </div>
                          <div className="p-6 space-y-3">
                            <h4 className="font-medium flex items-center gap-2">
                              <AlertTriangle className="h-4 w-4" />
                              Finding Summary
                            </h4>
                            <div className="grid grid-cols-2 gap-2">
                              <div className="text-center p-2 bg-destructive/10 rounded">
                                <div className="text-lg font-bold text-destructive">{complianceResult.summary.critical}</div>
                                <div className="text-xs text-muted-foreground">Critical</div>
                              </div>
                              <div className="text-center p-2 bg-orange-500/10 rounded">
                                <div className="text-lg font-bold text-orange-500">{complianceResult.summary.high}</div>
                                <div className="text-xs text-muted-foreground">High</div>
                              </div>
                              <div className="text-center p-2 bg-warning/10 rounded">
                                <div className="text-lg font-bold text-warning">{complianceResult.summary.medium}</div>
                                <div className="text-xs text-muted-foreground">Medium</div>
                              </div>
                              <div className="text-center p-2 bg-blue-500/10 rounded">
                                <div className="text-lg font-bold text-blue-500">{complianceResult.summary.low}</div>
                                <div className="text-xs text-muted-foreground">Low</div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </Card>

                      {/* AI Analysis */}
                      {complianceResult.ai_analysis && (
                        <ExpandableCard
                          title="AI Compliance Analysis"
                          defaultExpanded={true}
                          icon={Sparkles}
                        >
                          <div className="prose prose-sm max-w-none">
                            <MarkdownRenderer content={complianceResult.ai_analysis} />
                          </div>
                        </ExpandableCard>
                      )}

                      {/* Recommendations */}
                      {complianceResult.recommendations.length > 0 && (
                        <ExpandableCard
                          title="Recommendations"
                          defaultExpanded={true}
                          icon={CheckCircle}
                          badge={<Badge variant="secondary">{complianceResult.recommendations.length}</Badge>}
                        >
                          <div className="space-y-2">
                            {complianceResult.recommendations.map((rec, i) => (
                              <div key={i} className="flex gap-3 p-3 bg-muted/50 rounded-lg">
                                <div className="flex-shrink-0 w-6 h-6 bg-primary/20 rounded-full flex items-center justify-center">
                                  <span className="text-xs font-medium text-primary">{i + 1}</span>
                                </div>
                                <p className="text-sm">{rec}</p>
                              </div>
                            ))}
                          </div>
                        </ExpandableCard>
                      )}

                      {/* Compliance Findings */}
                      {complianceResult.findings.length > 0 && (
                        <ExpandableCard
                          title="Compliance Findings"
                          icon={AlertTriangle}
                          badge={<Badge variant="warning">{complianceResult.findings.length}</Badge>}
                        >
                          <div className="space-y-4">
                            {complianceResult.findings.map((finding, i) => (
                              <div key={i} className="border rounded-lg overflow-hidden">
                                <div className="flex items-center justify-between p-3 bg-muted/50 border-b">
                                  <div className="flex items-center gap-3">
                                    <SeverityIcon severity={finding.severity} />
                                    <div>
                                      <p className="font-medium text-sm">{finding.title}</p>
                                      <div className="flex items-center gap-2 mt-1">
                                        <Badge variant="outline" className="text-xs">{finding.regulation}</Badge>
                                        <Badge variant="secondary" className="text-xs">{finding.category}</Badge>
                                      </div>
                                    </div>
                                  </div>
                                  <a
                                    href={finding.reference_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                                  >
                                    <BookOpen className="h-3 w-3" />
                                    Reference
                                  </a>
                                </div>
                                <div className="p-3 border-b">
                                  <p className="text-sm text-muted-foreground">{finding.description}</p>
                                </div>
                                {finding.code_snippet && (
                                  <CodeSnippet code={finding.code_snippet} filePath={finding.file_path} />
                                )}
                                <div className="p-3 bg-primary/5 border-t">
                                  <p className="text-xs text-primary font-medium mb-1">Recommendation:</p>
                                  <p className="text-sm">{finding.recommendation}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </ExpandableCard>
                      )}
                    </>
                  )}
                </>
              )}
            </TabsContent>

            {/* Ask AI Tab */}
            <TabsContent value="ask" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <MessageSquare className="h-5 w-5" />
                    Ask About This Codebase
                  </CardTitle>
                  <CardDescription>
                    {analysisMode === 'deep' && deepResult?.qa_ready
                      ? "Using semantic search and call graph for accurate answers"
                      : "Using code context for answers"}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {analysisMode === 'deep' && !deepResult?.qa_ready && (
                    <div className="p-4 bg-muted rounded-lg flex items-center gap-3">
                      <Database className="h-5 w-5 text-muted-foreground" />
                      <p className="text-sm text-muted-foreground">
                        Run Deep Analysis to enable semantic Q&A with call graph context
                      </p>
                    </div>
                  )}

                  <Textarea
                    placeholder="Ask a question... (e.g., 'How does authentication work?' or 'What are the main API endpoints?')"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    className="min-h-[100px]"
                  />

                  {/* Quick questions */}
                  <div className="flex flex-wrap gap-2">
                    {[
                      "How does authentication work?",
                      "What are the main components?",
                      "How is data validated?",
                      "What database is used?",
                    ].map((q) => (
                      <Button
                        key={q}
                        variant="outline"
                        size="sm"
                        onClick={() => setQuestion(q)}
                        className="text-xs"
                      >
                        {q}
                      </Button>
                    ))}
                  </div>

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
                        Searching code...
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

              {/* Deep Q&A Result */}
              {deepAskResult && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <MessageSquare className="h-5 w-5 text-primary" />
                        Answer
                      </span>
                      <Badge variant={deepAskResult.confidence === 'high' ? 'default' : deepAskResult.confidence === 'medium' ? 'secondary' : 'outline'}>
                        {deepAskResult.confidence} confidence
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="prose prose-sm max-w-none">
                      <MarkdownRenderer content={deepAskResult.answer_text} />
                    </div>

                    {deepAskResult.call_graph_context && deepAskResult.call_graph_context.length > 0 && (
                      <div className="p-3 bg-muted/50 rounded-lg">
                        <h4 className="text-xs font-medium mb-2 flex items-center gap-1">
                          <Network className="h-3 w-3" /> Call Graph Context
                        </h4>
                        <div className="space-y-1">
                          {deepAskResult.call_graph_context.slice(0, 3).map((chain, i) => (
                            <code key={i} className="block text-xs text-muted-foreground font-mono">{chain}</code>
                          ))}
                        </div>
                      </div>
                    )}

                    {deepAskResult.unknowns.length > 0 && (
                      <div className="p-3 bg-warning/5 border border-warning/20 rounded-lg">
                        <h4 className="text-xs font-medium mb-2 text-warning">Could not determine:</h4>
                        <ul className="list-disc list-inside text-sm">
                          {deepAskResult.unknowns.map((u, i) => <li key={i}>{u}</li>)}
                        </ul>
                      </div>
                    )}

                    {deepAskResult.sources.length > 0 && (
                      <ExpandableCard
                        title="Sources"
                        defaultExpanded={true}
                        icon={FileCode2}
                        badge={<Badge variant="secondary">{deepAskResult.sources.length}</Badge>}
                      >
                        <div className="space-y-3">
                          {deepAskResult.sources.map((source, i) => (
                            <div key={i} className="border rounded-lg overflow-hidden">
                              <div className="flex items-center justify-between p-2 bg-muted/50">
                                <span className="text-xs font-mono">[{source.index}] {source.file_path}:{source.line_start}</span>
                                <a href={source.url} target="_blank" rel="noopener noreferrer">
                                  <ExternalLink className="h-3 w-3" />
                                </a>
                              </div>
                              <pre className="p-2 text-xs font-mono overflow-x-auto bg-zinc-950 max-h-32">
                                <code className="text-zinc-300">{source.code_snippet.slice(0, 400)}{source.code_snippet.length > 400 ? '...' : ''}</code>
                              </pre>
                            </div>
                          ))}
                        </div>
                      </ExpandableCard>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Simple Q&A Result */}
              {askResult && !deepAskResult && (
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
                          Sources ({askResult.sources.length} files)
                        </div>
                        <div className="grid gap-2">
                          {askResult.sources.map((source, i) => (
                            <a
                              key={i}
                              href={source.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-2 p-2 text-sm font-mono bg-muted rounded hover:bg-muted/80"
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
        )}
      </div>
    </PageContainer>
  );
}
