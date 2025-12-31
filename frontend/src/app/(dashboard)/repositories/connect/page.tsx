"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Github,
  FolderGit2,
  Lock,
  Globe,
  Search,
  Check,
  ArrowLeft,
  Loader2,
  AlertCircle,
  Star,
  GitFork,
} from "lucide-react";
import { PageContainer } from "@/components/layout/dashboard-layout";
import { PageHeader } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SearchInput } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn, formatRelativeTime } from "@/lib/utils";

// Mock available repositories from GitHub
const availableRepos = [
  {
    id: "1",
    name: "new-laravel-project",
    fullName: "acme/new-laravel-project",
    private: true,
    description: "A new Laravel 11 project with modern architecture",
    language: "PHP",
    stars: 0,
    forks: 0,
    updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 2),
  },
  {
    id: "2",
    name: "api-gateway",
    fullName: "acme/api-gateway",
    private: true,
    description: "API Gateway service built with Laravel Octane",
    language: "PHP",
    stars: 12,
    forks: 3,
    updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 24),
  },
  {
    id: "3",
    name: "customer-portal",
    fullName: "acme/customer-portal",
    private: false,
    description: "Customer self-service portal",
    language: "PHP",
    stars: 45,
    forks: 8,
    updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 48),
  },
  {
    id: "4",
    name: "internal-tools",
    fullName: "acme/internal-tools",
    private: true,
    description: "Internal developer tools and utilities",
    language: "PHP",
    stars: 5,
    forks: 1,
    updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 72),
  },
];

export default function ConnectRepositoryPage() {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [selectedRepos, setSelectedRepos] = React.useState<string[]>([]);
  const [isConnecting, setIsConnecting] = React.useState(false);
  const [step, setStep] = React.useState<"select" | "connecting" | "success">("select");

  const filteredRepos = availableRepos.filter((repo) =>
    repo.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    repo.fullName.toLowerCase().includes(searchQuery.toLowerCase()) ||
    repo.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleRepo = (id: string) => {
    setSelectedRepos((prev) =>
      prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id]
    );
  };

  const handleConnect = async () => {
    setIsConnecting(true);
    setStep("connecting");
    // Simulate connection
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setStep("success");
  };

  if (step === "success") {
    return (
      <PageContainer>
        <div className="max-w-lg mx-auto text-center py-12">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200, damping: 15 }}
            className="w-20 h-20 mx-auto bg-success/10 rounded-full flex items-center justify-center"
          >
            <Check className="h-10 w-10 text-success" />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <h2 className="text-2xl font-bold mt-6">Repositories Connected!</h2>
            <p className="text-muted-foreground mt-2">
              {selectedRepos.length} repositories are now being indexed. This usually takes a few minutes.
            </p>
            <div className="flex items-center justify-center gap-3 mt-6">
              <Button variant="outline" asChild>
                <Link href="/repositories">View Repositories</Link>
              </Button>
              <Button variant="glow" asChild>
                <Link href="/ask">Start Asking Questions</Link>
              </Button>
            </div>
          </motion.div>
        </div>
      </PageContainer>
    );
  }

  if (step === "connecting") {
    return (
      <PageContainer>
        <div className="max-w-lg mx-auto text-center py-12">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            className="w-20 h-20 mx-auto bg-primary/10 rounded-full flex items-center justify-center"
          >
            <Loader2 className="h-10 w-10 text-primary" />
          </motion.div>
          <h2 className="text-2xl font-bold mt-6">Connecting Repositories...</h2>
          <p className="text-muted-foreground mt-2">
            Setting up GitHub integration and starting initial indexing.
          </p>
          <div className="mt-8 space-y-3">
            {selectedRepos.map((id, index) => {
              const repo = availableRepos.find((r) => r.id === id);
              return (
                <motion.div
                  key={id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className="flex items-center gap-3 p-3 bg-card rounded-lg border border-border"
                >
                  <FolderGit2 className="h-5 w-5 text-primary" />
                  <span className="font-mono text-sm">{repo?.fullName}</span>
                  <Loader2 className="h-4 w-4 ml-auto animate-spin text-muted-foreground" />
                </motion.div>
              );
            })}
          </div>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageHeader
        breadcrumbs={[
          { label: "Repositories", href: "/repositories" },
          { label: "Connect" },
        ]}
        title="Connect Repository"
        description="Select Laravel repositories to connect and index"
        actions={
          <Button variant="ghost" asChild>
            <Link href="/repositories">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Link>
          </Button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Repository Selection */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-muted">
                  <Github className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle>GitHub Repositories</CardTitle>
                  <CardDescription>
                    Select repositories from your GitHub account
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <SearchInput
                placeholder="Search repositories..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onClear={() => setSearchQuery("")}
              />

              <div className="space-y-2">
                {filteredRepos.map((repo) => (
                  <RepoSelectionItem
                    key={repo.id}
                    repo={repo}
                    selected={selectedRepos.includes(repo.id)}
                    onSelect={() => toggleRepo(repo.id)}
                  />
                ))}
              </div>

              {filteredRepos.length === 0 && (
                <div className="text-center py-8 text-muted-foreground">
                  <Search className="h-8 w-8 mx-auto opacity-50" />
                  <p className="mt-2">No repositories found matching your search</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Selected repos */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Selected Repositories</CardTitle>
            </CardHeader>
            <CardContent>
              {selectedRepos.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No repositories selected. Click on a repository to select it.
                </p>
              ) : (
                <div className="space-y-2">
                  {selectedRepos.map((id) => {
                    const repo = availableRepos.find((r) => r.id === id);
                    return (
                      <div
                        key={id}
                        className="flex items-center gap-2 p-2 bg-muted/50 rounded-md"
                      >
                        <FolderGit2 className="h-4 w-4 text-primary" />
                        <span className="text-sm font-mono flex-1 truncate">
                          {repo?.name}
                        </span>
                        <button
                          onClick={() => toggleRepo(id)}
                          className="text-muted-foreground hover:text-foreground"
                        >
                          <Check className="h-4 w-4" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              <Separator className="my-4" />

              <Button
                variant="glow"
                className="w-full"
                disabled={selectedRepos.length === 0 || isConnecting}
                onClick={handleConnect}
              >
                {isConnecting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    Connect {selectedRepos.length > 0 && `(${selectedRepos.length})`}
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Info */}
          <Card className="bg-info/5 border-info/20">
            <CardContent className="pt-6">
              <div className="flex gap-3">
                <AlertCircle className="h-5 w-5 text-info shrink-0" />
                <div className="text-sm">
                  <p className="font-medium text-info">Laravel Projects Only</p>
                  <p className="text-muted-foreground mt-1">
                    CodeProof is optimized for Laravel projects. Other PHP frameworks may have limited support.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}

interface RepoSelectionItemProps {
  repo: typeof availableRepos[0];
  selected: boolean;
  onSelect: () => void;
}

function RepoSelectionItem({ repo, selected, onSelect }: RepoSelectionItemProps) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full flex items-start gap-3 p-4 rounded-lg border text-left transition-all",
        selected
          ? "border-primary bg-primary/5 ring-1 ring-primary"
          : "border-border hover:border-primary/50 hover:bg-muted/30"
      )}
    >
      <div className={cn(
        "mt-0.5 w-5 h-5 rounded border flex items-center justify-center shrink-0 transition-colors",
        selected
          ? "bg-primary border-primary text-primary-foreground"
          : "border-border"
      )}>
        {selected && <Check className="h-3 w-3" />}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium">{repo.name}</span>
          {repo.private ? (
            <Lock className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <Globe className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </div>
        <p className="text-sm text-muted-foreground font-mono">{repo.fullName}</p>
        {repo.description && (
          <p className="text-sm text-muted-foreground mt-1 truncate">{repo.description}</p>
        )}
        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
          <Badge variant="terminal" size="sm">{repo.language}</Badge>
          <span className="flex items-center gap-1">
            <Star className="h-3 w-3" />
            {repo.stars}
          </span>
          <span className="flex items-center gap-1">
            <GitFork className="h-3 w-3" />
            {repo.forks}
          </span>
          <span>Updated {formatRelativeTime(repo.updatedAt)}</span>
        </div>
      </div>
    </button>
  );
}
