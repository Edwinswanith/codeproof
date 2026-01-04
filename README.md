# CodeProof

An AI-powered code review SaaS platform that provides intelligent code analysis, Q&A with citations, and automated PR reviews with high-precision issue detection.

## Features

- **Q&A with Citations**: Ask questions about your codebase and get proof-carrying answers with exact source references
- **PR Analysis**: High-precision PR review that flags only confident issues including:
  - Secret exposure (GitHub PAT, AWS, Stripe, Slack, etc.)
  - Destructive migrations (DROP TABLE/COLUMN)
  - Authentication middleware removal
  - Dependency changes
  - Environment file leaks
  - Private key exposure
- **Code Parsing & Indexing**: 
  - Multi-language AST parsing (Python, JavaScript, TypeScript, PHP)
  - Symbol extraction and indexing (classes, functions, methods)
  - Dependency graph analysis
  - Call graph construction for impact analysis
- **Deep Code Analysis**: Local repository cloning with comprehensive AST-based analysis
- **Codebase Documentation**: AI-generated documentation for codebases
- **Compliance Analysis**: Automated compliance checking with regulations and standards
- **System Maps**: Generate architecture diagrams from routes and models (coming soon)
- **Vector Search**: Semantic code search powered by embeddings and Qdrant
- **GitHub Integration**: Secure repository cloning and webhook-based PR reviews

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Primary database with asyncpg driver
- **Qdrant** - Vector database for semantic code search
- **Redis** - Caching and Celery task queue
- **Celery** - Asynchronous task processing
- **Alembic** - Database migrations
- **Tree-sitter** - Code parsing for multiple languages (Python, JavaScript, TypeScript, PHP)
- **OpenAI/Gemini** - LLM integration for code analysis

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe JavaScript
- **TailwindCSS** - Utility-first CSS framework
- **Radix UI** - Accessible component primitives
- **Zustand** - State management

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 16+ (or use Docker)
- Redis (or use Docker)
- Qdrant (or use Docker)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Edwinswanith/codeproof.git
cd codeproof
```

### 2. Backend Setup

```bash
cd backend

# Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### 3. Environment Configuration

Create a `.env` file in the `backend` directory:

```env
# Application
APP_ENV=development
APP_DEBUG=true
SECRET_KEY=your-secret-key-here
API_URL=http://localhost:8000

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/codeproof
DATABASE_POOL_SIZE=10

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=code_embeddings

# GitHub App
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_WEBHOOK_SECRET=
GITHUB_TOKEN=

# LLM
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
GEMINI_EMBEDDING_MODEL=text-embedding-004

# OpenAI (alternative)
OPENAI_API_KEY=

# CORS (comma-separated for production)
CORS_ORIGINS=http://localhost:3000
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create environment file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```

## Running the Application

### Start Infrastructure Services

```bash
cd backend
docker-compose up -d db redis qdrant
```

This starts:
- PostgreSQL on port 5432
- Redis on port 6379
- Qdrant on port 6333

### Backend

```bash
cd backend

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or on a different port (e.g., 8001)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

The API will be available at:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Frontend

```bash
cd frontend
npm run dev
```

The frontend will be available at http://localhost:3000

## Project Structure

```
codeproof/
├── backend/
│   ├── app/
│   │   ├── analyzers/          # Code analyzers (high-precision PR review)
│   │   ├── api/
│   │   │   └── routes/         # API endpoints
│   │   ├── models/             # SQLAlchemy database models
│   │   ├── parsers/            # Code parsers (tree-sitter)
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # Business logic services
│   │   │   ├── auth_service.py           # Authentication
│   │   │   ├── clone_service.py          # Secure Git repository cloning
│   │   │   ├── codebase_doc_service.py   # AI documentation generation
│   │   │   ├── compliance_service.py     # Compliance analysis
│   │   │   ├── deep_analysis_service.py  # Deep code analysis
│   │   │   ├── embedding_service.py      # Vector embeddings
│   │   │   ├── github_service.py         # GitHub API integration
│   │   │   ├── index_service.py          # Code indexing and search
│   │   │   ├── llm_service.py            # LLM integration
│   │   │   ├── metering_service.py       # Usage tracking
│   │   │   ├── parser_service.py         # AST code parsing
│   │   │   ├── qa_service.py             # Q&A with citations
│   │   │   └── review_service.py         # PR review analysis
│   │   └── tasks/              # Celery tasks
│   ├── migrations/             # Alembic database migrations
│   ├── tests/                  # Test suite
│   ├── docker-compose.yml      # Infrastructure services
│   ├── Dockerfile              # Backend container
│   └── pyproject.toml          # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js app router pages
│   │   ├── components/         # React components
│   │   └── lib/                # Utilities
│   ├── public/                 # Static assets
│   └── package.json            # Node.js dependencies
│
└── README.md
```

## Development

### Backend Commands

```bash
cd backend

# Run tests
pytest
pytest tests/path/to/test.py::test_name  # Run specific test

# Code formatting
black .

# Linting
ruff check .

# Type checking
mypy .

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

### Frontend Commands

```bash
cd frontend

# Development server
npm run dev

# Production build
npm run build

# Start production server
npm start

# Linting
npm run lint
```

## Core Services

### Code Analysis Services
- **ParserService**: Multi-language AST parsing using tree-sitter (Python, JavaScript, TypeScript, PHP)
- **IndexService**: Builds comprehensive code indexes including symbol tables, dependency graphs, and call graphs
- **DeepAnalysisService**: Performs deep code analysis with local repository cloning and AST parsing
- **ReviewService**: High-precision PR review with confidence-based issue detection

### AI & Search Services
- **LLMService**: Google Gemini integration for code analysis and generation
- **EmbeddingService**: Vector embedding generation and semantic code search using Qdrant
- **QAService**: Question-answering with proof-carrying answers and source citations

### Infrastructure Services
- **CloneService**: Secure Git repository cloning with token sanitization and security controls
- **GitHubService**: GitHub API integration with secure authentication
- **CodebaseDocService**: AI-generated documentation for codebases
- **ComplianceService**: Automated compliance analysis with regulations and standards
- **MeteringService**: Usage tracking and cost calculation
- **AuthService**: JWT-based authentication and user management

## API Endpoints

- **Authentication**: `/auth/*`
- **Repositories**: `/api/repos/*`
- **Q&A**: `/api/{repo_id}/ask`
- **PR Reviews**: `/api/repos/{repo_id}/review`
- **Webhooks**: `/webhooks/github`
- **Health Check**: `/health`

See http://localhost:8000/docs for interactive API documentation.

## Database Models

- **User**: User accounts and authentication
- **Repository**: Connected GitHub repositories
- **File**: Source code files
- **Symbol**: Classes, functions, methods
- **Route**: API routes and endpoints
- **Migration**: Database migrations
- **Model**: Data models
- **Answer**: Q&A responses
- **Citation**: Source code references
- **PRReview**: Pull request reviews
- **PRFinding**: Individual review findings
- **UsageEvent**: Usage tracking and metering
- **SnippetCache**: Cached code snippets

## Security

- JWT-based authentication
- GitHub webhook signature verification
- Secure repository cloning with ASKPASS
- Environment variable validation
- CORS configuration for production

## Environment Variables

See `backend/app/config.py` for all available environment variables and their descriptions.

## Status

This project is in active development. See [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) for detailed implementation status.

## License

See [LICENSE](./LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please open an issue on GitHub.

