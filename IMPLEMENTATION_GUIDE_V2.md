# IMPLEMENTATION GUIDE V2: Laravel-First Code Intelligence

## Promise
"Ask questions about your Laravel repo and get answers with hard evidence. Generate accurate system maps and catch risky PR changes."

---

# CRITICAL FIXES FROM V1

| Issue | V1 (Wrong) | V2 (Fixed) |
|-------|------------|------------|
| File storage | `files.content TEXT` | Metadata only, snippets on-demand |
| Search | `to_tsvector('english')` | Trigram + simple token matching |
| Route parsing | Regex | AST-based tree-sitter |
| Answer validation | "Please cite sources" | Structured JSON + validation |
| Confidence | Fake percentage | Discrete tiers (HIGH/MEDIUM/LOW) |
| Git auth | Token in URL | Auth header |
| Analyzers | 15+ patterns | 6 high-precision only |
| Cost tracking | Fantasy numbers | Metered from day 1 |

---

# 1. REVISED ARCHITECTURE

## 1.1 Trust Model

```
DETECTION LAYER (Deterministic - Source of Truth)
├── tree-sitter AST parsing
├── Exact-match patterns (GitHub PAT, AWS keys, etc.)
├── Structural analysis (route groups, middleware chains)
└── Migration operation detection

RETRIEVAL LAYER (Hybrid Search)
├── Trigram matching on symbols/paths
├── Vector similarity on embeddings
└── Merge + deduplicate

EXPLANATION LAYER (LLM - Constrained)
├── Must output structured JSON
├── Every claim must reference source_id
├── Validated before returning to user
└── Falls back to "insufficient evidence" on validation failure

RULE: LLM never detects. LLM never invents file paths or line numbers.
```

## 1.2 Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER REQUEST                             │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RETRIEVAL (Deterministic)                   │
│  1. Trigram search on symbols.name, symbols.qualified_name       │
│  2. Vector search on Qdrant embeddings                           │
│  3. Merge results, deduplicate by file:line                      │
│  4. Fetch actual snippets from GitHub API (cached)               │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LLM GENERATION (Constrained)                │
│  1. Build prompt with numbered sources                           │
│  2. Require JSON output with source_ids per section              │
│  3. Validate: every source_id exists, every section has sources  │
│  4. If validation fails: retry once, then return insufficient    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RESPONSE (Evidence-Backed)                  │
│  - Answer text                                                   │
│  - Citations with file_path, line_range, snippet, github_url     │
│  - Confidence tier: HIGH / MEDIUM / LOW                          │
│  - Unknowns: what couldn't be answered                           │
└─────────────────────────────────────────────────────────────────┘
```

---

# 2. REVISED DATABASE SCHEMA

```sql
-- ===========================================
-- EXTENSIONS
-- ===========================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===========================================
-- USERS
-- ===========================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    github_id BIGINT UNIQUE NOT NULL,
    github_login VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    avatar_url VARCHAR(500),
    
    plan VARCHAR(20) DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'team')),
    stripe_customer_id VARCHAR(255),
    
    questions_used_this_month INTEGER DEFAULT 0,
    pr_reviews_used_this_month INTEGER DEFAULT 0,
    usage_reset_at TIMESTAMP DEFAULT NOW(),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ===========================================
-- REPOSITORIES (no file content storage)
-- ===========================================
CREATE TABLE repositories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    github_repo_id BIGINT NOT NULL,
    github_installation_id BIGINT NOT NULL,
    owner VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    default_branch VARCHAR(100) DEFAULT 'main',
    private BOOLEAN DEFAULT true,
    
    detected_framework VARCHAR(50) DEFAULT 'laravel',
    framework_version VARCHAR(20),
    
    index_status VARCHAR(20) DEFAULT 'pending' 
        CHECK (index_status IN ('pending', 'cloning', 'indexing', 'ready', 'failed')),
    index_error TEXT,
    last_indexed_at TIMESTAMP,
    last_indexed_commit VARCHAR(40),
    
    file_count INTEGER DEFAULT 0,
    symbol_count INTEGER DEFAULT 0,
    route_count INTEGER DEFAULT 0,
    
    -- Soft delete for compliance
    deleted_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, github_repo_id)
);

CREATE INDEX idx_repos_user ON repositories(user_id) WHERE deleted_at IS NULL;

-- ===========================================
-- FILES (metadata only, NO content)
-- ===========================================
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    
    path VARCHAR(1000) NOT NULL,
    sha VARCHAR(40) NOT NULL,  -- Git blob SHA for cache validation
    language VARCHAR(50),
    size_bytes INTEGER,
    
    last_indexed_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(repo_id, path)
);

CREATE INDEX idx_files_repo ON files(repo_id);
CREATE INDEX idx_files_path_trgm ON files USING GIN (path gin_trgm_ops);

-- ===========================================
-- SYMBOLS (extracted code entities)
-- ===========================================
CREATE TABLE symbols (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    file_id UUID REFERENCES files(id) ON DELETE CASCADE,
    
    name VARCHAR(255) NOT NULL,
    qualified_name VARCHAR(500),
    kind VARCHAR(50) NOT NULL CHECK (kind IN (
        'class', 'trait', 'interface', 'function', 'method', 'constant'
    )),
    
    file_path VARCHAR(1000) NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    
    signature TEXT,
    docstring TEXT,
    
    parent_symbol_id UUID REFERENCES symbols(id),
    visibility VARCHAR(20),
    is_static BOOLEAN DEFAULT false,
    
    -- Searchable text (name + signature + docstring combined)
    search_text TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_symbols_repo ON symbols(repo_id);
CREATE INDEX idx_symbols_file ON symbols(file_id);
CREATE INDEX idx_symbols_kind ON symbols(repo_id, kind);

-- Trigram indexes for fuzzy search
CREATE INDEX idx_symbols_name_trgm ON symbols USING GIN (name gin_trgm_ops);
CREATE INDEX idx_symbols_qualified_trgm ON symbols USING GIN (qualified_name gin_trgm_ops);

-- Simple config FTS (no stemming)
CREATE INDEX idx_symbols_search ON symbols 
    USING GIN (to_tsvector('simple', COALESCE(search_text, '')));

-- ===========================================
-- ROUTES (Laravel - AST extracted)
-- ===========================================
CREATE TABLE routes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    
    -- Route definition
    method VARCHAR(10) NOT NULL,
    uri VARCHAR(500) NOT NULL,
    full_uri VARCHAR(500) NOT NULL,  -- With prefix applied
    name VARCHAR(255),
    
    -- Handler
    controller VARCHAR(255),
    action VARCHAR(255),
    handler_type VARCHAR(20) CHECK (handler_type IN ('controller', 'closure', 'invokable')),
    
    -- Middleware chain (in order)
    middleware JSONB DEFAULT '[]',
    
    -- Group context
    group_prefix VARCHAR(255),
    group_middleware JSONB DEFAULT '[]',
    
    -- Source location
    source_file VARCHAR(1000) NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER,
    
    -- Linked entities
    controller_symbol_id UUID REFERENCES symbols(id),
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_routes_repo ON routes(repo_id);
CREATE INDEX idx_routes_uri ON routes(repo_id, full_uri);
CREATE INDEX idx_routes_controller ON routes(repo_id, controller);

-- ===========================================
-- MIGRATIONS (Laravel)
-- ===========================================
CREATE TABLE migrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    
    file_path VARCHAR(1000) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    migration_order INTEGER,  -- Derived from filename timestamp
    
    table_name VARCHAR(255),
    operation VARCHAR(20) CHECK (operation IN ('create', 'alter', 'drop', 'rename')),
    
    columns JSONB DEFAULT '[]',
    indexes JSONB DEFAULT '[]',
    foreign_keys JSONB DEFAULT '[]',
    
    is_destructive BOOLEAN DEFAULT false,
    destructive_operations JSONB DEFAULT '[]',  -- List of what's destructive
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_migrations_repo ON migrations(repo_id);
CREATE INDEX idx_migrations_table ON migrations(repo_id, table_name);

-- ===========================================
-- MODELS (Laravel Eloquent)
-- ===========================================
CREATE TABLE models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    symbol_id UUID REFERENCES symbols(id),
    
    name VARCHAR(255) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    
    table_name VARCHAR(255),
    
    fillable JSONB DEFAULT '[]',
    guarded JSONB DEFAULT '[]',
    casts JSONB DEFAULT '{}',
    relationships JSONB DEFAULT '[]',
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_models_repo ON models(repo_id);

-- ===========================================
-- ANSWERS (with structured validation)
-- ===========================================
CREATE TABLE answers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    
    question TEXT NOT NULL,
    
    -- Structured answer
    answer_text TEXT,
    answer_sections JSONB,  -- [{text, source_ids}]
    unknowns JSONB DEFAULT '[]',  -- What couldn't be answered
    
    -- Confidence (discrete tier, not fake percentage)
    confidence_tier VARCHAR(10) CHECK (confidence_tier IN ('high', 'medium', 'low', 'none')),
    confidence_factors JSONB,  -- {citation_count, file_count, has_entrypoints, etc}
    
    -- Validation
    validation_passed BOOLEAN DEFAULT true,
    validation_errors JSONB DEFAULT '[]',
    
    -- Metadata
    retrieval_stats JSONB,
    llm_model VARCHAR(50),
    input_tokens INTEGER,
    output_tokens INTEGER,
    
    -- Feedback
    feedback VARCHAR(10) CHECK (feedback IN ('up', 'down')),
    feedback_comment TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_answers_repo ON answers(repo_id);
CREATE INDEX idx_answers_user ON answers(user_id);

-- ===========================================
-- CITATIONS (deduplicated)
-- ===========================================
CREATE TABLE citations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    answer_id UUID REFERENCES answers(id) ON DELETE CASCADE,
    
    source_index INTEGER NOT NULL,  -- The [Source N] number
    
    file_path VARCHAR(1000) NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    
    -- Limited snippet (max 500 chars, fetched from GitHub)
    snippet VARCHAR(500) NOT NULL,
    snippet_sha VARCHAR(40),  -- To validate freshness
    
    symbol_id UUID REFERENCES symbols(id),
    symbol_name VARCHAR(255),
    
    relevance_score FLOAT,
    retrieval_source VARCHAR(20),  -- 'trigram', 'vector', 'both'
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Prevent duplicate citations
    UNIQUE(answer_id, file_path, start_line, end_line)
);

CREATE INDEX idx_citations_answer ON citations(answer_id);

-- ===========================================
-- PR REVIEWS
-- ===========================================
CREATE TABLE pr_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    
    pr_number INTEGER NOT NULL,
    pr_title VARCHAR(500),
    pr_url VARCHAR(500),
    head_sha VARCHAR(40),
    base_sha VARCHAR(40),
    
    status VARCHAR(20) DEFAULT 'pending' 
        CHECK (status IN ('pending', 'analyzing', 'completed', 'failed')),
    
    files_changed INTEGER DEFAULT 0,
    findings_count INTEGER DEFAULT 0,
    critical_count INTEGER DEFAULT 0,
    
    review_posted BOOLEAN DEFAULT false,
    github_review_id BIGINT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    
    UNIQUE(repo_id, pr_number, head_sha)
);

CREATE INDEX idx_pr_reviews_repo ON pr_reviews(repo_id);

-- ===========================================
-- PR FINDINGS (high-precision only)
-- ===========================================
CREATE TABLE pr_findings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pr_review_id UUID REFERENCES pr_reviews(id) ON DELETE CASCADE,
    repo_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    
    -- Classification
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    category VARCHAR(50) NOT NULL CHECK (category IN (
        'secret_exposure',      -- High-precision: exact key patterns
        'migration_destructive', -- High-precision: DROP TABLE/COLUMN
        'auth_middleware_removed', -- High-precision: middleware removal
        'dependency_changed',   -- Always flag: lockfile changes
        'env_leaked',          -- High-precision: .env in commit
        'private_key_exposed'  -- High-precision: PEM blocks
    )),
    
    -- Location
    file_path VARCHAR(1000) NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    
    -- Evidence (REQUIRED - this is what makes it trustworthy)
    evidence JSONB NOT NULL,
    /*
    {
        "snippet": "redacted code snippet",
        "pattern": "ghp_[a-zA-Z0-9]{36}",
        "match": "ghp_xxxx...xxxx",  -- Partially redacted
        "reason": "GitHub Personal Access Token detected",
        "confidence": "exact_match"  -- exact_match | structural | heuristic
    }
    */
    
    -- LLM explanation (generated AFTER detection, optional)
    explanation TEXT,
    suggested_fix TEXT,
    
    -- GitHub state
    comment_posted BOOLEAN DEFAULT false,
    github_comment_id BIGINT,
    
    -- Resolution
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'ignored', 'false_positive')),
    resolved_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_findings_pr ON pr_findings(pr_review_id);
CREATE INDEX idx_findings_severity ON pr_findings(repo_id, severity);

-- ===========================================
-- USAGE METERING (for real cost tracking)
-- ===========================================
CREATE TABLE usage_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    repo_id UUID REFERENCES repositories(id) ON DELETE SET NULL,
    
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
        'repo_indexed',
        'question_asked',
        'pr_reviewed',
        'snippet_fetched'
    )),
    
    -- Token tracking (for cost calculation)
    embedding_tokens INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    
    -- Computed cost (in hundredths of a cent)
    estimated_cost_micro_cents INTEGER DEFAULT 0,
    
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_usage_user ON usage_events(user_id);
CREATE INDEX idx_usage_date ON usage_events(created_at);

-- ===========================================
-- SNIPPET CACHE (temporary, auto-expire)
-- ===========================================
CREATE TABLE snippet_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    
    file_path VARCHAR(1000) NOT NULL,
    commit_sha VARCHAR(40) NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    
    content TEXT NOT NULL,
    
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '1 hour',
    
    UNIQUE(repo_id, commit_sha, file_path, start_line, end_line)
);

CREATE INDEX idx_snippet_cache_expiry ON snippet_cache(expires_at);

-- Cleanup job: DELETE FROM snippet_cache WHERE expires_at < NOW();
```

---

# 3. AST-BASED LARAVEL ROUTE EXTRACTION

## 3.1 Why Regex Fails

```php
// Regex CANNOT handle this:
Route::middleware(['auth', 'verified'])
    ->prefix('api/v1')
    ->group(function () {
        Route::get('/users', [UserController::class, 'index']);
        
        Route::middleware('admin')->group(function () {
            Route::delete('/users/{id}', [UserController::class, 'destroy']);
        });
    });

Route::resource('posts', PostController::class);
```

Regex fails because:
1. Middleware stacks across groups
2. Prefixes nest
3. Resource routes expand to 7 routes
4. Multi-line formatting
5. Variable method chaining order

## 3.2 AST-Based Route Parser

```python
# backend/app/parsers/laravel_route_parser.py

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import tree_sitter_php as php
from tree_sitter import Language, Parser, Node

@dataclass
class RouteContext:
    """Context inherited from parent groups."""
    prefix: str = ""
    middleware: List[str] = field(default_factory=list)
    namespace: str = ""

@dataclass
class ExtractedRoute:
    """A fully resolved Laravel route."""
    method: str
    uri: str
    full_uri: str  # With prefix
    name: Optional[str] = None
    controller: Optional[str] = None
    action: Optional[str] = None
    handler_type: str = "controller"
    middleware: List[str] = field(default_factory=list)
    group_prefix: str = ""
    group_middleware: List[str] = field(default_factory=list)
    source_file: str = ""
    start_line: int = 0
    end_line: int = 0


class LaravelRouteParser:
    """AST-based Laravel route parser using tree-sitter."""
    
    HTTP_METHODS = ['get', 'post', 'put', 'patch', 'delete', 'options', 'any']
    RESOURCE_ACTIONS = [
        ('index', 'get', ''),
        ('create', 'get', '/create'),
        ('store', 'post', ''),
        ('show', 'get', '/{id}'),
        ('edit', 'get', '/{id}/edit'),
        ('update', 'put', '/{id}'),
        ('destroy', 'delete', '/{id}'),
    ]
    API_RESOURCE_ACTIONS = [
        ('index', 'get', ''),
        ('store', 'post', ''),
        ('show', 'get', '/{id}'),
        ('update', 'put', '/{id}'),
        ('destroy', 'delete', '/{id}'),
    ]
    
    def __init__(self):
        self.parser = Parser()
        self.parser.language = Language(php.language())
    
    def parse_file(self, content: str, file_path: str) -> List[ExtractedRoute]:
        """Parse a Laravel route file and extract all routes."""
        tree = self.parser.parse(bytes(content, 'utf8'))
        code_bytes = bytes(content, 'utf8')
        
        routes = []
        root_context = RouteContext()
        
        # Find all Route:: calls
        self._extract_routes_recursive(
            tree.root_node, 
            code_bytes, 
            file_path, 
            root_context, 
            routes
        )
        
        return routes
    
    def _extract_routes_recursive(
        self,
        node: Node,
        code_bytes: bytes,
        file_path: str,
        context: RouteContext,
        routes: List[ExtractedRoute]
    ):
        """Recursively extract routes, handling groups."""
        
        for child in node.children:
            # Check if this is a method call
            if child.type == 'member_call_expression' or child.type == 'scoped_call_expression':
                route = self._try_parse_route_call(child, code_bytes, file_path, context)
                if route:
                    routes.extend(route)
                    continue
                
                # Check for group
                group_result = self._try_parse_group(child, code_bytes, file_path, context)
                if group_result:
                    new_context, group_body = group_result
                    if group_body:
                        self._extract_routes_recursive(
                            group_body, code_bytes, file_path, new_context, routes
                        )
                    continue
            
            # Recurse into children
            self._extract_routes_recursive(child, code_bytes, file_path, context, routes)
    
    def _try_parse_route_call(
        self,
        node: Node,
        code_bytes: bytes,
        file_path: str,
        context: RouteContext
    ) -> Optional[List[ExtractedRoute]]:
        """Try to parse a Route::method() call."""
        
        # Get the full call chain
        call_chain = self._get_call_chain(node, code_bytes)
        if not call_chain:
            return None
        
        # Check if it starts with Route::
        if not self._is_route_facade(call_chain):
            return None
        
        routes = []
        
        # Check for resource/apiResource
        for call in call_chain:
            if call['method'] == 'resource':
                routes.extend(self._expand_resource(call, code_bytes, file_path, context, False))
                return routes
            elif call['method'] == 'apiResource':
                routes.extend(self._expand_resource(call, code_bytes, file_path, context, True))
                return routes
        
        # Check for HTTP method routes
        for call in call_chain:
            if call['method'].lower() in self.HTTP_METHODS:
                route = self._parse_http_route(call, call_chain, code_bytes, file_path, context)
                if route:
                    routes.append(route)
                return routes
        
        return None
    
    def _get_call_chain(self, node: Node, code_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract the chain of method calls (e.g., Route::middleware()->get())."""
        chain = []
        current = node
        
        while current:
            if current.type in ('member_call_expression', 'scoped_call_expression'):
                method_name = self._get_method_name(current, code_bytes)
                args = self._get_call_arguments(current, code_bytes)
                
                if method_name:
                    chain.insert(0, {
                        'method': method_name,
                        'args': args,
                        'node': current
                    })
                
                # Move to the object being called on
                current = current.child_by_field_name('object') or current.children[0]
            elif current.type == 'name':
                # Base of chain (e.g., "Route")
                chain.insert(0, {
                    'method': self._get_node_text(current, code_bytes),
                    'args': [],
                    'node': current
                })
                break
            else:
                current = current.children[0] if current.children else None
        
        return chain
    
    def _is_route_facade(self, call_chain: List[Dict]) -> bool:
        """Check if call chain starts with Route::"""
        if not call_chain:
            return False
        return call_chain[0]['method'] == 'Route'
    
    def _parse_http_route(
        self,
        http_call: Dict,
        call_chain: List[Dict],
        code_bytes: bytes,
        file_path: str,
        context: RouteContext
    ) -> Optional[ExtractedRoute]:
        """Parse a Route::get/post/etc call."""
        
        args = http_call['args']
        if len(args) < 2:
            return None
        
        # First arg is URI
        uri = self._extract_string_value(args[0])
        if uri is None:
            return None
        
        # Second arg is handler
        controller, action, handler_type = self._parse_handler(args[1], code_bytes)
        
        # Get route name from chain
        name = None
        for call in call_chain:
            if call['method'] == 'name' and call['args']:
                name = self._extract_string_value(call['args'][0])
        
        # Get middleware from chain
        route_middleware = list(context.middleware)
        for call in call_chain:
            if call['method'] == 'middleware' and call['args']:
                mw = self._extract_middleware_list(call['args'][0], code_bytes)
                route_middleware.extend(mw)
        
        # Build full URI
        full_uri = self._build_full_uri(context.prefix, uri)
        
        return ExtractedRoute(
            method=http_call['method'].upper(),
            uri=uri,
            full_uri=full_uri,
            name=name,
            controller=controller,
            action=action,
            handler_type=handler_type,
            middleware=route_middleware,
            group_prefix=context.prefix,
            group_middleware=list(context.middleware),
            source_file=file_path,
            start_line=http_call['node'].start_point[0] + 1,
            end_line=http_call['node'].end_point[0] + 1
        )
    
    def _expand_resource(
        self,
        call: Dict,
        code_bytes: bytes,
        file_path: str,
        context: RouteContext,
        is_api: bool
    ) -> List[ExtractedRoute]:
        """Expand Route::resource() into individual routes."""
        
        args = call['args']
        if len(args) < 2:
            return []
        
        resource_name = self._extract_string_value(args[0])
        controller = self._extract_class_reference(args[1], code_bytes)
        
        if not resource_name or not controller:
            return []
        
        routes = []
        actions = self.API_RESOURCE_ACTIONS if is_api else self.RESOURCE_ACTIONS
        
        for action_name, method, suffix in actions:
            uri = f"/{resource_name}{suffix}"
            full_uri = self._build_full_uri(context.prefix, uri)
            
            routes.append(ExtractedRoute(
                method=method.upper(),
                uri=uri,
                full_uri=full_uri,
                name=f"{resource_name}.{action_name}",
                controller=controller,
                action=action_name,
                handler_type='controller',
                middleware=list(context.middleware),
                group_prefix=context.prefix,
                group_middleware=list(context.middleware),
                source_file=file_path,
                start_line=call['node'].start_point[0] + 1,
                end_line=call['node'].end_point[0] + 1
            ))
        
        return routes
    
    def _try_parse_group(
        self,
        node: Node,
        code_bytes: bytes,
        file_path: str,
        context: RouteContext
    ) -> Optional[Tuple[RouteContext, Optional[Node]]]:
        """Try to parse a Route::group() or ->group() call."""
        
        call_chain = self._get_call_chain(node, code_bytes)
        if not call_chain or not self._is_route_facade(call_chain):
            return None
        
        # Find group call in chain
        group_call = None
        for call in call_chain:
            if call['method'] == 'group':
                group_call = call
                break
        
        if not group_call:
            return None
        
        # Build new context from chain
        new_context = RouteContext(
            prefix=context.prefix,
            middleware=list(context.middleware),
            namespace=context.namespace
        )
        
        # Apply prefix from chain
        for call in call_chain:
            if call['method'] == 'prefix' and call['args']:
                prefix = self._extract_string_value(call['args'][0])
                if prefix:
                    new_context.prefix = self._build_full_uri(new_context.prefix, prefix)
        
        # Apply middleware from chain
        for call in call_chain:
            if call['method'] == 'middleware' and call['args']:
                mw = self._extract_middleware_list(call['args'][0], code_bytes)
                new_context.middleware.extend(mw)
        
        # Find the closure body
        group_body = None
        if group_call['args']:
            for arg in group_call['args']:
                if arg.type == 'anonymous_function_creation_expression':
                    group_body = arg.child_by_field_name('body')
                    break
        
        return new_context, group_body
    
    def _parse_handler(
        self, 
        handler_node: Node, 
        code_bytes: bytes
    ) -> Tuple[Optional[str], Optional[str], str]:
        """Parse route handler: [Controller::class, 'method'] or closure."""
        
        if handler_node.type == 'array_creation_expression':
            # [Controller::class, 'method']
            elements = [c for c in handler_node.children if c.type == 'array_element_initializer']
            
            if len(elements) >= 2:
                controller = self._extract_class_reference(elements[0], code_bytes)
                action = self._extract_string_value(elements[1])
                return controller, action, 'controller'
        
        elif handler_node.type == 'class_constant_access_expression':
            # InvokableController::class
            controller = self._extract_class_reference(handler_node, code_bytes)
            return controller, '__invoke', 'invokable'
        
        elif handler_node.type == 'anonymous_function_creation_expression':
            return None, None, 'closure'
        
        return None, None, 'unknown'
    
    def _extract_class_reference(self, node: Node, code_bytes: bytes) -> Optional[str]:
        """Extract class name from Controller::class."""
        if node.type == 'class_constant_access_expression':
            class_node = node.child_by_field_name('class')
            if class_node:
                return self._get_node_text(class_node, code_bytes)
        
        # Check inside array element
        for child in node.children:
            if child.type == 'class_constant_access_expression':
                return self._extract_class_reference(child, code_bytes)
        
        return None
    
    def _extract_string_value(self, node: Node) -> Optional[str]:
        """Extract string value from a node."""
        if node.type in ('string', 'encapsed_string'):
            # Remove quotes
            text = node.text.decode('utf8') if hasattr(node, 'text') else ''
            return text.strip("'\"")
        
        # Check children for string
        for child in node.children:
            if child.type in ('string', 'encapsed_string', 'string_content'):
                text = child.text.decode('utf8') if hasattr(child, 'text') else ''
                return text.strip("'\"")
        
        return None
    
    def _extract_middleware_list(self, node: Node, code_bytes: bytes) -> List[str]:
        """Extract middleware from argument (string or array)."""
        middleware = []
        
        if node.type in ('string', 'encapsed_string'):
            mw = self._extract_string_value(node)
            if mw:
                middleware.append(mw)
        
        elif node.type == 'array_creation_expression':
            for child in node.children:
                if child.type == 'array_element_initializer':
                    mw = self._extract_string_value(child)
                    if mw:
                        middleware.append(mw)
        
        return middleware
    
    def _get_method_name(self, node: Node, code_bytes: bytes) -> Optional[str]:
        """Get method name from a call expression."""
        name_node = node.child_by_field_name('name')
        if name_node:
            return self._get_node_text(name_node, code_bytes)
        return None
    
    def _get_call_arguments(self, node: Node, code_bytes: bytes) -> List[Node]:
        """Get argument nodes from a call."""
        args_node = node.child_by_field_name('arguments')
        if args_node:
            return [c for c in args_node.children if c.type not in ('(', ')', ',')]
        return []
    
    def _get_node_text(self, node: Node, code_bytes: bytes) -> str:
        """Get text content of a node."""
        return code_bytes[node.start_byte:node.end_byte].decode('utf8')
    
    def _build_full_uri(self, prefix: str, uri: str) -> str:
        """Combine prefix and URI."""
        prefix = prefix.strip('/')
        uri = uri.strip('/')
        
        if prefix and uri:
            return f"/{prefix}/{uri}"
        elif prefix:
            return f"/{prefix}"
        elif uri:
            return f"/{uri}"
        else:
            return "/"
```

## 3.3 Route Parser Tests

```python
# backend/tests/test_route_parser.py

import pytest
from app.parsers.laravel_route_parser import LaravelRouteParser

@pytest.fixture
def parser():
    return LaravelRouteParser()

class TestBasicRoutes:
    def test_simple_get(self, parser):
        content = """<?php
Route::get('/users', [UserController::class, 'index']);
"""
        routes = parser.parse_file(content, 'routes/web.php')
        
        assert len(routes) == 1
        assert routes[0].method == 'GET'
        assert routes[0].full_uri == '/users'
        assert routes[0].controller == 'UserController'
        assert routes[0].action == 'index'
    
    def test_route_with_name(self, parser):
        content = """<?php
Route::get('/users', [UserController::class, 'index'])->name('users.index');
"""
        routes = parser.parse_file(content, 'routes/web.php')
        
        assert len(routes) == 1
        assert routes[0].name == 'users.index'
    
    def test_route_with_middleware(self, parser):
        content = """<?php
Route::get('/dashboard', [DashboardController::class, 'index'])->middleware('auth');
"""
        routes = parser.parse_file(content, 'routes/web.php')
        
        assert len(routes) == 1
        assert 'auth' in routes[0].middleware


class TestResourceRoutes:
    def test_resource_expands(self, parser):
        content = """<?php
Route::resource('posts', PostController::class);
"""
        routes = parser.parse_file(content, 'routes/web.php')
        
        assert len(routes) == 7
        methods = {r.method for r in routes}
        assert methods == {'GET', 'POST', 'PUT', 'DELETE'}
        
        # Check specific routes
        index = next(r for r in routes if r.action == 'index')
        assert index.full_uri == '/posts'
        assert index.method == 'GET'
        
        destroy = next(r for r in routes if r.action == 'destroy')
        assert destroy.full_uri == '/posts/{id}'
        assert destroy.method == 'DELETE'
    
    def test_api_resource(self, parser):
        content = """<?php
Route::apiResource('posts', PostController::class);
"""
        routes = parser.parse_file(content, 'routes/api.php')
        
        # API resource has 5 routes (no create/edit)
        assert len(routes) == 5
        actions = {r.action for r in routes}
        assert 'create' not in actions
        assert 'edit' not in actions


class TestGroupedRoutes:
    def test_middleware_group(self, parser):
        content = """<?php
Route::middleware(['auth'])->group(function () {
    Route::get('/dashboard', [DashboardController::class, 'index']);
});
"""
        routes = parser.parse_file(content, 'routes/web.php')
        
        assert len(routes) == 1
        assert 'auth' in routes[0].middleware
    
    def test_prefix_group(self, parser):
        content = """<?php
Route::prefix('api/v1')->group(function () {
    Route::get('/users', [UserController::class, 'index']);
});
"""
        routes = parser.parse_file(content, 'routes/api.php')
        
        assert len(routes) == 1
        assert routes[0].full_uri == '/api/v1/users'
    
    def test_nested_groups(self, parser):
        content = """<?php
Route::middleware(['auth'])->prefix('api')->group(function () {
    Route::get('/public', [PublicController::class, 'index']);
    
    Route::middleware(['admin'])->group(function () {
        Route::delete('/users/{id}', [UserController::class, 'destroy']);
    });
});
"""
        routes = parser.parse_file(content, 'routes/web.php')
        
        assert len(routes) == 2
        
        public_route = next(r for r in routes if 'public' in r.full_uri)
        assert public_route.middleware == ['auth']
        
        delete_route = next(r for r in routes if r.method == 'DELETE')
        assert 'auth' in delete_route.middleware
        assert 'admin' in delete_route.middleware
        assert delete_route.full_uri == '/api/users/{id}'
```

---

# 4. PROOF-CARRYING ANSWER CONTRACT

## 4.1 The Problem

LLM says: "Authentication is handled in AuthController."
Reality: There is no AuthController. LLM hallucinated.

## 4.2 The Solution: Structured Output + Validation

```python
# backend/app/services/qa_service.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import json
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

class ConfidenceTier(str, Enum):
    HIGH = "high"      # >= 3 citations from >= 2 files, covers main question
    MEDIUM = "medium"  # >= 2 citations, partial coverage
    LOW = "low"        # 1 citation or weak relevance
    NONE = "none"      # 0 citations or validation failed

@dataclass
class RetrievedSource:
    """A source retrieved from search."""
    index: int
    file_path: str
    start_line: int
    end_line: int
    content: str
    symbol_name: Optional[str]
    score: float
    source_type: str  # 'trigram' or 'vector'

@dataclass
class AnswerSection:
    """A section of the answer with its sources."""
    text: str
    source_ids: List[int]

@dataclass
class ValidatedAnswer:
    """A fully validated answer."""
    sections: List[AnswerSection]
    unknowns: List[str]
    confidence_tier: ConfidenceTier
    confidence_factors: Dict[str, Any]
    validation_passed: bool
    validation_errors: List[str]

@dataclass
class QAResult:
    """Final Q&A result returned to user."""
    answer_text: str
    citations: List[Dict[str, Any]]
    confidence_tier: ConfidenceTier
    unknowns: List[str]
    has_sufficient_evidence: bool


class QAService:
    """Q&A service with proof-carrying answers."""
    
    ANSWER_PROMPT = """You are a code analysis assistant. Answer the question based ONLY on the provided sources.

CRITICAL RULES:
1. You MUST output valid JSON matching the schema below
2. Every claim MUST reference at least one source_id
3. If you cannot answer part of the question, put it in "unknowns"
4. Do NOT invent file paths or line numbers
5. Do NOT make claims without source evidence

OUTPUT SCHEMA:
{
    "sections": [
        {"text": "The authentication flow starts in...", "source_ids": [1, 3]},
        {"text": "Passwords are hashed using bcrypt...", "source_ids": [2]}
    ],
    "unknowns": [
        "I could not find where password reset emails are sent"
    ]
}

SOURCES:
{sources}

QUESTION: {question}

Respond with ONLY the JSON object, no other text:"""

    def __init__(self, db: AsyncSession, embedding_service, llm_service, github_service):
        self.db = db
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.github_service = github_service
    
    async def answer_question(
        self, 
        repo_id: str, 
        question: str,
        user_id: str
    ) -> QAResult:
        """Answer a question with validated citations."""
        
        # Step 1: Retrieve sources
        sources = await self._retrieve_sources(repo_id, question)
        
        # Step 2: Check minimum sources
        if len(sources) < 1:
            return self._no_evidence_result(question)
        
        # Step 3: Fetch actual snippets from GitHub
        repo = await self._get_repo(repo_id)
        sources = await self._fetch_snippets(repo, sources)
        
        # Step 4: Generate answer with structured output
        validated = await self._generate_validated_answer(question, sources)
        
        # Step 5: Build citations
        citations = self._build_citations(sources, validated, repo)
        
        # Step 6: Store answer
        await self._store_answer(repo_id, user_id, question, validated, citations)
        
        return QAResult(
            answer_text=self._format_answer_text(validated),
            citations=citations,
            confidence_tier=validated.confidence_tier,
            unknowns=validated.unknowns,
            has_sufficient_evidence=validated.confidence_tier != ConfidenceTier.NONE
        )
    
    async def _retrieve_sources(
        self, 
        repo_id: str, 
        question: str
    ) -> List[RetrievedSource]:
        """Retrieve sources using hybrid search."""
        sources = []
        seen_keys = set()
        index = 0
        
        # Trigram search on symbols
        trigram_results = await self._trigram_search(repo_id, question)
        for r in trigram_results:
            key = f"{r['file_path']}:{r['start_line']}"
            if key not in seen_keys:
                seen_keys.add(key)
                index += 1
                sources.append(RetrievedSource(
                    index=index,
                    file_path=r['file_path'],
                    start_line=r['start_line'],
                    end_line=r['end_line'],
                    content="",  # Fetched later from GitHub
                    symbol_name=r.get('symbol_name'),
                    score=r['score'],
                    source_type='trigram'
                ))
        
        # Vector search
        vector_results = await self.embedding_service.search(repo_id, question, limit=15)
        for r in vector_results:
            key = f"{r['file_path']}:{r['start_line']}"
            if key not in seen_keys:
                seen_keys.add(key)
                index += 1
                sources.append(RetrievedSource(
                    index=index,
                    file_path=r['file_path'],
                    start_line=r['start_line'],
                    end_line=r['end_line'],
                    content="",
                    symbol_name=r.get('symbol_name'),
                    score=r['score'],
                    source_type='vector'
                ))
        
        # Sort by score and limit
        sources.sort(key=lambda x: x.score, reverse=True)
        
        # Re-index after sorting
        for i, source in enumerate(sources[:15], 1):
            source.index = i
        
        return sources[:15]
    
    async def _trigram_search(
        self, 
        repo_id: str, 
        query: str
    ) -> List[Dict[str, Any]]:
        """Search using trigram similarity."""
        
        # Extract keywords from query
        keywords = self._extract_keywords(query)
        if not keywords:
            return []
        
        # Build trigram query
        sql = text("""
            SELECT 
                s.name,
                s.qualified_name,
                s.file_path,
                s.start_line,
                s.end_line,
                s.signature,
                GREATEST(
                    similarity(s.name, :query),
                    similarity(s.qualified_name, :query)
                ) as score
            FROM symbols s
            WHERE s.repo_id = :repo_id
            AND (
                s.name % :query
                OR s.qualified_name % :query
                OR s.search_text ILIKE :like_query
            )
            ORDER BY score DESC
            LIMIT 10
        """)
        
        result = await self.db.execute(sql, {
            'repo_id': repo_id,
            'query': ' '.join(keywords),
            'like_query': f'%{keywords[0]}%' if keywords else '%'
        })
        
        return [
            {
                'file_path': r.file_path,
                'start_line': r.start_line,
                'end_line': r.end_line,
                'symbol_name': r.qualified_name,
                'score': float(r.score) if r.score else 0.5
            }
            for r in result
        ]
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from query."""
        # Remove common words
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'how', 'what', 'where', 'when', 'why', 'which', 'who',
            'does', 'do', 'did', 'has', 'have', 'had',
            'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'
        }
        
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        return keywords[:5]
    
    async def _fetch_snippets(
        self, 
        repo, 
        sources: List[RetrievedSource]
    ) -> List[RetrievedSource]:
        """Fetch actual code snippets from GitHub."""
        
        for source in sources:
            # Check cache first
            cached = await self._get_cached_snippet(
                repo.id, 
                repo.last_indexed_commit,
                source.file_path,
                source.start_line,
                source.end_line
            )
            
            if cached:
                source.content = cached
                continue
            
            # Fetch from GitHub
            try:
                content = await self.github_service.get_file_content(
                    installation_id=repo.github_installation_id,
                    owner=repo.owner,
                    repo=repo.name,
                    path=source.file_path,
                    ref=repo.last_indexed_commit
                )
                
                # Extract lines
                lines = content.split('\n')
                start_idx = max(0, source.start_line - 1)
                end_idx = min(len(lines), source.end_line)
                snippet = '\n'.join(lines[start_idx:end_idx])
                
                # Limit size
                if len(snippet) > 500:
                    snippet = snippet[:500] + '...'
                
                source.content = snippet
                
                # Cache it
                await self._cache_snippet(
                    repo.id,
                    repo.last_indexed_commit,
                    source.file_path,
                    source.start_line,
                    source.end_line,
                    snippet
                )
                
            except Exception as e:
                source.content = f"[Could not fetch: {e}]"
        
        return sources
    
    async def _generate_validated_answer(
        self, 
        question: str, 
        sources: List[RetrievedSource]
    ) -> ValidatedAnswer:
        """Generate answer and validate it."""
        
        # Build sources text
        sources_text = "\n\n".join([
            f"[Source {s.index}] {s.file_path}:{s.start_line}-{s.end_line}"
            f"{f' ({s.symbol_name})' if s.symbol_name else ''}\n"
            f"```\n{s.content}\n```"
            for s in sources
        ])
        
        prompt = self.ANSWER_PROMPT.format(
            sources=sources_text,
            question=question
        )
        
        # Generate
        response = await self.llm_service.generate(prompt, max_tokens=1500)
        
        # Parse JSON
        parsed = self._parse_answer_json(response)
        if not parsed:
            # Retry once
            response = await self.llm_service.generate(
                prompt + "\n\nRemember: Output ONLY valid JSON.",
                max_tokens=1500
            )
            parsed = self._parse_answer_json(response)
        
        if not parsed:
            return ValidatedAnswer(
                sections=[],
                unknowns=["Failed to generate structured answer"],
                confidence_tier=ConfidenceTier.NONE,
                confidence_factors={},
                validation_passed=False,
                validation_errors=["JSON parsing failed"]
            )
        
        # Validate
        return self._validate_answer(parsed, sources)
    
    def _parse_answer_json(self, response: str) -> Optional[Dict]:
        """Parse JSON from LLM response."""
        # Try direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _validate_answer(
        self, 
        parsed: Dict, 
        sources: List[RetrievedSource]
    ) -> ValidatedAnswer:
        """Validate the parsed answer."""
        errors = []
        valid_source_ids = {s.index for s in sources}
        
        sections = []
        for i, section_data in enumerate(parsed.get('sections', [])):
            text = section_data.get('text', '')
            source_ids = section_data.get('source_ids', [])
            
            if not text:
                errors.append(f"Section {i} has no text")
                continue
            
            if not source_ids:
                errors.append(f"Section {i} has no source_ids")
                continue
            
            # Validate source_ids exist
            invalid_ids = [sid for sid in source_ids if sid not in valid_source_ids]
            if invalid_ids:
                errors.append(f"Section {i} references invalid source_ids: {invalid_ids}")
                # Remove invalid IDs but keep valid ones
                source_ids = [sid for sid in source_ids if sid in valid_source_ids]
            
            if source_ids:  # Only add if we have valid sources
                sections.append(AnswerSection(text=text, source_ids=source_ids))
        
        unknowns = parsed.get('unknowns', [])
        
        # Calculate confidence
        confidence_tier, confidence_factors = self._calculate_confidence(sections, sources)
        
        return ValidatedAnswer(
            sections=sections,
            unknowns=unknowns,
            confidence_tier=confidence_tier,
            confidence_factors=confidence_factors,
            validation_passed=len(errors) == 0,
            validation_errors=errors
        )
    
    def _calculate_confidence(
        self, 
        sections: List[AnswerSection],
        sources: List[RetrievedSource]
    ) -> Tuple[ConfidenceTier, Dict[str, Any]]:
        """Calculate confidence tier based on evidence coverage."""
        
        if not sections:
            return ConfidenceTier.NONE, {"reason": "no_sections"}
        
        # Collect all cited source IDs
        cited_ids = set()
        for section in sections:
            cited_ids.update(section.source_ids)
        
        # Get cited sources
        cited_sources = [s for s in sources if s.index in cited_ids]
        
        # Count unique files
        unique_files = len(set(s.file_path for s in cited_sources))
        
        # Check for entrypoints (routes, controllers for Laravel)
        has_entrypoints = any(
            'controller' in s.file_path.lower() or 
            'route' in s.file_path.lower()
            for s in cited_sources
        )
        
        factors = {
            "citation_count": len(cited_ids),
            "unique_files": unique_files,
            "has_entrypoints": has_entrypoints,
            "section_count": len(sections)
        }
        
        # Determine tier
        if len(cited_ids) >= 3 and unique_files >= 2:
            return ConfidenceTier.HIGH, factors
        elif len(cited_ids) >= 2:
            return ConfidenceTier.MEDIUM, factors
        elif len(cited_ids) >= 1:
            return ConfidenceTier.LOW, factors
        else:
            return ConfidenceTier.NONE, factors
    
    def _format_answer_text(self, validated: ValidatedAnswer) -> str:
        """Format validated answer as readable text."""
        parts = []
        
        for section in validated.sections:
            # Add source references
            refs = ', '.join(f'[{sid}]' for sid in section.source_ids)
            parts.append(f"{section.text} {refs}")
        
        if validated.unknowns:
            parts.append("\n**Could not determine:**")
            for unknown in validated.unknowns:
                parts.append(f"- {unknown}")
        
        return '\n\n'.join(parts)
    
    def _build_citations(
        self, 
        sources: List[RetrievedSource],
        validated: ValidatedAnswer,
        repo
    ) -> List[Dict[str, Any]]:
        """Build citation objects for response."""
        
        # Get all cited source IDs
        cited_ids = set()
        for section in validated.sections:
            cited_ids.update(section.source_ids)
        
        citations = []
        for source in sources:
            if source.index in cited_ids:
                github_url = (
                    f"https://github.com/{repo.full_name}/blob/"
                    f"{repo.last_indexed_commit}/{source.file_path}"
                    f"#L{source.start_line}-L{source.end_line}"
                )
                
                citations.append({
                    "source_index": source.index,
                    "file_path": source.file_path,
                    "start_line": source.start_line,
                    "end_line": source.end_line,
                    "snippet": source.content,
                    "symbol_name": source.symbol_name,
                    "github_url": github_url
                })
        
        return citations
    
    def _no_evidence_result(self, question: str) -> QAResult:
        """Return result when no evidence found."""
        return QAResult(
            answer_text=f"I could not find enough evidence in the codebase to answer: \"{question}\"\n\nTry asking about specific class or function names.",
            citations=[],
            confidence_tier=ConfidenceTier.NONE,
            unknowns=[question],
            has_sufficient_evidence=False
        )
    
    async def _get_repo(self, repo_id: str):
        """Get repository record."""
        from app.models.repository import Repository
        from sqlalchemy import select
        
        result = await self.db.execute(
            select(Repository).where(Repository.id == repo_id)
        )
        return result.scalar_one()
    
    async def _get_cached_snippet(
        self, repo_id, commit_sha, file_path, start_line, end_line
    ) -> Optional[str]:
        """Get cached snippet if available."""
        sql = text("""
            SELECT content FROM snippet_cache
            WHERE repo_id = :repo_id
            AND commit_sha = :commit_sha
            AND file_path = :file_path
            AND start_line = :start_line
            AND end_line = :end_line
            AND expires_at > NOW()
        """)
        result = await self.db.execute(sql, {
            'repo_id': repo_id,
            'commit_sha': commit_sha,
            'file_path': file_path,
            'start_line': start_line,
            'end_line': end_line
        })
        row = result.fetchone()
        return row.content if row else None
    
    async def _cache_snippet(
        self, repo_id, commit_sha, file_path, start_line, end_line, content
    ):
        """Cache snippet for later use."""
        sql = text("""
            INSERT INTO snippet_cache (repo_id, commit_sha, file_path, start_line, end_line, content)
            VALUES (:repo_id, :commit_sha, :file_path, :start_line, :end_line, :content)
            ON CONFLICT (repo_id, commit_sha, file_path, start_line, end_line) 
            DO UPDATE SET content = :content, expires_at = NOW() + INTERVAL '1 hour'
        """)
        await self.db.execute(sql, {
            'repo_id': repo_id,
            'commit_sha': commit_sha,
            'file_path': file_path,
            'start_line': start_line,
            'end_line': end_line,
            'content': content
        })
    
    async def _store_answer(
        self, repo_id, user_id, question, validated: ValidatedAnswer, citations
    ):
        """Store answer in database."""
        from app.models.answer import Answer
        from app.models.citation import Citation
        
        answer = Answer(
            repo_id=repo_id,
            user_id=user_id,
            question=question,
            answer_text=self._format_answer_text(validated),
            answer_sections=[
                {"text": s.text, "source_ids": s.source_ids}
                for s in validated.sections
            ],
            unknowns=validated.unknowns,
            confidence_tier=validated.confidence_tier.value,
            confidence_factors=validated.confidence_factors,
            validation_passed=validated.validation_passed,
            validation_errors=validated.validation_errors
        )
        self.db.add(answer)
        await self.db.flush()
        
        for cite in citations:
            citation = Citation(
                answer_id=answer.id,
                source_index=cite['source_index'],
                file_path=cite['file_path'],
                start_line=cite['start_line'],
                end_line=cite['end_line'],
                snippet=cite['snippet'][:500],
                symbol_name=cite.get('symbol_name')
            )
            self.db.add(citation)
        
        await self.db.commit()
```

---

# 5. HIGH-PRECISION ANALYZERS ONLY

## 5.1 What We Ship vs What We Cut

| Analyzer | Status | Precision | Why |
|----------|--------|-----------|-----|
| GitHub PAT | SHIP | ~100% | Exact pattern `ghp_[a-zA-Z0-9]{36}` |
| AWS Access Key | SHIP | ~100% | Exact pattern `AKIA[0-9A-Z]{16}` |
| Stripe Live Key | SHIP | ~100% | Exact pattern `sk_live_` |
| PEM Private Key | SHIP | ~100% | Exact pattern `-----BEGIN.*PRIVATE KEY-----` |
| .env in commit | SHIP | ~100% | File path match |
| DROP TABLE/COLUMN | SHIP | ~100% | AST/pattern match |
| Auth middleware removed | SHIP | ~95% | AST-based detection |
| Lockfile changed | SHIP | ~100% | File path match |
| Generic entropy | CUT | ~30% | Too many false positives |
| Generic password | CUT | ~40% | Flags examples and config |
| SQL injection | CUT | ~50% | Needs context |
| XSS patterns | CUT | ~40% | Needs context |
| Command injection | CUT | ~60% | Needs context |

## 5.2 High-Precision Analyzer Implementation

```python
# backend/app/analyzers/high_precision_analyzer.py

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

class Category(str, Enum):
    SECRET_EXPOSURE = "secret_exposure"
    MIGRATION_DESTRUCTIVE = "migration_destructive"
    AUTH_MIDDLEWARE_REMOVED = "auth_middleware_removed"
    DEPENDENCY_CHANGED = "dependency_changed"
    ENV_LEAKED = "env_leaked"
    PRIVATE_KEY_EXPOSED = "private_key_exposed"

@dataclass
class Finding:
    """A high-precision finding."""
    severity: Severity
    category: Category
    file_path: str
    start_line: int
    end_line: int
    evidence: Dict[str, Any]
    confidence: str = "exact_match"  # exact_match | structural | pattern


class HighPrecisionAnalyzer:
    """
    High-precision analyzer that only flags issues we're confident about.
    
    Design principle: It's better to miss some issues than to flood
    users with false positives and destroy trust.
    """
    
    # ========================================
    # EXACT MATCH PATTERNS (near 100% precision)
    # ========================================
    
    EXACT_PATTERNS = [
        # GitHub Personal Access Token (classic)
        {
            "pattern": r'ghp_[a-zA-Z0-9]{36}',
            "name": "GitHub Personal Access Token",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: f"ghp_{'*' * 32}..."
        },
        # GitHub Fine-grained PAT
        {
            "pattern": r'github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}',
            "name": "GitHub Fine-grained PAT",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "github_pat_****..."
        },
        # AWS Access Key ID
        {
            "pattern": r'AKIA[0-9A-Z]{16}',
            "name": "AWS Access Key ID",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: f"AKIA{'*' * 12}..."
        },
        # Stripe Live Secret Key
        {
            "pattern": r'sk_live_[a-zA-Z0-9]{24,}',
            "name": "Stripe Live Secret Key",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "sk_live_****..."
        },
        # Stripe Live Publishable Key (less critical but still flag)
        {
            "pattern": r'pk_live_[a-zA-Z0-9]{24,}',
            "name": "Stripe Live Publishable Key",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.WARNING,
            "redact": lambda m: "pk_live_****..."
        },
        # Slack Bot Token
        {
            "pattern": r'xoxb-[0-9]{11,13}-[0-9]{11,13}-[a-zA-Z0-9]{24}',
            "name": "Slack Bot Token",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "xoxb-****..."
        },
        # Slack User Token
        {
            "pattern": r'xoxp-[0-9]{11,13}-[0-9]{11,13}-[a-zA-Z0-9]{24}',
            "name": "Slack User Token",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "xoxp-****..."
        },
        # SendGrid API Key
        {
            "pattern": r'SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}',
            "name": "SendGrid API Key",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "SG.****..."
        },
        # Twilio Account SID
        {
            "pattern": r'AC[a-f0-9]{32}',
            "name": "Twilio Account SID",
            "category": Category.SECRET_EXPOSURE,
            "severity": Severity.WARNING,
            "redact": lambda m: "AC****..."
        },
        # RSA/EC/DSA Private Key
        {
            "pattern": r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
            "name": "Private Key",
            "category": Category.PRIVATE_KEY_EXPOSED,
            "severity": Severity.CRITICAL,
            "redact": lambda m: "-----BEGIN PRIVATE KEY-----"
        },
    ]
    
    # ========================================
    # FILE-BASED PATTERNS
    # ========================================
    
    DANGEROUS_FILES = [
        {
            "pattern": r'^\.env$',
            "name": ".env file committed",
            "category": Category.ENV_LEAKED,
            "severity": Severity.CRITICAL
        },
        {
            "pattern": r'^\.env\.(local|production|staging)$',
            "name": "Environment file committed",
            "category": Category.ENV_LEAKED,
            "severity": Severity.CRITICAL
        },
        {
            "pattern": r'id_rsa$|id_ed25519$|id_ecdsa$',
            "name": "SSH private key committed",
            "category": Category.PRIVATE_KEY_EXPOSED,
            "severity": Severity.CRITICAL
        },
    ]
    
    LOCKFILES = [
        'composer.lock',
        'package-lock.json',
        'yarn.lock',
        'pnpm-lock.yaml',
        'Gemfile.lock',
        'poetry.lock'
    ]
    
    # ========================================
    # MIGRATION PATTERNS (Laravel)
    # ========================================
    
    DESTRUCTIVE_MIGRATION_PATTERNS = [
        {
            "pattern": r'Schema::drop(?:IfExists)?\s*\(\s*[\'"](\w+)[\'"]',
            "name": "DROP TABLE",
            "extract_target": 1  # Group 1 contains table name
        },
        {
            "pattern": r'\$table->dropColumn\s*\(\s*[\'"](\w+)[\'"]',
            "name": "DROP COLUMN",
            "extract_target": 1
        },
        {
            "pattern": r'\$table->dropColumn\s*\(\s*\[([^\]]+)\]',
            "name": "DROP COLUMNS",
            "extract_target": 1
        },
        {
            "pattern": r'Schema::rename\s*\(',
            "name": "RENAME TABLE",
            "extract_target": None
        },
        {
            "pattern": r'\$table->renameColumn\s*\(',
            "name": "RENAME COLUMN",
            "extract_target": None
        },
    ]
    
    # ========================================
    # AUTH PATTERNS (Laravel)
    # ========================================
    
    AUTH_MIDDLEWARE_REMOVAL_PATTERN = re.compile(
        r'->withoutMiddleware\s*\(\s*[\'"](auth|verified|can|admin)[\'"]',
        re.IGNORECASE
    )
    
    def __init__(self):
        # Compile patterns
        self.compiled_exact = [
            {**p, "compiled": re.compile(p["pattern"])}
            for p in self.EXACT_PATTERNS
        ]
        self.compiled_files = [
            {**p, "compiled": re.compile(p["pattern"])}
            for p in self.DANGEROUS_FILES
        ]
        self.compiled_migrations = [
            {**p, "compiled": re.compile(p["pattern"], re.IGNORECASE)}
            for p in self.DESTRUCTIVE_MIGRATION_PATTERNS
        ]
    
    def analyze_file(
        self,
        file_path: str,
        content: str,
        diff_lines: Optional[List[int]] = None
    ) -> List[Finding]:
        """Analyze a single file for high-precision issues."""
        findings = []
        
        # Check dangerous file patterns
        findings.extend(self._check_dangerous_file(file_path))
        
        # Check lockfile changes
        if self._is_lockfile(file_path):
            findings.append(Finding(
                severity=Severity.INFO,
                category=Category.DEPENDENCY_CHANGED,
                file_path=file_path,
                start_line=1,
                end_line=1,
                evidence={
                    "snippet": f"{file_path} was modified",
                    "reason": "Dependency lockfile changed - review for security implications",
                    "confidence": "exact_match"
                }
            ))
        
        # Check content patterns
        if content:
            findings.extend(self._check_exact_patterns(file_path, content, diff_lines))
            
            if self._is_migration_file(file_path):
                findings.extend(self._check_destructive_migrations(file_path, content, diff_lines))
            
            if self._is_route_file(file_path):
                findings.extend(self._check_auth_middleware_removal(file_path, content, diff_lines))
        
        return findings
    
    def _check_dangerous_file(self, file_path: str) -> List[Finding]:
        """Check if file itself is dangerous to commit."""
        findings = []
        filename = file_path.split('/')[-1]
        
        for pattern in self.compiled_files:
            if pattern["compiled"].search(filename):
                findings.append(Finding(
                    severity=pattern["severity"],
                    category=pattern["category"],
                    file_path=file_path,
                    start_line=1,
                    end_line=1,
                    evidence={
                        "snippet": file_path,
                        "pattern": pattern["pattern"],
                        "reason": f"{pattern['name']} - this file should not be committed",
                        "confidence": "exact_match"
                    }
                ))
        
        return findings
    
    def _is_lockfile(self, file_path: str) -> bool:
        """Check if file is a dependency lockfile."""
        filename = file_path.split('/')[-1]
        return filename in self.LOCKFILES
    
    def _is_migration_file(self, file_path: str) -> bool:
        """Check if file is a Laravel migration."""
        return 'migrations/' in file_path.lower() and file_path.endswith('.php')
    
    def _is_route_file(self, file_path: str) -> bool:
        """Check if file is a Laravel route file."""
        return 'routes/' in file_path.lower() and file_path.endswith('.php')
    
    def _check_exact_patterns(
        self,
        file_path: str,
        content: str,
        diff_lines: Optional[List[int]]
    ) -> List[Finding]:
        """Check for exact-match secret patterns."""
        findings = []
        
        # Skip files that are unlikely to contain real secrets
        if self._should_skip_file(file_path):
            return findings
        
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Skip if not in diff (when diff_lines provided)
            if diff_lines and line_num not in diff_lines:
                continue
            
            for pattern in self.compiled_exact:
                match = pattern["compiled"].search(line)
                if match:
                    # Redact the match for safe display
                    redacted = pattern["redact"](match)
                    
                    findings.append(Finding(
                        severity=pattern["severity"],
                        category=pattern["category"],
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence={
                            "snippet": self._redact_line(line, match),
                            "pattern": pattern["name"],
                            "match": redacted,
                            "reason": f"{pattern['name']} detected - this should not be in code",
                            "confidence": "exact_match"
                        }
                    ))
        
        return findings
    
    def _check_destructive_migrations(
        self,
        file_path: str,
        content: str,
        diff_lines: Optional[List[int]]
    ) -> List[Finding]:
        """Check for destructive migration operations."""
        findings = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            if diff_lines and line_num not in diff_lines:
                continue
            
            for pattern in self.compiled_migrations:
                match = pattern["compiled"].search(line)
                if match:
                    target = ""
                    if pattern["extract_target"] is not None:
                        try:
                            target = match.group(pattern["extract_target"])
                        except IndexError:
                            pass
                    
                    reason = f"{pattern['name']}"
                    if target:
                        reason += f" on '{target}'"
                    reason += " - this will cause data loss"
                    
                    findings.append(Finding(
                        severity=Severity.CRITICAL,
                        category=Category.MIGRATION_DESTRUCTIVE,
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        evidence={
                            "snippet": line.strip(),
                            "operation": pattern["name"],
                            "target": target,
                            "reason": reason,
                            "confidence": "exact_match"
                        }
                    ))
        
        return findings
    
    def _check_auth_middleware_removal(
        self,
        file_path: str,
        content: str,
        diff_lines: Optional[List[int]]
    ) -> List[Finding]:
        """Check for auth middleware being removed from routes."""
        findings = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            if diff_lines and line_num not in diff_lines:
                continue
            
            match = self.AUTH_MIDDLEWARE_REMOVAL_PATTERN.search(line)
            if match:
                middleware = match.group(1)
                findings.append(Finding(
                    severity=Severity.CRITICAL,
                    category=Category.AUTH_MIDDLEWARE_REMOVED,
                    file_path=file_path,
                    start_line=line_num,
                    end_line=line_num,
                    evidence={
                        "snippet": line.strip(),
                        "middleware": middleware,
                        "reason": f"'{middleware}' middleware is being removed - this may expose the route to unauthorized access",
                        "confidence": "structural"
                    }
                ))
        
        return findings
    
    def _should_skip_file(self, file_path: str) -> bool:
        """Check if file should be skipped for secret scanning."""
        skip_patterns = [
            '.lock',
            '.min.js',
            '.min.css',
            '.map',
            '.svg',
            '.png',
            '.jpg',
            '.gif',
            '.ico',
            '.woff',
            '.ttf',
            '/vendor/',
            '/node_modules/',
            '/dist/',
            '/build/',
            '__pycache__',
        ]
        
        path_lower = file_path.lower()
        return any(pattern in path_lower for pattern in skip_patterns)
    
    def _redact_line(self, line: str, match) -> str:
        """Redact the matched secret in the line."""
        start, end = match.span()
        secret = match.group()
        
        # Show first 4 and last 4 chars
        if len(secret) > 12:
            redacted = secret[:4] + '*' * (len(secret) - 8) + secret[-4:]
        else:
            redacted = secret[:2] + '*' * (len(secret) - 2)
        
        return line[:start] + redacted + line[end:]
```

## 5.3 Review Service (Using High-Precision Only)

```python
# backend/app/services/review_service.py

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.repository import Repository
from app.models.pr_review import PRReview
from app.models.pr_finding import PRFinding
from app.services.github_service import github_service
from app.services.llm_service import LLMService
from app.analyzers.high_precision_analyzer import HighPrecisionAnalyzer, Finding, Severity


class ReviewService:
    """PR review service using high-precision analyzers only."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.analyzer = HighPrecisionAnalyzer()
        self.llm_service = LLMService()
    
    async def review_pr(
        self,
        repo_id: str,
        pr_number: int,
        installation_id: int
    ) -> PRReview:
        """Review a PR with high-precision analysis."""
        
        # Get repo
        result = await self.db.execute(
            select(Repository).where(Repository.id == repo_id)
        )
        repo = result.scalar_one()
        
        # Create review record
        review = PRReview(
            repo_id=repo_id,
            pr_number=pr_number,
            status="analyzing"
        )
        self.db.add(review)
        await self.db.flush()
        
        try:
            # Get PR data
            pr_data = await github_service.get_pr(
                installation_id=installation_id,
                owner=repo.owner,
                repo=repo.name,
                pr_number=pr_number
            )
            
            review.pr_title = pr_data["title"]
            review.pr_url = pr_data["html_url"]
            review.head_sha = pr_data["head"]["sha"]
            review.base_sha = pr_data["base"]["sha"]
            
            # Get changed files
            pr_files = await github_service.get_pr_files(
                installation_id=installation_id,
                owner=repo.owner,
                repo=repo.name,
                pr_number=pr_number
            )
            
            review.files_changed = len(pr_files)
            
            # Analyze each file
            all_findings: List[Finding] = []
            
            for file_data in pr_files:
                file_path = file_data["filename"]
                status = file_data["status"]
                patch = file_data.get("patch", "")
                
                # Get diff lines
                diff_lines = self._parse_diff_lines(patch) if patch else None
                
                # For added/modified files, get content
                if status in ("added", "modified"):
                    try:
                        content = await github_service.get_file_content(
                            installation_id=installation_id,
                            owner=repo.owner,
                            repo=repo.name,
                            path=file_path,
                            ref=review.head_sha
                        )
                        
                        findings = self.analyzer.analyze_file(
                            file_path=file_path,
                            content=content,
                            diff_lines=diff_lines
                        )
                        all_findings.extend(findings)
                        
                    except Exception:
                        continue
                
                # For any file, check if it's a dangerous file type
                elif status == "added":
                    findings = self.analyzer.analyze_file(
                        file_path=file_path,
                        content="",
                        diff_lines=None
                    )
                    all_findings.extend(findings)
            
            # Store findings
            for finding in all_findings:
                pr_finding = PRFinding(
                    pr_review_id=review.id,
                    repo_id=repo_id,
                    severity=finding.severity.value,
                    category=finding.category.value,
                    file_path=finding.file_path,
                    start_line=finding.start_line,
                    end_line=finding.end_line,
                    evidence=finding.evidence
                )
                self.db.add(pr_finding)
            
            # Generate explanations for critical findings only
            critical_findings = [f for f in all_findings if f.severity == Severity.CRITICAL]
            if critical_findings:
                await self._add_explanations(critical_findings)
            
            # Post to GitHub
            await self._post_review(repo, review, all_findings, installation_id)
            
            # Update stats
            review.findings_count = len(all_findings)
            review.critical_count = len(critical_findings)
            review.status = "completed"
            review.review_posted = True
            
        except Exception as e:
            review.status = "failed"
            raise
        
        await self.db.commit()
        return review
    
    def _parse_diff_lines(self, patch: str) -> List[int]:
        """Parse diff to get added line numbers."""
        if not patch:
            return []
        
        lines = []
        current_line = 0
        
        for line in patch.split('\n'):
            if line.startswith('@@'):
                # Parse @@ -start,count +start,count @@
                import re
                match = re.search(r'\+(\d+)', line)
                if match:
                    current_line = int(match.group(1)) - 1
            elif line.startswith('+') and not line.startswith('+++'):
                current_line += 1
                lines.append(current_line)
            elif not line.startswith('-'):
                current_line += 1
        
        return lines
    
    async def _add_explanations(self, findings: List[Finding]):
        """Add LLM explanations to critical findings."""
        for finding in findings[:5]:  # Limit to 5 explanations
            prompt = f"""Explain this security finding in 2 sentences and suggest a fix in 1 sentence.

Finding: {finding.evidence.get('reason', '')}
File: {finding.file_path}
Code: {finding.evidence.get('snippet', '')}

Be concise and actionable."""

            explanation = await self.llm_service.generate(prompt, max_tokens=150)
            finding.evidence["explanation"] = explanation
    
    async def _post_review(
        self,
        repo: Repository,
        review: PRReview,
        findings: List[Finding],
        installation_id: int
    ):
        """Post review to GitHub."""
        
        if not findings:
            # No findings - just post a comment
            await github_service.create_pr_review(
                installation_id=installation_id,
                owner=repo.owner,
                repo=repo.name,
                pr_number=review.pr_number,
                body="**CodeProof Review**\n\nNo high-risk issues detected.",
                event="COMMENT"
            )
            return
        
        # Build summary
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        warnings = [f for f in findings if f.severity == Severity.WARNING]
        info = [f for f in findings if f.severity == Severity.INFO]
        
        body_parts = ["**CodeProof Review**\n"]
        
        if critical:
            body_parts.append(f"### :red_circle: Critical ({len(critical)})\n")
            for f in critical:
                body_parts.append(
                    f"- **{f.evidence.get('pattern', f.category.value)}** "
                    f"in `{f.file_path}:{f.start_line}`\n"
                )
        
        if warnings:
            body_parts.append(f"\n### :yellow_circle: Warnings ({len(warnings)})\n")
            for f in warnings:
                body_parts.append(
                    f"- {f.evidence.get('reason', f.category.value)} "
                    f"in `{f.file_path}`\n"
                )
        
        if info:
            body_parts.append(f"\n### :blue_circle: Info ({len(info)})\n")
            body_parts.append(f"{len(info)} informational items.\n")
        
        body = "".join(body_parts)
        
        # Build inline comments for critical findings only
        comments = []
        for finding in critical[:10]:
            comment_body = (
                f"**{finding.severity.value.upper()}**: "
                f"{finding.evidence.get('pattern', finding.category.value)}\n\n"
                f"{finding.evidence.get('reason', '')}\n\n"
            )
            
            if finding.evidence.get('explanation'):
                comment_body += f"**Explanation:** {finding.evidence['explanation']}\n\n"
            
            comment_body += f"```\n{finding.evidence.get('snippet', '')[:200]}\n```"
            
            comments.append({
                "path": finding.file_path,
                "line": finding.start_line,
                "body": comment_body
            })
        
        # Determine event type
        event = "REQUEST_CHANGES" if critical else "COMMENT"
        
        # Post review
        result = await github_service.create_pr_review(
            installation_id=installation_id,
            owner=repo.owner,
            repo=repo.name,
            pr_number=review.pr_number,
            body=body,
            event=event,
            comments=comments if comments else None
        )
        
        review.github_review_id = result.get("id")
```

---

# 6. SECURE GITHUB AUTHENTICATION

## 6.1 Fixed Clone Method

```python
# backend/app/services/github_service.py (fixed)

import subprocess
import tempfile
import os

class GitHubService:
    # ... other methods ...
    
    async def clone_repo(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        target_dir: str,
        ref: str = None
    ) -> str:
        """
        Clone repository securely using auth header.
        
        SECURITY: Never put tokens in URLs - they leak via:
        - Shell history
        - Process lists (ps aux)
        - Error logs
        - CI/CD artifacts
        """
        token = await self.get_installation_token(installation_id)
        
        # Use auth header instead of URL token
        clone_url = f"https://github.com/{owner}/{repo}.git"
        
        # Set up environment for git
        env = os.environ.copy()
        
        # Use GIT_ASKPASS to provide credentials securely
        askpass_script = self._create_askpass_script(token)
        env["GIT_ASKPASS"] = askpass_script
        env["GIT_TERMINAL_PROMPT"] = "0"
        
        try:
            # Clone with depth 1 for speed
            cmd = ["git", "clone", "--depth", "1"]
            if ref:
                cmd.extend(["--branch", ref])
            cmd.extend([clone_url, target_dir])
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                # Sanitize error message (remove any tokens)
                error = self._sanitize_error(result.stderr)
                raise Exception(f"Clone failed: {error}")
            
            # Get commit SHA
            sha_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=target_dir,
                capture_output=True,
                text=True
            )
            
            return sha_result.stdout.strip()
            
        finally:
            # Clean up askpass script
            if os.path.exists(askpass_script):
                os.remove(askpass_script)
    
    def _create_askpass_script(self, token: str) -> str:
        """Create a temporary script to provide git credentials."""
        # Create temp file
        fd, path = tempfile.mkstemp(suffix='.sh')
        
        # Write script that echoes the token
        script = f"""#!/bin/bash
echo "{token}"
"""
        os.write(fd, script.encode())
        os.close(fd)
        
        # Make executable
        os.chmod(path, 0o700)
        
        return path
    
    def _sanitize_error(self, error: str) -> str:
        """Remove any potential secrets from error messages."""
        import re
        
        # Remove anything that looks like a token
        sanitized = re.sub(r'ghp_[a-zA-Z0-9]+', '[REDACTED]', error)
        sanitized = re.sub(r'ghu_[a-zA-Z0-9]+', '[REDACTED]', sanitized)
        sanitized = re.sub(r'x-access-token:[^@]+@', 'x-access-token:[REDACTED]@', sanitized)
        
        return sanitized
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify GitHub webhook signature.
        
        CRITICAL: Always verify webhooks to prevent:
        - Fake webhook injection
        - Unauthorized actions
        """
        import hmac
        import hashlib
        
        if not signature or not signature.startswith("sha256="):
            return False
        
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(f"sha256={expected}", signature)
```

---

# 7. USAGE METERING

## 7.1 Cost Tracking Service

```python
# backend/app/services/metering_service.py

from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# Cost per 1K tokens (as of Dec 2024)
COSTS = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},  # $2.50/$10 per 1M
    "text-embedding-3-small": {"input": 0.00002},  # $0.02 per 1M
}

@dataclass
class UsageMetrics:
    embedding_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    
    def estimated_cost_cents(self) -> int:
        """Calculate cost in hundredths of a cent."""
        embedding_cost = (self.embedding_tokens / 1000) * COSTS["text-embedding-3-small"]["input"]
        input_cost = (self.input_tokens / 1000) * COSTS["gpt-4o"]["input"]
        output_cost = (self.output_tokens / 1000) * COSTS["gpt-4o"]["output"]
        
        total_dollars = embedding_cost + input_cost + output_cost
        return int(total_dollars * 10000)  # Convert to micro-cents for precision


class MeteringService:
    """Service for tracking usage and costs."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def record_indexing(
        self,
        user_id: str,
        repo_id: str,
        file_count: int,
        chunk_count: int,
        embedding_tokens: int
    ):
        """Record indexing usage."""
        metrics = UsageMetrics(embedding_tokens=embedding_tokens)
        
        await self._record_event(
            user_id=user_id,
            repo_id=repo_id,
            event_type="repo_indexed",
            metrics=metrics,
            metadata={
                "file_count": file_count,
                "chunk_count": chunk_count
            }
        )
    
    async def record_question(
        self,
        user_id: str,
        repo_id: str,
        input_tokens: int,
        output_tokens: int,
        embedding_tokens: int
    ):
        """Record Q&A usage."""
        metrics = UsageMetrics(
            embedding_tokens=embedding_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        
        await self._record_event(
            user_id=user_id,
            repo_id=repo_id,
            event_type="question_asked",
            metrics=metrics
        )
    
    async def record_pr_review(
        self,
        user_id: str,
        repo_id: str,
        input_tokens: int,
        output_tokens: int,
        files_analyzed: int
    ):
        """Record PR review usage."""
        metrics = UsageMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        
        await self._record_event(
            user_id=user_id,
            repo_id=repo_id,
            event_type="pr_reviewed",
            metrics=metrics,
            metadata={"files_analyzed": files_analyzed}
        )
    
    async def _record_event(
        self,
        user_id: str,
        repo_id: str,
        event_type: str,
        metrics: UsageMetrics,
        metadata: dict = None
    ):
        """Record a usage event."""
        sql = text("""
            INSERT INTO usage_events (
                user_id, repo_id, event_type,
                embedding_tokens, input_tokens, output_tokens,
                estimated_cost_micro_cents, metadata
            ) VALUES (
                :user_id, :repo_id, :event_type,
                :embedding_tokens, :input_tokens, :output_tokens,
                :cost, :metadata
            )
        """)
        
        await self.db.execute(sql, {
            "user_id": user_id,
            "repo_id": repo_id,
            "event_type": event_type,
            "embedding_tokens": metrics.embedding_tokens,
            "input_tokens": metrics.input_tokens,
            "output_tokens": metrics.output_tokens,
            "cost": metrics.estimated_cost_cents(),
            "metadata": metadata or {}
        })
        await self.db.commit()
    
    async def get_user_costs(
        self,
        user_id: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> dict:
        """Get user's usage and costs for a period."""
        sql = text("""
            SELECT 
                event_type,
                COUNT(*) as count,
                SUM(embedding_tokens) as total_embedding_tokens,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(estimated_cost_micro_cents) as total_cost_micro_cents
            FROM usage_events
            WHERE user_id = :user_id
            AND created_at >= COALESCE(:start_date, '2020-01-01')
            AND created_at <= COALESCE(:end_date, NOW())
            GROUP BY event_type
        """)
        
        result = await self.db.execute(sql, {
            "user_id": user_id,
            "start_date": start_date,
            "end_date": end_date
        })
        
        costs = {}
        total_micro_cents = 0
        
        for row in result:
            costs[row.event_type] = {
                "count": row.count,
                "embedding_tokens": row.total_embedding_tokens or 0,
                "input_tokens": row.total_input_tokens or 0,
                "output_tokens": row.total_output_tokens or 0,
                "cost_cents": (row.total_cost_micro_cents or 0) / 100
            }
            total_micro_cents += row.total_cost_micro_cents or 0
        
        costs["total_cost_cents"] = total_micro_cents / 100
        costs["total_cost_dollars"] = total_micro_cents / 10000
        
        return costs
```

---

# 8. ACCEPTANCE CRITERIA (REVISED)

## Week 1: GitHub App + Foundation
- [ ] GitHub App created and can be installed
- [ ] OAuth flow works, JWT issued
- [ ] Repos can be connected
- [ ] Webhooks received and signature verified
- [ ] Repo cloning uses auth header (not URL token)
- [ ] File scanner works, ignores vendor/node_modules

## Week 2: Indexer
- [ ] tree-sitter parses PHP files
- [ ] Symbols extracted with correct line numbers
- [ ] Trigram search finds symbols by partial name
- [ ] Embeddings stored in Qdrant
- [ ] NO file content stored in Postgres
- [ ] Index completes in < 5 min for medium repo

## Week 3: Laravel System Map
- [ ] AST-based route extraction (not regex)
- [ ] Route::resource expands to 7 routes
- [ ] Nested middleware groups stack correctly
- [ ] Nested prefixes combine correctly
- [ ] Migrations parsed with operations
- [ ] Mermaid generated from extracted data

## Week 4: Proof-Carrying Q&A
- [ ] LLM outputs structured JSON
- [ ] Every section has source_ids
- [ ] Invalid source_ids rejected
- [ ] Snippets fetched from GitHub (not stored)
- [ ] Confidence tier (HIGH/MEDIUM/LOW), not percentage
- [ ] "Insufficient evidence" when < 2 sources

## Week 5: High-Precision PR Review
- [ ] Only 6 analyzer categories (not 15+)
- [ ] Exact-match patterns for secrets (GitHub PAT, AWS, Stripe)
- [ ] DROP TABLE/COLUMN flagged
- [ ] Auth middleware removal flagged
- [ ] Lockfile changes noted
- [ ] No generic "SQL injection" or "XSS" patterns
- [ ] < 3 false positives per 100 PRs

## Week 6: Polish + Metering
- [ ] Usage events logged with token counts
- [ ] Costs calculated per event
- [ ] Dashboard shows usage/costs
- [ ] Snippet cache with expiry
- [ ] Soft delete for repos
- [ ] < 3 min to first value for new user

---

# 9. WHAT'S DIFFERENT FROM V1

| Aspect | V1 (Wrong) | V2 (Fixed) |
|--------|------------|------------|
| File storage | `files.content TEXT` | Metadata only, snippets on-demand |
| Search | `to_tsvector('english')` | Trigram + `'simple'` config |
| Route parsing | Regex | AST-based tree-sitter |
| Answer format | "Please cite" | Structured JSON + validation |
| Confidence | Fake 0.6 threshold | Discrete tiers |
| Git auth | Token in URL | Auth header / ASKPASS |
| Analyzers | 15+ patterns | 6 high-precision only |
| Costs | Fantasy | Metered from day 1 |
| Snippets | Stored forever | Cached 1 hour, fetched fresh |

---

**END OF IMPLEMENTATION GUIDE V2**
