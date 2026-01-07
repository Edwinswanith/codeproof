# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CodeProof is an AI-powered code review SaaS platform for Laravel codebases. It provides:
- **Q&A with Citations**: Ask questions about your codebase and get proof-carrying answers with exact source references
- **PR Analysis**: High-precision PR review that flags only confident issues (secrets, destructive migrations, auth removal)
- **System Maps**: Generate architecture diagrams from Laravel routes and models

## Development Commands

### Backend (FastAPI/Python)
```bash
cd backend

# Setup
poetry install
poetry shell

# Start infrastructure (PostgreSQL, Redis, Qdrant)
docker-compose up -d db redis qdrant

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest
pytest tests/path/to/test.py::test_name  # single test
pytest --cov                              # with coverage

# Linting/formatting
black .
ruff check .
mypy .

# Create new migration
alembic revision --autogenerate -m "description"
```

### Frontend (Next.js)
```bash
cd frontend

# Install and run
npm install
npm run dev      # http://localhost:3000
npm run build
npm run lint
```

### Docker (full stack)
```bash
cd backend
docker-compose up -d
```

## Architecture

### Three-Layer Trust Model

```
DETECTION LAYER (Deterministic - Source of Truth)
├── High-precision analyzers (6 categories only)
├── Exact-match patterns for secrets (GitHub PAT, AWS, Stripe, etc.)
└── Structural analysis (migrations, middleware removal)

RETRIEVAL LAYER (Hybrid Search)
├── Trigram matching on symbols/paths (PostgreSQL pg_trgm)
├── Vector similarity (Qdrant + OpenAI embeddings)
└── Merge + deduplicate results

EXPLANATION LAYER (LLM - Constrained)
├── Must output structured JSON with source_ids
├── Validation rejects invalid source references
└── Falls back to "insufficient evidence" on validation failure

RULE: LLM never detects. LLM never invents file paths or line numbers.
```

### Backend Structure (`backend/app/`)

- **`main.py`**: FastAPI app with CORS, routers, lifespan handler
- **`config.py`**: Pydantic settings with validation for secrets (rejects insecure defaults)
- **`database.py`**: SQLAlchemy async engine + session factory
- **`models/`**: SQLAlchemy models (User, Repository, Symbol, Route, PRReview, Answer, Citation, etc.)
- **`schemas/`**: Pydantic request/response schemas
- **`services/`**:
  - `qa_service.py`: Proof-carrying answer generation with citation validation
  - `review_service.py`: PR analysis using high-precision analyzer
  - `embedding_service.py`: Qdrant vector storage/search
  - `llm_service.py`: Gemini (primary) / OpenAI (fallback) with usage tracking
  - `metering_service.py`: Cost tracking per operation
  - `github_service.py`: GitHub API + secure ASKPASS cloning
  - `auth_service.py`: JWT authentication
  - `index_service.py`: Repository indexing and search
  - `clone_service.py`: Secure Git repository cloning
  - `parser_service.py`: Tree-sitter multi-language parsing
- **`analyzers/high_precision_analyzer.py`**: 6 high-confidence detectors
- **`api/routes/`**: FastAPI routers (auth, repos, qa, pr_reviews, webhooks)
- **`parsers/`**: Tree-sitter based parsers (not yet implemented)
- **`tasks/`**: Celery async tasks (not yet implemented)

### Frontend Structure (`frontend/src/`)

- **`app/`**: Next.js 14 App Router pages
  - `(dashboard)/`: Protected dashboard routes (repositories, ask, pr-reviews, system-map, usage, settings)
- **`components/`**: React components
  - `ui/`: Shadcn/ui primitives (Button, Card, Dialog, etc.)
  - `layout/`: Dashboard layout, Sidebar, Header
  - `code-block.tsx`, `finding-card.tsx`, `source-citation.tsx`: Domain components
- **`lib/utils.ts`**: Utility functions (cn, formatRelativeTime, getSeverityColor)
- **`lib/api.ts`**: Typed API client (repositoryApi, qaApi, authApi, healthApi)

### API Endpoints

| Prefix | Router | Purpose |
|--------|--------|---------|
| `/auth` | `auth.py` | GitHub OAuth, JWT tokens |
| `/api/repos` | `repos.py` | Repository CRUD |
| `/api/{repo_id}/ask` | `qa.py` | Q&A with citations |
| `/api/repos/{repo_id}/review` | `pr_reviews.py` | PR analysis |
| `/webhooks/github` | `webhooks.py` | GitHub webhook handler |
| `/health` | `main.py` | Health check |

## Key Design Decisions

### Q&A Service (`qa_service.py`)
- **Hybrid search**: Trigram (PostgreSQL pg_trgm) + vector (Qdrant) with deduplication
- **Structured LLM output**: JSON schema with `sections[{text, source_ids}]` and `unknowns[]`
- **Citation validation**: Rejects answers referencing non-existent source indices
- **Confidence tiers**: HIGH (3+ citations from 2+ files), MEDIUM (2+), LOW (1), NONE (0 or failed validation)
- **Snippet caching**: Fresh from GitHub API, cached 1 hour in `SnippetCache` table

### High-Precision Analyzer (`high_precision_analyzer.py`)
Only 6 categories with near-100% precision (better to miss than false positive):
1. `secret_exposure`: Exact patterns (ghp_, AKIA, sk_live_, xoxb-, etc.)
2. `migration_destructive`: DROP TABLE/COLUMN detection
3. `auth_middleware_removed`: `->withoutMiddleware('auth')` detection
4. `dependency_changed`: Lockfile modifications
5. `env_leaked`: .env files in commits
6. `private_key_exposed`: PEM blocks

### Configuration (`config.py`)
- **Secure by default**: `secret_key`, `jwt_secret`, `database_url` have no defaults and must be set
- **Validation**: Rejects secrets under 32 chars or matching insecure values
- **Environment**: Loads from `.env` file via pydantic-settings

## What's Not Yet Implemented

See `IMPLEMENTATION_STATUS.md` for full details. Key gaps:
- **Laravel Route Parser**: AST-based tree-sitter parser (regex approach fails on nested groups)
- **Symbol Extractor**: tree-sitter PHP parser for classes/methods
- **Celery Tasks**: Repository indexing and async PR review
- **Frontend API Integration**: Pages exist but don't connect to backend

## Environment Variables

Required in `backend/.env`:
```env
SECRET_KEY=<32+ char secure string>
JWT_SECRET=<32+ char secure string>
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
GEMINI_API_KEY=<your key>
GITHUB_CLIENT_ID=<oauth app>
GITHUB_CLIENT_SECRET=<oauth app>
```

Optional:
```env
OPENAI_API_KEY=<fallback LLM>
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379/0
```

## Testing

Test structure mirrors app structure:
- `tests/test_analyzers/` - Analyzer tests
- `tests/test_api/` - API endpoint tests
- `tests/test_services/` - Service unit tests
- `tests/test_parsers/` - Parser tests
- `tests/test_e2e/` - End-to-end tests

Coverage excludes legacy services not yet integrated (clone_service, codebase_doc_service, compliance_service, deep_analysis_service, parser_service).
