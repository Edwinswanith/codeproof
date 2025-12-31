"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  FolderGit2,
  MessageSquareText,
  GitPullRequest,
  AlertTriangle,
  TrendingUp,
  Clock,
  Zap,
  ArrowRight,
  FileCode2,
  ShieldAlert,
} from "lucide-react";
import { PageContainer, CardGrid } from "@/components/layout/dashboard-layout";
import { PageHeader } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, StatusBadge, SeverityBadge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: "easeOut" },
  },
};

export default function DashboardPage() {
  return (
    <PageContainer>
      <PageHeader
        title="Dashboard"
        description="Overview of your code intelligence metrics"
      />

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Stats Grid */}
        <motion.div variants={itemVariants}>
          <CardGrid columns={4}>
            <StatCard
              title="Repositories"
              value="12"
              change="+2 this month"
              icon={FolderGit2}
              iconColor="text-primary"
            />
            <StatCard
              title="Questions Asked"
              value="847"
              change="+124 this week"
              icon={MessageSquareText}
              iconColor="text-info"
            />
            <StatCard
              title="PR Reviews"
              value="156"
              change="+23 this week"
              icon={GitPullRequest}
              iconColor="text-success"
            />
            <StatCard
              title="Issues Found"
              value="34"
              change="5 critical"
              icon={AlertTriangle}
              iconColor="text-warning"
            />
          </CardGrid>
        </motion.div>

        {/* Main content grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent Activity */}
          <motion.div variants={itemVariants} className="lg:col-span-2">
            <Card variant="terminal">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Clock className="h-5 w-5 text-primary" />
                    Recent Activity
                  </CardTitle>
                  <CardDescription>Latest questions and reviews</CardDescription>
                </div>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/activity">
                    View All <ArrowRight className="h-4 w-4 ml-1" />
                  </Link>
                </Button>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <ActivityItem
                    type="question"
                    title="How does the authentication middleware work?"
                    repo="laravel-app"
                    time="5 minutes ago"
                    confidence="high"
                  />
                  <ActivityItem
                    type="pr_review"
                    title="PR #142: Add user profile endpoint"
                    repo="laravel-app"
                    time="1 hour ago"
                    findings={{ critical: 1, warning: 2 }}
                  />
                  <ActivityItem
                    type="question"
                    title="What routes are protected by the admin middleware?"
                    repo="laravel-api"
                    time="2 hours ago"
                    confidence="medium"
                  />
                  <ActivityItem
                    type="pr_review"
                    title="PR #87: Database migration for orders"
                    repo="e-commerce-backend"
                    time="3 hours ago"
                    findings={{ warning: 1 }}
                  />
                  <ActivityItem
                    type="question"
                    title="Where is the payment processing logic?"
                    repo="e-commerce-backend"
                    time="5 hours ago"
                    confidence="high"
                  />
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Quick Actions & Usage */}
          <motion.div variants={itemVariants} className="space-y-6">
            {/* Quick Actions */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-5 w-5 text-accent" />
                  Quick Actions
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Button variant="outline" className="w-full justify-start" asChild>
                  <Link href="/ask">
                    <MessageSquareText className="h-4 w-4 mr-2" />
                    Ask a Question
                  </Link>
                </Button>
                <Button variant="outline" className="w-full justify-start" asChild>
                  <Link href="/repositories/connect">
                    <FolderGit2 className="h-4 w-4 mr-2" />
                    Connect Repository
                  </Link>
                </Button>
                <Button variant="outline" className="w-full justify-start" asChild>
                  <Link href="/system-map">
                    <FileCode2 className="h-4 w-4 mr-2" />
                    View System Map
                  </Link>
                </Button>
              </CardContent>
            </Card>

            {/* Usage Stats */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-success" />
                  Monthly Usage
                </CardTitle>
                <CardDescription>Pro Plan</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <UsageItem
                  label="Questions"
                  used={847}
                  limit={1000}
                  variant="default"
                />
                <UsageItem
                  label="PR Reviews"
                  used={156}
                  limit={200}
                  variant="warning"
                />
                <UsageItem
                  label="Repositories"
                  used={12}
                  limit={20}
                  variant="success"
                />
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Recent Critical Findings */}
        <motion.div variants={itemVariants}>
          <Card variant="terminal">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <ShieldAlert className="h-5 w-5 text-critical" />
                  Critical Findings
                </CardTitle>
                <CardDescription>Issues requiring immediate attention</CardDescription>
              </div>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/pr-reviews?severity=critical">
                  View All <ArrowRight className="h-4 w-4 ml-1" />
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <CriticalFindingItem
                  category="secret_exposure"
                  file="config/services.php"
                  line={42}
                  pr="PR #142"
                  repo="laravel-app"
                />
                <CriticalFindingItem
                  category="migration_destructive"
                  file="database/migrations/2024_01_15_drop_users.php"
                  line={18}
                  pr="PR #138"
                  repo="e-commerce-backend"
                />
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </PageContainer>
  );
}

// Stat Card Component
interface StatCardProps {
  title: string;
  value: string;
  change: string;
  icon: React.ElementType;
  iconColor?: string;
}

function StatCard({ title, value, change, icon: Icon, iconColor }: StatCardProps) {
  return (
    <Card variant="interactive" className="group">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className={cn("p-2 rounded-lg bg-muted/50 group-hover:bg-primary/10 transition-colors", iconColor)}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-4">
          <p className="text-3xl font-bold tracking-tight">{value}</p>
          <p className="text-sm text-muted-foreground mt-1">{title}</p>
        </div>
        <p className="text-xs text-muted-foreground mt-2">{change}</p>
      </CardContent>
    </Card>
  );
}

// Activity Item Component
interface ActivityItemProps {
  type: "question" | "pr_review";
  title: string;
  repo: string;
  time: string;
  confidence?: "high" | "medium" | "low";
  findings?: { critical?: number; warning?: number };
}

function ActivityItem({ type, title, repo, time, confidence, findings }: ActivityItemProps) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg hover:bg-muted/30 transition-colors cursor-pointer group">
      <div className={cn(
        "p-2 rounded-lg shrink-0",
        type === "question" ? "bg-info/10 text-info" : "bg-success/10 text-success"
      )}>
        {type === "question" ? (
          <MessageSquareText className="h-4 w-4" />
        ) : (
          <GitPullRequest className="h-4 w-4" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
          {title}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <Badge variant="outline" size="sm" className="font-mono">
            {repo}
          </Badge>
          <span className="text-xs text-muted-foreground">{time}</span>
        </div>
      </div>
      <div className="shrink-0">
        {confidence && (
          <Badge
            variant={confidence === "high" ? "success" : confidence === "medium" ? "warning" : "critical"}
            size="sm"
          >
            {confidence}
          </Badge>
        )}
        {findings && (
          <div className="flex items-center gap-1">
            {findings.critical && (
              <Badge variant="critical" size="sm">{findings.critical}</Badge>
            )}
            {findings.warning && (
              <Badge variant="warning" size="sm">{findings.warning}</Badge>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Usage Item Component
interface UsageItemProps {
  label: string;
  used: number;
  limit: number;
  variant?: "default" | "success" | "warning" | "critical";
}

function UsageItem({ label, used, limit, variant = "default" }: UsageItemProps) {
  const percentage = (used / limit) * 100;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono">
          {used.toLocaleString()} / {limit.toLocaleString()}
        </span>
      </div>
      <Progress value={percentage} variant={variant} />
    </div>
  );
}

// Critical Finding Item
interface CriticalFindingItemProps {
  category: string;
  file: string;
  line: number;
  pr: string;
  repo: string;
}

function CriticalFindingItem({ category, file, line, pr, repo }: CriticalFindingItemProps) {
  const categoryLabels: Record<string, string> = {
    secret_exposure: "Secret Exposure",
    migration_destructive: "Destructive Migration",
    auth_middleware_removed: "Auth Middleware Removed",
  };

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-critical/5 border border-critical/20 hover:border-critical/40 transition-colors cursor-pointer">
      <div className="p-2 rounded-lg bg-critical/10 text-critical">
        <ShieldAlert className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <SeverityBadge severity="critical" />
          <span className="text-sm font-medium">
            {categoryLabels[category] || category}
          </span>
        </div>
        <p className="text-xs text-muted-foreground font-mono mt-1 truncate">
          {file}:{line}
        </p>
      </div>
      <div className="text-right shrink-0">
        <p className="text-sm font-medium">{pr}</p>
        <p className="text-xs text-muted-foreground">{repo}</p>
      </div>
    </div>
  );
}
