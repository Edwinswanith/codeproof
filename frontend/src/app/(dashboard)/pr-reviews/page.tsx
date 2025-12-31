"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  GitPullRequest,
  GitMerge,
  GitPullRequestClosed,
  Filter,
  ExternalLink,
  ChevronRight,
  Clock,
  FileCode2,
  ShieldAlert,
  AlertTriangle,
  Info,
  CheckCircle2,
  FolderGit2,
} from "lucide-react";
import { PageContainer, CardGrid } from "@/components/layout/dashboard-layout";
import { PageHeader } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SearchInput } from "@/components/ui/input";
import { Badge, SeverityBadge, StatusBadge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { FindingCard, type Finding, FindingList } from "@/components/finding-card";
import { cn, formatRelativeTime } from "@/lib/utils";

// Mock PR reviews data
const prReviews = [
  {
    id: "1",
    prNumber: 142,
    prTitle: "Add user profile endpoint",
    prUrl: "https://github.com/acme/laravel-app/pull/142",
    repo: { id: "1", name: "laravel-app", fullName: "acme/laravel-app" },
    headSha: "a1b2c3d",
    baseSha: "e5f6g7h",
    status: "completed" as const,
    filesChanged: 12,
    findingsCount: 3,
    criticalCount: 1,
    warningCount: 2,
    createdAt: new Date(Date.now() - 1000 * 60 * 60),
    findings: [
      {
        id: "f1",
        severity: "critical" as const,
        category: "secret_exposure",
        filePath: "config/services.php",
        startLine: 42,
        endLine: 45,
        evidence: {
          snippet: `'stripe' => [
    'key' => 'sk_live_51ABC123xyz789...',
    'secret' => env('STRIPE_SECRET'),
],`,
          pattern: "sk_live_[a-zA-Z0-9]{24,}",
          match: "sk_live_51ABC123xyz789...",
          reason: "Stripe Live API Key exposed in configuration file",
          confidence: "exact_match",
        },
        explanation: "A Stripe live API key was found hardcoded in the configuration. This key provides access to your Stripe account and should never be committed to version control.",
        suggestedFix: "Remove the hardcoded key and use environment variables: 'key' => env('STRIPE_KEY')",
        githubUrl: "https://github.com/acme/laravel-app/pull/142/files#diff-abc123",
        status: "open" as const,
      },
      {
        id: "f2",
        severity: "warning" as const,
        category: "auth_middleware_removed",
        filePath: "routes/api.php",
        startLine: 28,
        endLine: 35,
        evidence: {
          snippet: `Route::get('/users/{user}/profile', [UserController::class, 'profile']);
// Previously protected by auth:sanctum middleware`,
          reason: "Auth middleware removed from user profile endpoint",
          confidence: "structural",
        },
        explanation: "The auth:sanctum middleware was removed from this route, making the user profile publicly accessible.",
        status: "open" as const,
      },
      {
        id: "f3",
        severity: "warning" as const,
        category: "dependency_changed",
        filePath: "composer.lock",
        evidence: {
          snippet: `- laravel/sanctum: 3.3.0 -> 4.0.0
+ Major version update detected`,
          reason: "Major version bump in laravel/sanctum dependency",
          confidence: "exact_match",
        },
        explanation: "A major version update was detected. Major versions may include breaking changes that should be reviewed.",
        status: "open" as const,
      },
    ],
  },
  {
    id: "2",
    prNumber: 138,
    prTitle: "Database migration for orders table",
    prUrl: "https://github.com/acme/e-commerce-backend/pull/138",
    repo: { id: "2", name: "e-commerce-backend", fullName: "acme/e-commerce-backend" },
    headSha: "i9j0k1l",
    baseSha: "m2n3o4p",
    status: "completed" as const,
    filesChanged: 5,
    findingsCount: 1,
    criticalCount: 1,
    warningCount: 0,
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 3),
    findings: [
      {
        id: "f4",
        severity: "critical" as const,
        category: "migration_destructive",
        filePath: "database/migrations/2024_01_15_drop_users.php",
        startLine: 18,
        endLine: 22,
        evidence: {
          snippet: `public function up(): void
{
    Schema::dropColumn('orders', 'legacy_id');
    Schema::dropColumn('orders', 'old_status');
}`,
          pattern: "Schema::dropColumn",
          reason: "Destructive migration: dropping columns from orders table",
          confidence: "exact_match",
        },
        explanation: "This migration drops columns from an existing table. This is a destructive operation that cannot be easily reversed and may cause data loss.",
        suggestedFix: "Consider creating a backup of the data before running this migration, or use soft deletion if the data might be needed later.",
        status: "open" as const,
      },
    ],
  },
  {
    id: "3",
    prNumber: 87,
    prTitle: "Update user authentication flow",
    prUrl: "https://github.com/acme/laravel-api/pull/87",
    repo: { id: "3", name: "laravel-api", fullName: "acme/laravel-api" },
    headSha: "q5r6s7t",
    baseSha: "u8v9w0x",
    status: "completed" as const,
    filesChanged: 8,
    findingsCount: 0,
    criticalCount: 0,
    warningCount: 0,
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24),
    findings: [],
  },
  {
    id: "4",
    prNumber: 143,
    prTitle: "Add payment processing module",
    prUrl: "https://github.com/acme/laravel-app/pull/143",
    repo: { id: "1", name: "laravel-app", fullName: "acme/laravel-app" },
    headSha: "y1z2a3b",
    baseSha: "c4d5e6f",
    status: "analyzing" as const,
    filesChanged: 25,
    findingsCount: 0,
    criticalCount: 0,
    warningCount: 0,
    createdAt: new Date(Date.now() - 1000 * 60 * 5),
    findings: [],
  },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.05 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export default function PRReviewsPage() {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [selectedReview, setSelectedReview] = React.useState<typeof prReviews[0] | null>(null);
  const [statusFilter, setStatusFilter] = React.useState<string>("all");
  const [severityFilter, setSeverityFilter] = React.useState<string>("all");

  const filteredReviews = prReviews.filter((review) => {
    const matchesSearch =
      review.prTitle.toLowerCase().includes(searchQuery.toLowerCase()) ||
      `#${review.prNumber}`.includes(searchQuery) ||
      review.repo.name.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus =
      statusFilter === "all" || review.status === statusFilter;

    const matchesSeverity =
      severityFilter === "all" ||
      (severityFilter === "critical" && review.criticalCount > 0) ||
      (severityFilter === "warning" && review.warningCount > 0) ||
      (severityFilter === "clean" && review.findingsCount === 0);

    return matchesSearch && matchesStatus && matchesSeverity;
  });

  // Stats
  const stats = {
    total: prReviews.length,
    withFindings: prReviews.filter((r) => r.findingsCount > 0).length,
    critical: prReviews.reduce((sum, r) => sum + r.criticalCount, 0),
    warning: prReviews.reduce((sum, r) => sum + r.warningCount, 0),
  };

  return (
    <PageContainer>
      <PageHeader
        title="PR Reviews"
        description="Automated security analysis of pull requests"
      />

      {/* Stats */}
      <CardGrid columns={4}>
        <StatCard
          label="Total Reviews"
          value={stats.total}
          icon={GitPullRequest}
          iconColor="text-primary"
        />
        <StatCard
          label="With Findings"
          value={stats.withFindings}
          icon={AlertTriangle}
          iconColor="text-warning"
        />
        <StatCard
          label="Critical Issues"
          value={stats.critical}
          icon={ShieldAlert}
          iconColor="text-critical"
        />
        <StatCard
          label="Clean Merges"
          value={stats.total - stats.withFindings}
          icon={CheckCircle2}
          iconColor="text-success"
        />
      </CardGrid>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex-1 max-w-md">
          <SearchInput
            placeholder="Search PRs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onClear={() => setSearchQuery("")}
          />
        </div>
        <Tabs value={severityFilter} onValueChange={setSeverityFilter}>
          <TabsList variant="pills">
            <TabsTrigger value="all" variant="pills">All</TabsTrigger>
            <TabsTrigger value="critical" variant="pills">
              Critical ({stats.critical})
            </TabsTrigger>
            <TabsTrigger value="warning" variant="pills">
              Warnings
            </TabsTrigger>
            <TabsTrigger value="clean" variant="pills">
              Clean
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* PR Reviews Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* PR List */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="space-y-3"
        >
          {filteredReviews.map((review) => (
            <motion.div key={review.id} variants={itemVariants}>
              <PRReviewCard
                review={review}
                selected={selectedReview?.id === review.id}
                onSelect={() => setSelectedReview(review)}
              />
            </motion.div>
          ))}

          {filteredReviews.length === 0 && (
            <div className="text-center py-12">
              <GitPullRequest className="h-12 w-12 mx-auto text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-medium">No PR reviews found</h3>
              <p className="text-muted-foreground mt-1">
                Try adjusting your filters or search query
              </p>
            </div>
          )}
        </motion.div>

        {/* Findings Detail */}
        <div className="lg:sticky lg:top-6 lg:h-[calc(100vh-12rem)]">
          {selectedReview ? (
            <Card className="h-full overflow-hidden">
              <CardHeader className="border-b border-border">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge variant="terminal">#{selectedReview.prNumber}</Badge>
                      <StatusBadge status={selectedReview.status} />
                    </div>
                    <CardTitle className="mt-2">{selectedReview.prTitle}</CardTitle>
                    <div className="flex items-center gap-2 mt-2 text-sm text-muted-foreground">
                      <FolderGit2 className="h-4 w-4" />
                      {selectedReview.repo.fullName}
                    </div>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <a href={selectedReview.prUrl} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="h-4 w-4 mr-1.5" />
                      GitHub
                    </a>
                  </Button>
                </div>

                <div className="flex items-center gap-4 mt-4 text-sm">
                  <span className="flex items-center gap-1">
                    <FileCode2 className="h-4 w-4 text-muted-foreground" />
                    {selectedReview.filesChanged} files
                  </span>
                  {selectedReview.criticalCount > 0 && (
                    <span className="flex items-center gap-1 text-critical">
                      <ShieldAlert className="h-4 w-4" />
                      {selectedReview.criticalCount} critical
                    </span>
                  )}
                  {selectedReview.warningCount > 0 && (
                    <span className="flex items-center gap-1 text-warning">
                      <AlertTriangle className="h-4 w-4" />
                      {selectedReview.warningCount} warnings
                    </span>
                  )}
                </div>
              </CardHeader>
              <CardContent className="p-4 overflow-y-auto h-[calc(100%-200px)]">
                {selectedReview.findings.length > 0 ? (
                  <FindingList findings={selectedReview.findings} />
                ) : selectedReview.status === "analyzing" ? (
                  <div className="text-center py-12">
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                      className="w-12 h-12 mx-auto border-2 border-primary border-t-transparent rounded-full"
                    />
                    <p className="mt-4 text-muted-foreground">
                      Analyzing pull request...
                    </p>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <CheckCircle2 className="h-12 w-12 mx-auto text-success" />
                    <h3 className="mt-4 text-lg font-medium text-success">
                      No Issues Found
                    </h3>
                    <p className="text-muted-foreground mt-1">
                      This PR passed all security checks
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card className="h-full flex items-center justify-center">
              <div className="text-center p-8">
                <GitPullRequest className="h-12 w-12 mx-auto text-muted-foreground/50" />
                <h3 className="mt-4 text-lg font-medium">Select a PR Review</h3>
                <p className="text-muted-foreground mt-1">
                  Click on a PR review to see its findings
                </p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </PageContainer>
  );
}

// Stat Card
interface StatCardProps {
  label: string;
  value: number;
  icon: React.ElementType;
  iconColor?: string;
}

function StatCard({ label, value, icon: Icon, iconColor }: StatCardProps) {
  return (
    <Card>
      <CardContent className="p-4 flex items-center gap-4">
        <div className={cn("p-2 rounded-lg bg-muted", iconColor)}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-sm text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

// PR Review Card
interface PRReviewCardProps {
  review: typeof prReviews[0];
  selected?: boolean;
  onSelect: () => void;
}

function PRReviewCard({ review, selected, onSelect }: PRReviewCardProps) {
  const getStatusIcon = () => {
    switch (review.status) {
      case "completed":
        return review.findingsCount > 0 ? (
          <AlertTriangle className="h-5 w-5 text-warning" />
        ) : (
          <CheckCircle2 className="h-5 w-5 text-success" />
        );
      case "analyzing":
        return <GitPullRequest className="h-5 w-5 text-primary animate-pulse" />;
      default:
        return <GitPullRequest className="h-5 w-5 text-muted-foreground" />;
    }
  };

  return (
    <Card
      variant="interactive"
      className={cn(
        "cursor-pointer transition-all",
        selected && "border-primary ring-1 ring-primary"
      )}
      onClick={onSelect}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5">{getStatusIcon()}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <Badge variant="terminal" size="sm">#{review.prNumber}</Badge>
              <span className="text-xs text-muted-foreground font-mono">
                {review.repo.name}
              </span>
            </div>
            <p className="font-medium mt-1 truncate">{review.prTitle}</p>
            <div className="flex items-center gap-3 mt-2">
              <StatusBadge status={review.status} />
              {review.criticalCount > 0 && (
                <SeverityBadge severity="critical">{review.criticalCount}</SeverityBadge>
              )}
              {review.warningCount > 0 && (
                <SeverityBadge severity="warning">{review.warningCount}</SeverityBadge>
              )}
              {review.findingsCount === 0 && review.status === "completed" && (
                <Badge variant="success" size="sm">Clean</Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatRelativeTime(review.createdAt)}
            </p>
          </div>
          <ChevronRight className={cn(
            "h-5 w-5 text-muted-foreground transition-transform",
            selected && "rotate-90"
          )} />
        </div>
      </CardContent>
    </Card>
  );
}
