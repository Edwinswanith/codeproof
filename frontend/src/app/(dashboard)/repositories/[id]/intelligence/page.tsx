"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import {
  ShieldAlert,
  ShieldCheck,
  Activity,
  AlertTriangle,
  DatabaseZap,
  Wrench,
  Network,
  Gauge,
  ClipboardCheck,
  PlayCircle,
  Sparkles,
} from "lucide-react";
import { PageContainer } from "@/components/layout/dashboard-layout";
import { PageHeader } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import {
  useControlResults,
  useCreateFixPack,
  useFindings,
  usePromptTemplates,
  useRepository,
  useScanRuns,
  useStartScan,
} from "@/lib/hooks";
import { Finding, FixPackResponse, PromptTemplate } from "@/lib/api";

const severityWeights: Record<string, number> = {
  critical: 20,
  high: 12,
  medium: 6,
  low: 3,
  info: 1,
};

function computeSafetyScore(findings: Finding[]) {
  const totalPenalty = findings.reduce((sum, finding) => {
    const weight = severityWeights[finding.severity] ?? 0;
    return sum + weight;
  }, 0);
  const score = Math.max(0, 100 - totalPenalty);
  return { score, totalPenalty };
}

export default function RepoIntelligencePage() {
  const params = useParams<{ id: string }>();
  const repoId = params.id;

  const { data: repoData } = useRepository(repoId);
  const { data: scanRuns, refetch: refetchScans } = useScanRuns(repoId);
  const { mutate: startScan, loading: startingScan } = useStartScan();

  const latestScanRun = scanRuns?.scan_runs[0] ?? null;
  const scanRunId = latestScanRun?.id ?? "";

  const [activeFinding, setActiveFinding] = React.useState<FixPackResponse | null>(null);

  const handleStartScan = async () => {
    await startScan({ repo_id: repoId });
    await refetchScans();
  };

  return (
    <PageContainer>
      <PageHeader
        title="Repo Intelligence"
        description="Evidence-backed findings, fix packs, and operational risk context"
        actions={
          <Button variant="glow" onClick={handleStartScan} disabled={startingScan}>
            <PlayCircle className="h-4 w-4 mr-2" />
            {startingScan ? "Queueing..." : "Run Scan"}
          </Button>
        }
      />

      <Card className="mb-6">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-primary" />
              {repoData?.full_name || "Repository"}
            </CardTitle>
            <CardDescription>
              Commit {latestScanRun?.commit_sha || "pending"} • Branch {repoData?.default_branch || "main"}
            </CardDescription>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={latestScanRun?.status || "pending"} />
            <Badge variant="terminal">Scan {latestScanRun?.status || "not started"}</Badge>
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <InfoStat label="Last Run" value={latestScanRun?.created_at || "—"} />
          <InfoStat
            label="Coverage"
            value={
              typeof latestScanRun?.coverage_summary?.coverage_percentage === "number"
                ? `${latestScanRun.coverage_summary.coverage_percentage.toFixed(1)}%`
                : "—"
            }
          />
          <InfoStat label="Degraded Modes" value={latestScanRun?.coverage_summary?.degraded_modes?.join(", ") || "None"} />
        </CardContent>
      </Card>

      {!scanRunId ? (
        <Card>
          <CardHeader>
            <CardTitle>No scans yet</CardTitle>
            <CardDescription>Run a scan to generate evidence-backed findings.</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <RepoTabs
          scanRunId={scanRunId}
          scanRun={latestScanRun}
          onFixPackGenerated={setActiveFinding}
          activeFixPack={activeFinding}
        />
      )}
    </PageContainer>
  );
}

function RepoTabs({
  scanRunId,
  scanRun,
  onFixPackGenerated,
  activeFixPack,
}: {
  scanRunId: string;
  scanRun: { coverage_summary: { coverage_percentage: number | null } | null } | null;
  onFixPackGenerated: (fixPack: FixPackResponse) => void;
  activeFixPack: FixPackResponse | null;
}) {
  const { data: findingsData } = useFindings(scanRunId);
  const { data: controlResults } = useControlResults(scanRunId);
  const { data: promptTemplates } = usePromptTemplates();
  const { mutate: createFixPack, loading: creatingFixPack } = useCreateFixPack();

  const findings = findingsData?.findings ?? [];
  const safetyScore = computeSafetyScore(findings);
  const coveragePercentage = scanRun?.coverage_summary?.coverage_percentage ?? null;

  const handleFixPack = async (findingId: string) => {
    const result = await createFixPack({ scan_run_id: scanRunId, finding_ids: [findingId] });
    onFixPackGenerated(result);
  };

  return (
    <Tabs defaultValue="overview">
      <TabsList variant="underline" className="flex flex-wrap">
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="security">Security</TabsTrigger>
        <TabsTrigger value="privacy">Privacy</TabsTrigger>
        <TabsTrigger value="compliance">Compliance</TabsTrigger>
        <TabsTrigger value="reliability">Reliability</TabsTrigger>
        <TabsTrigger value="performance">Performance</TabsTrigger>
        <TabsTrigger value="maintainability">Maintainability</TabsTrigger>
        <TabsTrigger value="architecture">Architecture</TabsTrigger>
        <TabsTrigger value="prompt-studio">Prompt Studio</TabsTrigger>
      </TabsList>

      <TabsContent value="overview">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Gauge className="h-5 w-5 text-primary" />
                Safety Score
              </CardTitle>
              <CardDescription>Weighted severity score, explainable formula</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-4xl font-semibold">{safetyScore.score}</div>
              <p className="text-xs text-muted-foreground mt-2">
                Score = 100 - Σ(weight × findings). Weights: critical 20, high 12, medium 6, low 3, info 1.
              </p>
              <Progress value={safetyScore.score} className="mt-4" />
            </CardContent>
          </Card>
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ClipboardCheck className="h-5 w-5 text-primary" />
                Coverage
              </CardTitle>
              <CardDescription>What was scanned and what was skipped.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Coverage</span>
                <span className="text-sm font-medium">
                  {coveragePercentage !== null ? `${coveragePercentage.toFixed(1)}%` : "Loading"}
                </span>
              </div>
              <Progress value={coveragePercentage ?? 0} />
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Skipped reasons</p>
                  <p className="mt-1">See scan summary</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Degraded modes</p>
                  <p className="mt-1">See scan header</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-warning" />
                Top Risks
              </CardTitle>
              <CardDescription>Highest severity, deduped findings.</CardDescription>
            </CardHeader>
            <CardContent>
              <FindingsTable findings={findings.slice(0, 6)} onFixPack={handleFixPack} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldAlert className="h-5 w-5 text-critical" />
                Unknowns from Coverage Gaps
              </CardTitle>
              <CardDescription>Areas we could not confirm due to missing coverage.</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Check degraded modes and skipped files to identify unknowns. If coverage is low, expect more unknowns.
            </CardContent>
          </Card>
        </div>

        {activeFixPack && (
          <FixPackViewer fixPack={activeFixPack} creating={creatingFixPack} />
        )}
      </TabsContent>

      <TabsContent value="security">
        <CategoryPanel
          icon={ShieldAlert}
          title="Security Findings"
          description="SAST signals, secrets, and API security risks."
          findings={findings.filter((finding) => finding.category === "security")}
          onFixPack={handleFixPack}
        />
      </TabsContent>

      <TabsContent value="privacy">
        <CategoryPanel
          icon={DatabaseZap}
          title="Privacy Findings"
          description="Personal data signals and logging of sensitive data."
          findings={findings.filter((finding) => finding.category === "privacy")}
          onFixPack={handleFixPack}
        />
      </TabsContent>

      <TabsContent value="compliance">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ClipboardCheck className="h-5 w-5 text-primary" />
              Controls Checklist
            </CardTitle>
            <CardDescription>Pass / Fail / Unknown mapped to evidence.</CardDescription>
          </CardHeader>
          <CardContent>
            {controlResults?.controls?.length ? (
              <div className="space-y-3">
                {controlResults.controls.map((control) => (
                  <div key={control.id} className="flex items-center justify-between rounded-md border border-border p-3">
                    <div>
                      <p className="text-sm font-medium">{control.control_id}</p>
                      <p className="text-xs text-muted-foreground">{control.rationale || "No evidence available."}</p>
                    </div>
                    <Badge variant="outline">{control.status.toUpperCase()}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No control results available yet.</p>
            )}
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="reliability">
        <CategoryPanel
          icon={Activity}
          title="Reliability Findings"
          description="Timeouts, retries, idempotency, and failure handling."
          findings={findings.filter((finding) => finding.category === "reliability")}
          onFixPack={handleFixPack}
        />
      </TabsContent>

      <TabsContent value="performance">
        <CategoryPanel
          icon={Gauge}
          title="Performance Findings"
          description="Query, payload, and latency risks."
          findings={findings.filter((finding) => finding.category === "performance")}
          onFixPack={handleFixPack}
        />
      </TabsContent>

      <TabsContent value="maintainability">
        <CategoryPanel
          icon={Wrench}
          title="Maintainability Findings"
          description="Complexity hotspots and refactor opportunities."
          findings={findings.filter((finding) => finding.category === "maintainability")}
          onFixPack={handleFixPack}
        />
      </TabsContent>

      <TabsContent value="architecture">
        <CategoryPanel
          icon={Network}
          title="Architecture Findings"
          description="System boundaries and module coupling signals."
          findings={findings.filter((finding) => finding.category === "architecture")}
          onFixPack={handleFixPack}
        />
      </TabsContent>

      <TabsContent value="prompt-studio">
        <PromptStudioPanel templates={promptTemplates || []} />
      </TabsContent>
    </Tabs>
  );
}

function CategoryPanel({
  icon: Icon,
  title,
  description,
  findings,
  onFixPack,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  findings: Finding[];
  onFixPack: (findingId: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-primary" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <FindingsTable findings={findings} onFixPack={onFixPack} />
      </CardContent>
    </Card>
  );
}

function FindingsTable({
  findings,
  onFixPack,
}: {
  findings: Finding[];
  onFixPack: (findingId: string) => void;
}) {
  if (!findings.length) {
    return <p className="text-sm text-muted-foreground">No findings in this category.</p>;
  }

  return (
    <div className="space-y-3">
      {findings.map((finding) => (
        <div key={finding.id} className="flex items-start justify-between gap-4 border border-border rounded-lg p-3">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant={severityToBadge(finding.severity)} dot>
                {finding.severity.toUpperCase()}
              </Badge>
              <span className="text-sm font-medium">{finding.title}</span>
              <Badge variant="outline" size="sm">
                {finding.confidence.toUpperCase()}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-1">{finding.description}</p>
            <p className="text-xs text-muted-foreground mt-1">Instances: {finding.instance_count}</p>
          </div>
          <Button size="sm" variant="outline" onClick={() => onFixPack(finding.id)}>
            Fix Pack
          </Button>
        </div>
      ))}
    </div>
  );
}

function severityToBadge(severity: Finding["severity"]) {
  switch (severity) {
    case "critical":
    case "high":
      return "critical";
    case "medium":
      return "warning";
    case "low":
    case "info":
      return "info";
    default:
      return "outline";
  }
}

function FixPackViewer({ fixPack, creating }: { fixPack: FixPackResponse; creating: boolean }) {
  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          Fix Pack
        </CardTitle>
        <CardDescription>Copy-paste prompt and verification checklist.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-sm font-medium">Explanation</p>
          <p className="text-sm text-muted-foreground">{fixPack.human_explanation}</p>
        </div>
        <div>
          <p className="text-sm font-medium">Prompt Pack</p>
          <pre className="text-xs bg-muted/60 rounded-md p-3 overflow-auto whitespace-pre-wrap">
            {fixPack.prompt_pack.prompt}
          </pre>
        </div>
        <div>
          <p className="text-sm font-medium">Verification Checklist</p>
          <ul className="text-sm text-muted-foreground list-disc pl-5">
            {fixPack.verification_checklist.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        {creating && <p className="text-xs text-muted-foreground">Generating fix pack...</p>}
      </CardContent>
    </Card>
  );
}

function PromptStudioPanel({ templates }: { templates: PromptTemplate[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          Prompt Studio
        </CardTitle>
        <CardDescription>Start from structured templates with guardrails.</CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {templates.length ? (
          templates.map((template) => (
            <Card key={template.id} className="border border-border">
              <CardHeader>
                <CardTitle className="text-base">{template.title}</CardTitle>
                <CardDescription>{template.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="text-xs text-muted-foreground">Acceptance criteria</p>
                <ul className="text-xs text-muted-foreground list-disc pl-5">
                  {template.acceptance_criteria.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">No templates available.</p>
        )}
      </CardContent>
    </Card>
  );
}

function InfoStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border p-3">
      <p className="text-xs uppercase text-muted-foreground">{label}</p>
      <p className="text-sm font-medium mt-1">{value}</p>
    </div>
  );
}
