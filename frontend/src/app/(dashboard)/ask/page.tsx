"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  MessageSquareText,
  Loader2,
  FolderGit2,
  ChevronDown,
  Sparkles,
  ThumbsUp,
  ThumbsDown,
  Copy,
  Check,
  FileCode2,
  Clock,
  AlertCircle,
} from "lucide-react";
import { PageContainer } from "@/components/layout/dashboard-layout";
import { PageHeader } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Badge, ConfidenceBadge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CodeBlock } from "@/components/code-block";
import { SourceCitation, CitationBadge, type Citation } from "@/components/source-citation";
import { cn } from "@/lib/utils";
import { useRepositories, useAskQuestion } from "@/lib/hooks";
import { AnswerResponse, Citation as ApiCitation } from "@/lib/api";

// Transform API citation to UI format
function transformCitation(citation: ApiCitation, id: string): Citation {
  return {
    id,
    sourceIndex: citation.source_index,
    filePath: citation.file_path,
    startLine: citation.start_line,
    endLine: citation.end_line,
    snippet: citation.snippet,
    symbolName: citation.symbol_name || undefined,
    retrievalSource: "both" as const,
  };
}

// Mock conversation
const mockAnswer = {
  id: "1",
  question: "How does the authentication middleware work in this project?",
  answerText: `The authentication in this project uses Laravel's built-in authentication with some custom middleware layers.

**Authentication Flow:**

1. **Session-based auth** is used for web routes, handled by the \`Authenticate\` middleware [1]

2. **API routes** use Sanctum for token-based authentication [2]

3. A custom \`EnsureUserIsActive\` middleware checks that the user's account is not suspended [3]

**Route Protection:**

Protected routes are defined in the \`web.php\` and \`api.php\` route files. The auth middleware is applied at the group level [4].

**Key Components:**
- \`App\\Http\\Middleware\\Authenticate\` - Main auth check
- \`App\\Http\\Middleware\\EnsureUserIsActive\` - Custom active user check
- \`App\\Providers\\AuthServiceProvider\` - Auth configuration`,
  confidenceTier: "high" as const,
  citations: [
    {
      id: "c1",
      sourceIndex: 1,
      filePath: "app/Http/Middleware/Authenticate.php",
      startLine: 1,
      endLine: 25,
      snippet: `<?php

namespace App\\Http\\Middleware;

use Illuminate\\Auth\\Middleware\\Authenticate as Middleware;
use Illuminate\\Http\\Request;

class Authenticate extends Middleware
{
    /**
     * Get the path the user should be redirected to.
     */
    protected function redirectTo(Request $request): ?string
    {
        return $request->expectsJson()
            ? null
            : route('login');
    }
}`,
      symbolName: "Authenticate",
      retrievalSource: "both" as const,
    },
    {
      id: "c2",
      sourceIndex: 2,
      filePath: "app/Http/Kernel.php",
      startLine: 45,
      endLine: 55,
      snippet: `    protected $middlewareGroups = [
        'api' => [
            \\Laravel\\Sanctum\\Http\\Middleware\\EnsureFrontendRequestsAreStateful::class,
            \\Illuminate\\Routing\\Middleware\\ThrottleRequests::class.':api',
            \\Illuminate\\Routing\\Middleware\\SubstituteBindings::class,
        ],
    ];`,
      symbolName: "$middlewareGroups",
      retrievalSource: "trigram" as const,
    },
    {
      id: "c3",
      sourceIndex: 3,
      filePath: "app/Http/Middleware/EnsureUserIsActive.php",
      startLine: 1,
      endLine: 30,
      snippet: `<?php

namespace App\\Http\\Middleware;

use Closure;
use Illuminate\\Http\\Request;
use Symfony\\Component\\HttpFoundation\\Response;

class EnsureUserIsActive
{
    public function handle(Request $request, Closure $next): Response
    {
        if ($request->user() && !$request->user()->is_active) {
            abort(403, 'Your account has been suspended.');
        }

        return $next($request);
    }
}`,
      symbolName: "EnsureUserIsActive",
      retrievalSource: "vector" as const,
    },
    {
      id: "c4",
      sourceIndex: 4,
      filePath: "routes/web.php",
      startLine: 18,
      endLine: 35,
      snippet: `Route::middleware(['auth', 'verified', 'active'])->group(function () {
    Route::get('/dashboard', [DashboardController::class, 'index'])
        ->name('dashboard');

    Route::resource('users', UserController::class);
    Route::resource('projects', ProjectController::class);

    Route::prefix('settings')->group(function () {
        Route::get('/', [SettingsController::class, 'index']);
        Route::post('/profile', [SettingsController::class, 'updateProfile']);
    });
});`,
      retrievalSource: "both" as const,
    },
  ] as Citation[],
  createdAt: new Date(),
};

const suggestedQuestions = [
  "What routes are protected by authentication?",
  "How are database migrations structured?",
  "What are the main models and their relationships?",
  "How does the payment processing work?",
  "What external APIs does this project integrate with?",
];

export default function AskPage() {
  // Fetch repositories from API
  const { data: apiRepos, loading: reposLoading } = useRepositories();
  const repositories = React.useMemo(() => {
    if (!apiRepos) return [];
    return apiRepos.map(repo => ({
      id: repo.id,
      name: repo.name,
      fullName: repo.full_name,
    }));
  }, [apiRepos]);

  const [selectedRepo, setSelectedRepo] = React.useState<{ id: string; name: string; fullName: string } | null>(null);
  const [question, setQuestion] = React.useState("");
  const [conversation, setConversation] = React.useState<{
    question: string;
    answerText: string;
    confidenceTier: "high" | "medium" | "low" | "none";
    citations: Citation[];
    unknowns: string[];
  } | null>(null);
  const [copied, setCopied] = React.useState(false);
  const [feedback, setFeedback] = React.useState<"up" | "down" | null>(null);

  // Q&A hook
  const { ask, loading: isLoading, error: askError } = useAskQuestion();

  // Set initial repo when repos load
  React.useEffect(() => {
    if (repositories.length > 0 && !selectedRepo) {
      setSelectedRepo(repositories[0]);
    }
  }, [repositories, selectedRepo]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading || !selectedRepo) return;

    const currentQuestion = question;
    setQuestion("");

    try {
      const response = await ask(selectedRepo.id, currentQuestion);
      setConversation({
        question: currentQuestion,
        answerText: response.answer_text,
        confidenceTier: response.confidence_tier,
        citations: response.citations.map((c, i) => transformCitation(c, `c${i}`)),
        unknowns: response.unknowns,
      });
      setFeedback(null);
    } catch (err) {
      // Error is handled by the hook
      console.error("Failed to get answer:", err);
    }
  };

  const handleSuggestedQuestion = (q: string) => {
    setQuestion(q);
  };

  const handleCopy = async () => {
    if (conversation) {
      await navigator.clipboard.writeText(conversation.answerText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Show loading if repos are loading
  if (reposLoading) {
    return (
      <PageContainer className="h-[calc(100vh-4rem)]">
        <div className="flex items-center justify-center h-full">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </PageContainer>
    );
  }

  // Show message if no repos
  if (repositories.length === 0) {
    return (
      <PageContainer className="h-[calc(100vh-4rem)]">
        <div className="flex flex-col items-center justify-center h-full">
          <FolderGit2 className="h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold">No Repositories</h2>
          <p className="text-muted-foreground mt-2">
            Connect a repository to start asking questions.
          </p>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer className="h-[calc(100vh-4rem)]">
      <div className="h-full flex flex-col">
        <PageHeader
          title="Ask Questions"
          description="Get answers about your codebase with hard evidence"
          actions={
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="gap-2">
                  <FolderGit2 className="h-4 w-4" />
                  {selectedRepo?.name || "Select repo"}
                  <ChevronDown className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {repositories.map((repo) => (
                  <DropdownMenuItem
                    key={repo.id}
                    onClick={() => setSelectedRepo(repo)}
                  >
                    <FolderGit2 className="h-4 w-4 mr-2" />
                    {repo.fullName}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          }
        />

        <div className="flex-1 flex gap-6 min-h-0 mt-6">
          {/* Main chat area */}
          <div className="flex-1 flex flex-col min-w-0">
            {/* Answer area */}
            <ScrollArea className="flex-1">
              <AnimatePresence mode="wait">
                {!conversation && !isLoading ? (
                  <motion.div
                    key="empty"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="h-full flex flex-col items-center justify-center py-12"
                  >
                    <div className="relative">
                      <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center">
                        <MessageSquareText className="h-10 w-10 text-primary" />
                      </div>
                      <Sparkles className="absolute -top-2 -right-2 h-6 w-6 text-accent" />
                    </div>
                    <h2 className="text-xl font-semibold mt-6">Ask about {selectedRepo?.name || "your codebase"}</h2>
                    <p className="text-muted-foreground mt-2 text-center max-w-md">
                      Ask questions about your codebase and get answers backed by evidence from the actual source code.
                    </p>

                    <div className="mt-8 space-y-2 w-full max-w-lg">
                      <p className="text-xs text-muted-foreground uppercase tracking-wider text-center">
                        Suggested questions
                      </p>
                      {suggestedQuestions.slice(0, 3).map((q, i) => (
                        <button
                          key={i}
                          onClick={() => handleSuggestedQuestion(q)}
                          className="w-full p-3 text-left text-sm rounded-lg border border-border hover:border-primary/50 hover:bg-muted/30 transition-colors"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                ) : isLoading ? (
                  <motion.div
                    key="loading"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="p-6"
                  >
                    <Card variant="terminal">
                      <CardContent className="p-6">
                        <div className="flex items-start gap-4">
                          <div className="p-2 rounded-lg bg-primary/10 text-primary">
                            <MessageSquareText className="h-5 w-5" />
                          </div>
                          <div className="flex-1">
                            <p className="font-medium">{question}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="mt-4 border-primary/20">
                      <CardContent className="p-6">
                        <div className="flex items-center gap-3">
                          <Loader2 className="h-5 w-5 animate-spin text-primary" />
                          <div>
                            <p className="font-medium">Analyzing codebase...</p>
                            <p className="text-sm text-muted-foreground">
                              Searching symbols, routes, and models
                            </p>
                          </div>
                        </div>
                        <div className="mt-4 space-y-2">
                          <LoadingStep label="Querying vector embeddings" done />
                          <LoadingStep label="Searching symbol index" done />
                          <LoadingStep label="Fetching code snippets" />
                          <LoadingStep label="Generating answer" />
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ) : conversation ? (
                  <motion.div
                    key="answer"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-6 space-y-4"
                  >
                    {/* Question */}
                    <Card variant="terminal">
                      <CardContent className="p-6">
                        <div className="flex items-start gap-4">
                          <div className="p-2 rounded-lg bg-primary/10 text-primary">
                            <MessageSquareText className="h-5 w-5" />
                          </div>
                          <div className="flex-1">
                            <p className="font-medium">{conversation.question}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Answer */}
                    <Card>
                      <CardContent className="p-6">
                        <div className="flex items-center justify-between mb-4">
                          <div className="flex items-center gap-2">
                            <Sparkles className="h-4 w-4 text-accent" />
                            <span className="text-sm font-medium">Answer</span>
                            <ConfidenceBadge tier={conversation.confidenceTier} />
                          </div>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              onClick={handleCopy}
                            >
                              {copied ? (
                                <Check className="h-4 w-4 text-success" />
                              ) : (
                                <Copy className="h-4 w-4" />
                              )}
                            </Button>
                            <Button
                              variant={feedback === "up" ? "default" : "ghost"}
                              size="icon-sm"
                              onClick={() => setFeedback("up")}
                            >
                              <ThumbsUp className="h-4 w-4" />
                            </Button>
                            <Button
                              variant={feedback === "down" ? "default" : "ghost"}
                              size="icon-sm"
                              onClick={() => setFeedback("down")}
                            >
                              <ThumbsDown className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>

                        <div className="prose prose-sm dark:prose-invert max-w-none">
                          <AnswerContent
                            text={conversation.answerText}
                            citations={conversation.citations}
                          />
                        </div>
                      </CardContent>
                    </Card>

                    {/* Sources */}
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                          <FileCode2 className="h-4 w-4" />
                          Sources ({conversation.citations.length})
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="pt-0">
                        <div className="space-y-3">
                          {conversation.citations.map((citation) => (
                            <SourceCitation
                              key={citation.id}
                              citation={citation}
                              variant="card"
                            />
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </ScrollArea>

            {/* Input area */}
            <div className="border-t border-border p-4 bg-card/50 backdrop-blur-sm">
              <form onSubmit={handleSubmit} className="flex gap-3">
                <Textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask a question about your codebase..."
                  className="min-h-[60px] resize-none"
                  variant="terminal"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit(e);
                    }
                  }}
                />
                <Button
                  type="submit"
                  variant="glow"
                  size="icon"
                  className="h-[60px] w-[60px]"
                  disabled={!question.trim() || isLoading}
                >
                  {isLoading ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Send className="h-5 w-5" />
                  )}
                </Button>
              </form>
              <p className="text-xs text-muted-foreground mt-2 text-center">
                Press Enter to send, Shift+Enter for new line
              </p>
            </div>
          </div>

          {/* Sidebar - Recent questions */}
          <div className="w-80 shrink-0 hidden xl:block">
            <Card className="h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Clock className="h-4 w-4" />
                  Recent Questions
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-3">
                  {[
                    { q: "How does the payment flow work?", time: "2h ago", confidence: "high" },
                    { q: "What middleware protects admin routes?", time: "5h ago", confidence: "high" },
                    { q: "Where is email sending configured?", time: "1d ago", confidence: "medium" },
                  ].map((item, i) => (
                    <button
                      key={i}
                      className="w-full text-left p-3 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/30 transition-colors"
                    >
                      <p className="text-sm font-medium truncate">{item.q}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-muted-foreground">{item.time}</span>
                        <Badge variant={item.confidence === "high" ? "success" : "warning"} size="sm">
                          {item.confidence}
                        </Badge>
                      </div>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </PageContainer>
  );
}

// Loading step indicator
function LoadingStep({ label, done }: { label: string; done?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {done ? (
        <Check className="h-4 w-4 text-success" />
      ) : (
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      )}
      <span className={done ? "text-muted-foreground" : "text-foreground"}>
        {label}
      </span>
    </div>
  );
}

// Answer content with inline citations
function AnswerContent({ text, citations }: { text: string; citations: Citation[] }) {
  // Parse text and replace [N] with clickable badges
  const parts = text.split(/(\[\d+\])/g);

  return (
    <div className="space-y-4">
      {text.split("\n\n").map((paragraph, pIndex) => (
        <p key={pIndex}>
          {paragraph.split(/(\[\d+\])/).map((part, i) => {
            const match = part.match(/\[(\d+)\]/);
            if (match) {
              const sourceIndex = parseInt(match[1]);
              const citation = citations.find((c) => c.sourceIndex === sourceIndex);
              if (citation) {
                return (
                  <SourceCitation key={i} citation={citation} variant="inline" />
                );
              }
            }
            // Handle markdown-style bold
            return part.split(/(\*\*[^*]+\*\*)/).map((segment, j) => {
              if (segment.startsWith("**") && segment.endsWith("**")) {
                return <strong key={`${i}-${j}`}>{segment.slice(2, -2)}</strong>;
              }
              // Handle inline code
              return segment.split(/(`[^`]+`)/).map((codePart, k) => {
                if (codePart.startsWith("`") && codePart.endsWith("`")) {
                  return (
                    <code key={`${i}-${j}-${k}`} className="px-1.5 py-0.5 bg-muted rounded text-sm font-mono">
                      {codePart.slice(1, -1)}
                    </code>
                  );
                }
                return codePart;
              });
            });
          })}
        </p>
      ))}
    </div>
  );
}
