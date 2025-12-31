"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  MessageSquareText,
  GitPullRequest,
  FolderGit2,
  DollarSign,
  Calendar,
  Download,
} from "lucide-react";
import { PageContainer, CardGrid } from "@/components/layout/dashboard-layout";
import { PageHeader } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

// Mock usage data
const usageData = {
  currentPlan: "Pro",
  billingCycle: "Monthly",
  nextBillingDate: new Date(Date.now() + 1000 * 60 * 60 * 24 * 15),
  limits: {
    questions: { used: 847, limit: 1000 },
    prReviews: { used: 156, limit: 200 },
    repositories: { used: 12, limit: 20 },
  },
  costs: {
    totalThisMonth: 45.67,
    lastMonth: 42.30,
    breakdown: [
      { category: "Questions", amount: 28.50, tokens: 285000 },
      { category: "PR Reviews", amount: 12.45, tokens: 124500 },
      { category: "Indexing", amount: 4.72, tokens: 472000 },
    ],
  },
  dailyUsage: [
    { date: "Dec 24", questions: 45, reviews: 8 },
    { date: "Dec 25", questions: 12, reviews: 2 },
    { date: "Dec 26", questions: 56, reviews: 12 },
    { date: "Dec 27", questions: 78, reviews: 15 },
    { date: "Dec 28", questions: 92, reviews: 18 },
    { date: "Dec 29", questions: 67, reviews: 11 },
    { date: "Dec 30", questions: 84, reviews: 14 },
  ],
};

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export default function UsagePage() {
  const [period, setPeriod] = React.useState("month");

  const costChange = ((usageData.costs.totalThisMonth - usageData.costs.lastMonth) / usageData.costs.lastMonth) * 100;

  return (
    <PageContainer>
      <PageHeader
        title="Usage & Billing"
        description="Monitor your usage and manage billing"
        actions={
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            Export Report
          </Button>
        }
      />

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Plan Overview */}
        <motion.div variants={itemVariants}>
          <Card className="bg-gradient-to-r from-primary/5 via-accent/5 to-primary/5 border-primary/20">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge variant="default" className="text-sm px-3 py-1">
                      {usageData.currentPlan} Plan
                    </Badge>
                    <Badge variant="outline">{usageData.billingCycle}</Badge>
                  </div>
                  <p className="text-muted-foreground mt-2">
                    Next billing date: {usageData.nextBillingDate.toLocaleDateString("en-US", {
                      month: "long",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </p>
                </div>
                <Button variant="glow">Upgrade Plan</Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Usage Stats */}
        <motion.div variants={itemVariants}>
          <CardGrid columns={4}>
            <UsageCard
              title="Questions"
              icon={MessageSquareText}
              used={usageData.limits.questions.used}
              limit={usageData.limits.questions.limit}
              variant="default"
            />
            <UsageCard
              title="PR Reviews"
              icon={GitPullRequest}
              used={usageData.limits.prReviews.used}
              limit={usageData.limits.prReviews.limit}
              variant="warning"
            />
            <UsageCard
              title="Repositories"
              icon={FolderGit2}
              used={usageData.limits.repositories.used}
              limit={usageData.limits.repositories.limit}
              variant="success"
            />
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-accent/10 text-accent">
                    <DollarSign className="h-5 w-5" />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-muted-foreground">This Month</p>
                    <div className="flex items-center gap-2 mt-1">
                      <p className="text-2xl font-bold">
                        ${usageData.costs.totalThisMonth.toFixed(2)}
                      </p>
                      <span
                        className={cn(
                          "flex items-center gap-0.5 text-xs",
                          costChange > 0 ? "text-critical" : "text-success"
                        )}
                      >
                        {costChange > 0 ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : (
                          <TrendingDown className="h-3 w-3" />
                        )}
                        {Math.abs(costChange).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </CardGrid>
        </motion.div>

        {/* Charts and Breakdown */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Daily Usage Chart */}
          <motion.div variants={itemVariants}>
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <BarChart3 className="h-5 w-5 text-primary" />
                      Daily Usage
                    </CardTitle>
                    <CardDescription>Questions and PR reviews per day</CardDescription>
                  </div>
                  <Tabs value={period} onValueChange={setPeriod}>
                    <TabsList variant="pills">
                      <TabsTrigger value="week" variant="pills">Week</TabsTrigger>
                      <TabsTrigger value="month" variant="pills">Month</TabsTrigger>
                    </TabsList>
                  </Tabs>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {usageData.dailyUsage.map((day) => (
                    <div key={day.date} className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground w-16">{day.date}</span>
                        <div className="flex items-center gap-4 text-xs">
                          <span className="flex items-center gap-1">
                            <div className="w-2 h-2 rounded-full bg-primary" />
                            {day.questions}
                          </span>
                          <span className="flex items-center gap-1">
                            <div className="w-2 h-2 rounded-full bg-accent" />
                            {day.reviews}
                          </span>
                        </div>
                      </div>
                      <div className="flex gap-1 h-6">
                        <div
                          className="bg-primary/80 rounded-sm transition-all"
                          style={{ width: `${(day.questions / 100) * 100}%` }}
                        />
                        <div
                          className="bg-accent/80 rounded-sm transition-all"
                          style={{ width: `${(day.reviews / 20) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex items-center justify-center gap-6 mt-6 pt-4 border-t border-border">
                  <div className="flex items-center gap-2 text-sm">
                    <div className="w-3 h-3 rounded bg-primary" />
                    <span>Questions</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <div className="w-3 h-3 rounded bg-accent" />
                    <span>PR Reviews</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Cost Breakdown */}
          <motion.div variants={itemVariants}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5 text-accent" />
                  Cost Breakdown
                </CardTitle>
                <CardDescription>Estimated costs by category</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {usageData.costs.breakdown.map((item) => (
                    <div key={item.category} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{item.category}</span>
                        <span className="font-mono">${item.amount.toFixed(2)}</span>
                      </div>
                      <Progress
                        value={(item.amount / usageData.costs.totalThisMonth) * 100}
                        variant="default"
                      />
                      <p className="text-xs text-muted-foreground">
                        {item.tokens.toLocaleString()} tokens
                      </p>
                    </div>
                  ))}
                </div>

                <div className="mt-6 pt-4 border-t border-border">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">Total This Month</span>
                    <span className="text-xl font-bold">
                      ${usageData.costs.totalThisMonth.toFixed(2)}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Last month: ${usageData.costs.lastMonth.toFixed(2)}
                  </p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Billing History */}
        <motion.div variants={itemVariants}>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-muted-foreground" />
                Billing History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[
                  { date: "Dec 1, 2024", amount: 49.99, status: "Paid" },
                  { date: "Nov 1, 2024", amount: 42.30, status: "Paid" },
                  { date: "Oct 1, 2024", amount: 49.99, status: "Paid" },
                ].map((invoice, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 rounded-lg bg-muted/30"
                  >
                    <div>
                      <p className="font-medium">{invoice.date}</p>
                      <p className="text-sm text-muted-foreground">Pro Plan</p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono">${invoice.amount.toFixed(2)}</p>
                      <Badge variant="success" size="sm">{invoice.status}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </PageContainer>
  );
}

// Usage Card Component
interface UsageCardProps {
  title: string;
  icon: React.ElementType;
  used: number;
  limit: number;
  variant?: "default" | "success" | "warning" | "critical";
}

function UsageCard({ title, icon: Icon, used, limit, variant = "default" }: UsageCardProps) {
  const percentage = (used / limit) * 100;
  const progressVariant = percentage > 90 ? "critical" : percentage > 70 ? "warning" : variant;

  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className={cn("p-2 rounded-lg bg-muted")}>
            <Icon className="h-5 w-5" />
          </div>
          <span className="font-medium">{title}</span>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Used</span>
            <span className="font-mono">
              {used.toLocaleString()} / {limit.toLocaleString()}
            </span>
          </div>
          <Progress value={percentage} variant={progressVariant} />
          <p className="text-xs text-muted-foreground">
            {(limit - used).toLocaleString()} remaining
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
