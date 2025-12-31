"""GitHub webhook handlers."""

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.repository import Repository
from app.services.github_service import GitHubService

router = APIRouter()

github_service = GitHubService()


@router.post("/github")
async def github_webhook(
    request: Request,
    db: DbSession,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
):
    """Handle GitHub webhooks.

    Supported events:
    - installation: App installed/uninstalled
    - push: Code pushed (triggers re-indexing)
    - pull_request: PR opened/updated (triggers review)
    """
    # Get raw payload for signature verification
    payload = await request.body()

    # Verify signature (constant-time comparison)
    if not github_service.verify_webhook_signature(payload, x_hub_signature_256 or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse payload
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    # Route by event type
    event = x_github_event or ""

    if event == "installation":
        return await handle_installation(data, db)
    elif event == "push":
        return await handle_push(data, db)
    elif event == "pull_request":
        return await handle_pull_request(data, db)
    elif event == "ping":
        return {"status": "pong"}
    else:
        # Log unknown event but don't fail
        return {"status": "ignored", "event": event}


async def handle_installation(data: dict, db):
    """Handle installation/uninstallation events."""
    action = data.get("action")
    installation_id = data.get("installation", {}).get("id")

    if action == "created":
        # App was installed - repos will be added when user connects them
        return {"status": "ok", "action": "installed", "installation_id": installation_id}

    elif action == "deleted":
        # App was uninstalled - mark repos as disconnected
        if installation_id:
            result = await db.execute(
                select(Repository).where(
                    Repository.github_installation_id == installation_id
                )
            )
            repos = result.scalars().all()
            from datetime import datetime

            for repo in repos:
                repo.deleted_at = datetime.utcnow()
            await db.commit()

        return {"status": "ok", "action": "uninstalled", "installation_id": installation_id}

    return {"status": "ignored", "action": action}


async def handle_push(data: dict, db):
    """Handle push events - trigger re-indexing."""
    repo_data = data.get("repository", {})
    github_repo_id = repo_data.get("id")

    if not github_repo_id:
        return {"status": "ignored", "reason": "no repository id"}

    # Find connected repository
    result = await db.execute(
        select(Repository)
        .where(Repository.github_repo_id == github_repo_id)
        .where(Repository.deleted_at.is_(None))
    )
    repo = result.scalar_one_or_none()

    if not repo:
        return {"status": "ignored", "reason": "repository not connected"}

    # Check if push is to default branch
    ref = data.get("ref", "")
    default_branch = repo.default_branch
    if not ref.endswith(f"/{default_branch}"):
        return {"status": "ignored", "reason": "not default branch"}

    # Queue re-indexing
    repo.index_status = "pending"
    await db.commit()

    # TODO: Trigger Celery task
    # from app.tasks.index_repo import index_repository
    # index_repository.delay(str(repo.id))

    return {"status": "ok", "action": "reindex_queued", "repo_id": str(repo.id)}


async def handle_pull_request(data: dict, db):
    """Handle pull request events - trigger review."""
    action = data.get("action")
    pr_data = data.get("pull_request", {})
    repo_data = data.get("repository", {})
    github_repo_id = repo_data.get("id")

    # Only process opened and synchronize events
    if action not in ("opened", "synchronize"):
        return {"status": "ignored", "reason": f"action {action} not handled"}

    if not github_repo_id:
        return {"status": "ignored", "reason": "no repository id"}

    # Find connected repository
    result = await db.execute(
        select(Repository)
        .where(Repository.github_repo_id == github_repo_id)
        .where(Repository.deleted_at.is_(None))
    )
    repo = result.scalar_one_or_none()

    if not repo:
        return {"status": "ignored", "reason": "repository not connected"}

    # Check if indexed
    if repo.index_status != "ready":
        return {"status": "ignored", "reason": "repository not indexed"}

    # Extract PR info
    pr_number = pr_data.get("number")
    pr_title = pr_data.get("title")
    head_sha = pr_data.get("head", {}).get("sha")
    base_sha = pr_data.get("base", {}).get("sha")

    # TODO: Create PR review record and trigger analysis
    # from app.tasks.review_pr import review_pull_request
    # review_pull_request.delay(
    #     str(repo.id),
    #     pr_number,
    #     pr_title,
    #     head_sha,
    #     base_sha,
    # )

    return {
        "status": "ok",
        "action": "review_queued",
        "repo_id": str(repo.id),
        "pr_number": pr_number,
    }
