"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, intelligence, pr_reviews, qa, repos, test, webhooks
from app.config import get_settings
from app.database import init_db

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    yield
    # Shutdown


app = FastAPI(
    title="CodeProof API",
    description="AI-powered code review and analysis platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# CORS middleware - allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else settings.cors_origins,
    allow_credentials=False,  # Must be False when using allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(repos.router, prefix="/api/repos", tags=["Repositories"])
app.include_router(qa.router, prefix="/api", tags=["Q&A"])
app.include_router(intelligence.router, prefix="/api", tags=["Repo Intelligence"])
app.include_router(pr_reviews.router, prefix="/api/repos", tags=["PR Reviews"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(test.router, prefix="/test", tags=["Test"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}
