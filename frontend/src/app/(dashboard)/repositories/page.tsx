"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  FolderGit2,
  Plus,
  Search,
  MoreVertical,
  ExternalLink,
  Trash2,
  RefreshCcw,
  GitBranch,
  FileCode2,
  Route,
  Database,
  Clock,
  Filter,
} from "lucide-react";
import { PageContainer, CardGrid } from "@/components/layout/dashboard-layout";
import { PageHeader } from "@/components/layout/header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SearchInput } from "@/components/ui/input";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn, formatRelativeTime } from "@/lib/utils";

type IndexStatus = "ready" | "indexing" | "failed" | "pending";

interface Repository {
  id: string;
  name: string;
  fullName: string;
  owner: string;
  private: boolean;
  defaultBranch: string;
  indexStatus: IndexStatus;
  lastIndexedAt: Date | null;
  lastIndexedCommit?: string;
  fileCount: number;
  symbolCount: number;
  routeCount: number;
  framework: string;
  indexProgress?: number;
  indexError?: string;
}

// Mock data
const repositories: Repository[] = [
  {
    id: "1",
    name: "laravel-app",
    fullName: "acme/laravel-app",
    owner: "acme",
    private: true,
    defaultBranch: "main",
    indexStatus: "ready" as const,
    lastIndexedAt: new Date(Date.now() - 1000 * 60 * 30),
    lastIndexedCommit: "a1b2c3d",
    fileCount: 342,
    symbolCount: 1847,
    routeCount: 86,
    framework: "Laravel 10",
  },
  {
    id: "2",
    name: "e-commerce-backend",
    fullName: "acme/e-commerce-backend",
    owner: "acme",
    private: true,
    defaultBranch: "main",
    indexStatus: "indexing" as const,
    lastIndexedAt: null,
    fileCount: 0,
    symbolCount: 0,
    routeCount: 0,
    framework: "Laravel 11",
    indexProgress: 65,
  },
  {
    id: "3",
    name: "laravel-api",
    fullName: "acme/laravel-api",
    owner: "acme",
    private: false,
    defaultBranch: "develop",
    indexStatus: "ready" as const,
    lastIndexedAt: new Date(Date.now() - 1000 * 60 * 60 * 2),
    lastIndexedCommit: "e5f6g7h",
    fileCount: 128,
    symbolCount: 634,
    routeCount: 45,
    framework: "Laravel 10",
  },
  {
    id: "4",
    name: "admin-panel",
    fullName: "acme/admin-panel",
    owner: "acme",
    private: true,
    defaultBranch: "main",
    indexStatus: "failed" as const,
    indexError: "Failed to clone repository: Permission denied",
    lastIndexedAt: null,
    fileCount: 0,
    symbolCount: 0,
    routeCount: 0,
    framework: "Laravel 10",
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

export default function RepositoriesPage() {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState<string | null>(null);

  const filteredRepos = repositories.filter((repo) => {
    const matchesSearch = repo.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      repo.fullName.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = !statusFilter || repo.indexStatus === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <PageContainer>
      <PageHeader
        title="Repositories"
        description="Manage your connected Laravel repositories"
        actions={
          <Button variant="glow" asChild>
            <Link href="/repositories/connect">
              <Plus className="h-4 w-4 mr-2" />
              Connect Repository
            </Link>
          </Button>
        }
      />

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex-1 max-w-md">
          <SearchInput
            placeholder="Search repositories..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onClear={() => setSearchQuery("")}
          />
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              <Filter className="h-4 w-4 mr-2" />
              {statusFilter ? statusFilter.charAt(0).toUpperCase() + statusFilter.slice(1) : "All Status"}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={() => setStatusFilter(null)}>
              All Status
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => setStatusFilter("ready")}>
              Ready
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setStatusFilter("indexing")}>
              Indexing
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setStatusFilter("failed")}>
              Failed
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Repository Grid */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        <CardGrid columns={2}>
          {filteredRepos.map((repo) => (
            <motion.div key={repo.id} variants={itemVariants}>
              <RepositoryCard repo={repo} />
            </motion.div>
          ))}
        </CardGrid>
      </motion.div>

      {filteredRepos.length === 0 && (
        <div className="text-center py-12">
          <FolderGit2 className="h-12 w-12 mx-auto text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-medium">No repositories found</h3>
          <p className="text-muted-foreground mt-1">
            {searchQuery ? "Try a different search term" : "Connect your first repository to get started"}
          </p>
          {!searchQuery && (
            <Button variant="glow" className="mt-4" asChild>
              <Link href="/repositories/connect">
                <Plus className="h-4 w-4 mr-2" />
                Connect Repository
              </Link>
            </Button>
          )}
        </div>
      )}
    </PageContainer>
  );
}

interface RepositoryCardProps {
  repo: Repository;
}

function RepositoryCard({ repo }: RepositoryCardProps) {
  return (
    <Card variant="interactive" className="group">
      <CardContent className="p-0">
        {/* Header */}
        <div className="p-4 border-b border-border">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10 text-primary">
                <FolderGit2 className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <Link
                    href={`/repositories/${repo.id}`}
                    className="font-semibold hover:text-primary transition-colors"
                  >
                    {repo.name}
                  </Link>
                  {repo.private ? (
                    <Badge variant="outline" size="sm">Private</Badge>
                  ) : (
                    <Badge variant="secondary" size="sm">Public</Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground font-mono">
                  {repo.fullName}
                </p>
              </div>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon-sm">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem>
                  <ExternalLink className="h-4 w-4 mr-2" />
                  View on GitHub
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <RefreshCcw className="h-4 w-4 mr-2" />
                  Re-index
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-destructive focus:text-destructive">
                  <Trash2 className="h-4 w-4 mr-2" />
                  Disconnect
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* Status */}
          <div className="flex items-center gap-2 mt-3">
            <StatusBadge status={repo.indexStatus} />
            <Badge variant="terminal" size="sm">
              {repo.framework}
            </Badge>
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <GitBranch className="h-3 w-3" />
              {repo.defaultBranch}
            </div>
          </div>
        </div>

        {/* Indexing Progress */}
        {repo.indexStatus === "indexing" && repo.indexProgress !== undefined && (
          <div className="px-4 py-3 bg-warning/5 border-b border-warning/20">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-warning font-medium">Indexing in progress...</span>
              <span className="text-muted-foreground">{repo.indexProgress}%</span>
            </div>
            <Progress value={repo.indexProgress} variant="warning" />
          </div>
        )}

        {/* Error */}
        {repo.indexStatus === "failed" && repo.indexError && (
          <div className="px-4 py-3 bg-critical/5 border-b border-critical/20">
            <p className="text-sm text-critical">{repo.indexError}</p>
            <Button variant="outline" size="sm" className="mt-2">
              <RefreshCcw className="h-3 w-3 mr-1.5" />
              Retry
            </Button>
          </div>
        )}

        {/* Stats */}
        {repo.indexStatus === "ready" && (
          <div className="p-4">
            <div className="grid grid-cols-3 gap-4">
              <StatItem icon={FileCode2} label="Files" value={repo.fileCount} />
              <StatItem icon={Database} label="Symbols" value={repo.symbolCount} />
              <StatItem icon={Route} label="Routes" value={repo.routeCount} />
            </div>
            {repo.lastIndexedAt && (
              <div className="flex items-center gap-1 mt-4 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                Last indexed {formatRelativeTime(repo.lastIndexedAt)}
                {repo.lastIndexedCommit && (
                  <code className="ml-1 text-primary">{repo.lastIndexedCommit}</code>
                )}
              </div>
            )}
          </div>
        )}

        {/* Pending state */}
        {repo.indexStatus === "pending" && (
          <div className="p-4 text-center text-muted-foreground">
            <p className="text-sm">Waiting to start indexing...</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface StatItemProps {
  icon: React.ElementType;
  label: string;
  value: number;
}

function StatItem({ icon: Icon, label, value }: StatItemProps) {
  return (
    <div className="text-center">
      <div className="flex items-center justify-center gap-1.5 text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-xs">{label}</span>
      </div>
      <p className="text-lg font-semibold mt-1">{value.toLocaleString()}</p>
    </div>
  );
}
