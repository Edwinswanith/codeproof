# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains **product specification documents** for an AI-powered Code Review SaaS Platform. The project is currently in the specification phase, not yet implemented.

**Product Name:** AI CODE REVIEW (Laravel-first code intelligence)
**Promise:** "Ask questions about your Laravel repo and get answers with hard evidence. Generate accurate system maps and catch risky PR changes."

## Repository Structure

```
code_review/
├── main.md                    # Original product spec (features, pricing, competitive analysis)
└── IMPLEMENTATION_GUIDE_V2.md # Technical implementation guide (the primary reference)
```

**Use `IMPLEMENTATION_GUIDE_V2.md` as the primary technical reference** - it contains critical fixes to V1 approaches and production-ready code examples.

## V2 Architecture Principles

```
DETECTION LAYER (Deterministic - Source of Truth)
├── tree-sitter AST parsing (NOT regex)
├── Exact-match patterns only (GitHub PAT, AWS keys, etc.)
└── Structural analysis (route groups, middleware chains)

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

## Critical V2 Fixes (from V1 mistakes)

| Issue | V1 (Wrong) | V2 (Fixed) |
|-------|------------|------------|
| File storage | `files.content TEXT` | Metadata only, snippets on-demand |
| Search | `to_tsvector('english')` | Trigram + `'simple'` config |
| Route parsing | Regex | AST-based tree-sitter |
| Answer format | "Please cite" | Structured JSON + validation |
| Confidence | Fake percentage | Discrete tiers (HIGH/MEDIUM/LOW) |
| Git auth | Token in URL | Auth header / ASKPASS |
| Analyzers | 15+ patterns | 6 high-precision only |
| Costs | Fantasy | Metered from day 1 |

## Tech Stack

**Backend:** Python 3.11+, FastAPI, SQLAlchemy, Celery
**Frontend:** Next.js 14, TypeScript, Tailwind CSS, Shadcn/ui
**AI/ML:** OpenAI API, tree-sitter (AST parsing), Sentence Transformers
**Data:** PostgreSQL (+ pg_trgm extension), Qdrant (vectors), Redis
**Infrastructure:** Docker, GitHub Actions, Vercel, Railway/Render

## Key Implementation Details

### PR Analyzers (6 high-precision only)
- `secret_exposure` - Exact key patterns (GitHub PAT, AWS, Stripe)
- `migration_destructive` - DROP TABLE/COLUMN
- `auth_middleware_removed` - Middleware removal detection
- `dependency_changed` - Lockfile changes
- `env_leaked` - .env in commit
- `private_key_exposed` - PEM blocks

### Route Parsing
Use AST-based tree-sitter parser in `IMPLEMENTATION_GUIDE_V2.md` section 3. Regex fails on nested groups, middleware stacks, and Route::resource expansion.

### Q&A Answers
All answers must be proof-carrying:
- Structured JSON output with `source_ids` per section
- Validation rejects invalid source references
- Snippets fetched fresh from GitHub API (cached 1 hour)
- Confidence tiers: HIGH (5+ sources), MEDIUM (2-4), LOW (1), NONE (0)

## Implementation Guide Sections

1. **Revised Architecture** - Trust model and data flow
2. **Database Schema** - PostgreSQL + Qdrant schemas
3. **AST-Based Route Extraction** - tree-sitter PHP parser
4. **Proof-Carrying Answer Contract** - LLM output validation
5. **High-Precision Analyzers** - 6 detector implementations
6. **Secure GitHub Auth** - ASKPASS method, token handling
7. **Usage Metering** - Cost tracking per operation
8. **Acceptance Criteria** - Week-by-week checklist
