"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Map,
  Route,
  Database,
  Layers,
  GitBranch,
  Search,
  Filter,
  ChevronRight,
  ExternalLink,
  FolderGit2,
  ChevronDown,
  Shield,
  Lock,
  Globe,
  Workflow,
  FileCode2,
  Box,
} from "lucide-react";
import { PageContainer } from "@/components/layout/dashboard-layout";
import { PageHeader } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SearchInput } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

// Mock data for routes
const routes = [
  {
    id: "1",
    method: "GET",
    uri: "/api/users",
    fullUri: "/api/users",
    name: "users.index",
    controller: "UserController",
    action: "index",
    middleware: ["api", "auth:sanctum"],
    sourceFile: "routes/api.php",
    startLine: 15,
  },
  {
    id: "2",
    method: "POST",
    uri: "/api/users",
    fullUri: "/api/users",
    name: "users.store",
    controller: "UserController",
    action: "store",
    middleware: ["api", "auth:sanctum", "admin"],
    sourceFile: "routes/api.php",
    startLine: 16,
  },
  {
    id: "3",
    method: "GET",
    uri: "/api/users/{user}",
    fullUri: "/api/users/{user}",
    name: "users.show",
    controller: "UserController",
    action: "show",
    middleware: ["api", "auth:sanctum"],
    sourceFile: "routes/api.php",
    startLine: 17,
  },
  {
    id: "4",
    method: "GET",
    uri: "/dashboard",
    fullUri: "/dashboard",
    name: "dashboard",
    controller: "DashboardController",
    action: "index",
    middleware: ["web", "auth", "verified"],
    sourceFile: "routes/web.php",
    startLine: 12,
  },
  {
    id: "5",
    method: "GET",
    uri: "/login",
    fullUri: "/login",
    name: "login",
    controller: "Auth\\LoginController",
    action: "showLoginForm",
    middleware: ["web", "guest"],
    sourceFile: "routes/web.php",
    startLine: 8,
  },
  {
    id: "6",
    method: "POST",
    uri: "/login",
    fullUri: "/login",
    name: "login.submit",
    controller: "Auth\\LoginController",
    action: "login",
    middleware: ["web", "guest", "throttle:5,1"],
    sourceFile: "routes/web.php",
    startLine: 9,
  },
  {
    id: "7",
    method: "GET",
    uri: "/api/orders",
    fullUri: "/api/orders",
    name: "orders.index",
    controller: "OrderController",
    action: "index",
    middleware: ["api", "auth:sanctum"],
    sourceFile: "routes/api.php",
    startLine: 25,
  },
  {
    id: "8",
    method: "POST",
    uri: "/api/orders",
    fullUri: "/api/orders",
    name: "orders.store",
    controller: "OrderController",
    action: "store",
    middleware: ["api", "auth:sanctum"],
    sourceFile: "routes/api.php",
    startLine: 26,
  },
];

// Mock data for models
const models = [
  {
    id: "1",
    name: "User",
    filePath: "app/Models/User.php",
    tableName: "users",
    fillable: ["name", "email", "password"],
    relationships: [
      { type: "hasMany", related: "Order", method: "orders" },
      { type: "hasMany", related: "Post", method: "posts" },
      { type: "belongsToMany", related: "Role", method: "roles" },
    ],
  },
  {
    id: "2",
    name: "Order",
    filePath: "app/Models/Order.php",
    tableName: "orders",
    fillable: ["user_id", "status", "total", "shipped_at"],
    relationships: [
      { type: "belongsTo", related: "User", method: "user" },
      { type: "hasMany", related: "OrderItem", method: "items" },
      { type: "hasOne", related: "Payment", method: "payment" },
    ],
  },
  {
    id: "3",
    name: "Product",
    filePath: "app/Models/Product.php",
    tableName: "products",
    fillable: ["name", "description", "price", "stock"],
    relationships: [
      { type: "belongsToMany", related: "Category", method: "categories" },
      { type: "hasMany", related: "OrderItem", method: "orderItems" },
    ],
  },
  {
    id: "4",
    name: "Post",
    filePath: "app/Models/Post.php",
    tableName: "posts",
    fillable: ["user_id", "title", "content", "published_at"],
    relationships: [
      { type: "belongsTo", related: "User", method: "author" },
      { type: "hasMany", related: "Comment", method: "comments" },
      { type: "belongsToMany", related: "Tag", method: "tags" },
    ],
  },
];

// Mock middleware
const middlewareGroups = [
  {
    name: "web",
    middleware: [
      "EncryptCookies",
      "AddQueuedCookiesToResponse",
      "StartSession",
      "ShareErrorsFromSession",
      "VerifyCsrfToken",
      "SubstituteBindings",
    ],
  },
  {
    name: "api",
    middleware: [
      "EnsureFrontendRequestsAreStateful",
      "ThrottleRequests",
      "SubstituteBindings",
    ],
  },
];

const repositories = [
  { id: "1", name: "laravel-app", fullName: "acme/laravel-app" },
  { id: "2", name: "e-commerce-backend", fullName: "acme/e-commerce-backend" },
];

export default function SystemMapPage() {
  const [selectedRepo, setSelectedRepo] = React.useState(repositories[0]);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [activeTab, setActiveTab] = React.useState("routes");
  const [selectedItem, setSelectedItem] = React.useState<any>(null);

  // Filter routes
  const filteredRoutes = routes.filter(
    (route) =>
      route.uri.toLowerCase().includes(searchQuery.toLowerCase()) ||
      route.controller.toLowerCase().includes(searchQuery.toLowerCase()) ||
      route.name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Filter models
  const filteredModels = models.filter(
    (model) =>
      model.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      model.tableName.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group routes by controller
  const routesByController = filteredRoutes.reduce((acc, route) => {
    if (!acc[route.controller]) {
      acc[route.controller] = [];
    }
    acc[route.controller].push(route);
    return acc;
  }, {} as Record<string, typeof routes>);

  return (
    <PageContainer>
      <PageHeader
        title="System Map"
        description="Explore routes, models, and middleware in your codebase"
        actions={
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" className="gap-2">
                <FolderGit2 className="h-4 w-4" />
                {selectedRepo.name}
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

      <div className="flex items-center gap-4">
        <div className="flex-1 max-w-md">
          <SearchInput
            placeholder={`Search ${activeTab}...`}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onClear={() => setSearchQuery("")}
          />
        </div>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="routes" className="gap-2">
              <Route className="h-4 w-4" />
              Routes ({routes.length})
            </TabsTrigger>
            <TabsTrigger value="models" className="gap-2">
              <Database className="h-4 w-4" />
              Models ({models.length})
            </TabsTrigger>
            <TabsTrigger value="middleware" className="gap-2">
              <Shield className="h-4 w-4" />
              Middleware
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* List Panel */}
        <div className="lg:col-span-2">
          <AnimatePresence mode="wait">
            {activeTab === "routes" && (
              <motion.div
                key="routes"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-4"
              >
                {Object.entries(routesByController).map(([controller, controllerRoutes]) => (
                  <Card key={controller} variant="terminal">
                    <CardHeader className="py-3">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Box className="h-4 w-4 text-primary" />
                        <span className="font-mono">{controller}</span>
                        <Badge variant="secondary" size="sm">
                          {controllerRoutes.length} routes
                        </Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="space-y-1">
                        {controllerRoutes.map((route) => (
                          <RouteItem
                            key={route.id}
                            route={route}
                            selected={selectedItem?.id === route.id}
                            onSelect={() => setSelectedItem(route)}
                          />
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                ))}

                {Object.keys(routesByController).length === 0 && (
                  <EmptyState
                    icon={Route}
                    title="No routes found"
                    description="Try adjusting your search query"
                  />
                )}
              </motion.div>
            )}

            {activeTab === "models" && (
              <motion.div
                key="models"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="grid grid-cols-1 md:grid-cols-2 gap-4"
              >
                {filteredModels.map((model) => (
                  <ModelCard
                    key={model.id}
                    model={model}
                    selected={selectedItem?.id === model.id}
                    onSelect={() => setSelectedItem(model)}
                  />
                ))}

                {filteredModels.length === 0 && (
                  <div className="md:col-span-2">
                    <EmptyState
                      icon={Database}
                      title="No models found"
                      description="Try adjusting your search query"
                    />
                  </div>
                )}
              </motion.div>
            )}

            {activeTab === "middleware" && (
              <motion.div
                key="middleware"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-4"
              >
                {middlewareGroups.map((group) => (
                  <Card key={group.name} variant="terminal">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Shield className="h-5 w-5 text-primary" />
                        <span className="font-mono">{group.name}</span>
                        <Badge variant="terminal" size="sm">
                          {group.middleware.length} middleware
                        </Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="flex flex-wrap gap-2">
                        {group.middleware.map((mw, i) => (
                          <Badge key={i} variant="outline" className="font-mono">
                            {mw}
                          </Badge>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Detail Panel */}
        <div className="lg:sticky lg:top-6 lg:h-[calc(100vh-12rem)]">
          <Card className="h-full overflow-hidden">
            {selectedItem ? (
              <>
                <CardHeader className="border-b border-border">
                  <CardTitle className="flex items-center gap-2">
                    {activeTab === "routes" ? (
                      <>
                        <Route className="h-5 w-5 text-primary" />
                        Route Details
                      </>
                    ) : (
                      <>
                        <Database className="h-5 w-5 text-primary" />
                        Model Details
                      </>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 overflow-y-auto h-[calc(100%-80px)]">
                  {activeTab === "routes" && <RouteDetails route={selectedItem} />}
                  {activeTab === "models" && <ModelDetails model={selectedItem} />}
                </CardContent>
              </>
            ) : (
              <div className="h-full flex items-center justify-center p-8">
                <div className="text-center">
                  <Map className="h-12 w-12 mx-auto text-muted-foreground/50" />
                  <h3 className="mt-4 text-lg font-medium">Select an item</h3>
                  <p className="text-muted-foreground mt-1">
                    Click on a route or model to see details
                  </p>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}

// Route Item
interface RouteItemProps {
  route: typeof routes[0];
  selected?: boolean;
  onSelect: () => void;
}

function RouteItem({ route, selected, onSelect }: RouteItemProps) {
  const methodColors: Record<string, string> = {
    GET: "text-success bg-success/10",
    POST: "text-info bg-info/10",
    PUT: "text-warning bg-warning/10",
    PATCH: "text-warning bg-warning/10",
    DELETE: "text-critical bg-critical/10",
  };

  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full flex items-center gap-3 p-2 rounded-lg text-left transition-colors",
        selected
          ? "bg-primary/10 border border-primary/30"
          : "hover:bg-muted/50"
      )}
    >
      <Badge
        className={cn("font-mono text-xs w-16 justify-center", methodColors[route.method])}
      >
        {route.method}
      </Badge>
      <span className="font-mono text-sm flex-1 truncate">{route.uri}</span>
      {route.middleware.includes("auth") || route.middleware.includes("auth:sanctum") ? (
        <Lock className="h-3.5 w-3.5 text-muted-foreground" />
      ) : (
        <Globe className="h-3.5 w-3.5 text-muted-foreground" />
      )}
    </button>
  );
}

// Route Details
function RouteDetails({ route }: { route: typeof routes[0] }) {
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
          Endpoint
        </p>
        <div className="flex items-center gap-2">
          <Badge variant="terminal">{route.method}</Badge>
          <code className="text-sm font-mono">{route.fullUri}</code>
        </div>
      </div>

      {route.name && (
        <div>
          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
            Route Name
          </p>
          <code className="text-sm font-mono text-primary">{route.name}</code>
        </div>
      )}

      <div>
        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
          Handler
        </p>
        <code className="text-sm font-mono">
          {route.controller}@{route.action}
        </code>
      </div>

      <div>
        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
          Middleware
        </p>
        <div className="flex flex-wrap gap-1">
          {route.middleware.map((mw, i) => (
            <Badge key={i} variant="outline" size="sm" className="font-mono">
              {mw}
            </Badge>
          ))}
        </div>
      </div>

      <Separator />

      <div>
        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
          Source
        </p>
        <div className="flex items-center gap-2 text-sm">
          <FileCode2 className="h-4 w-4 text-muted-foreground" />
          <code className="font-mono">{route.sourceFile}:{route.startLine}</code>
        </div>
      </div>
    </div>
  );
}

// Model Card
interface ModelCardProps {
  model: typeof models[0];
  selected?: boolean;
  onSelect: () => void;
}

function ModelCard({ model, selected, onSelect }: ModelCardProps) {
  return (
    <Card
      variant="interactive"
      className={cn(
        "cursor-pointer",
        selected && "border-primary ring-1 ring-primary"
      )}
      onClick={onSelect}
    >
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <Database className="h-5 w-5" />
          </div>
          <div>
            <p className="font-semibold">{model.name}</p>
            <p className="text-xs text-muted-foreground font-mono">
              {model.tableName}
            </p>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
          <Workflow className="h-3.5 w-3.5" />
          {model.relationships.length} relationships
        </div>
      </CardContent>
    </Card>
  );
}

// Model Details
function ModelDetails({ model }: { model: typeof models[0] }) {
  const relationshipIcons: Record<string, React.ElementType> = {
    hasMany: Layers,
    hasOne: GitBranch,
    belongsTo: GitBranch,
    belongsToMany: Layers,
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
          Model
        </p>
        <p className="font-semibold text-lg">{model.name}</p>
      </div>

      <div>
        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
          Table
        </p>
        <code className="text-sm font-mono text-primary">{model.tableName}</code>
      </div>

      <div>
        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
          Fillable Fields
        </p>
        <div className="flex flex-wrap gap-1">
          {model.fillable.map((field) => (
            <Badge key={field} variant="outline" size="sm" className="font-mono">
              {field}
            </Badge>
          ))}
        </div>
      </div>

      <Separator />

      <div>
        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
          Relationships
        </p>
        <div className="space-y-2">
          {model.relationships.map((rel, i) => {
            const Icon = relationshipIcons[rel.type] || Workflow;
            return (
              <div
                key={i}
                className="flex items-center gap-2 p-2 rounded-lg bg-muted/30"
              >
                <Icon className="h-4 w-4 text-primary" />
                <span className="text-sm font-mono">{rel.method}()</span>
                <ChevronRight className="h-3 w-3 text-muted-foreground" />
                <Badge variant="terminal" size="sm">{rel.related}</Badge>
                <Badge variant="outline" size="sm" className="ml-auto">
                  {rel.type}
                </Badge>
              </div>
            );
          })}
        </div>
      </div>

      <Separator />

      <div>
        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
          Source
        </p>
        <div className="flex items-center gap-2 text-sm">
          <FileCode2 className="h-4 w-4 text-muted-foreground" />
          <code className="font-mono">{model.filePath}</code>
        </div>
      </div>
    </div>
  );
}

// Empty State
function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
}) {
  return (
    <div className="text-center py-12">
      <Icon className="h-12 w-12 mx-auto text-muted-foreground/50" />
      <h3 className="mt-4 text-lg font-medium">{title}</h3>
      <p className="text-muted-foreground mt-1">{description}</p>
    </div>
  );
}
