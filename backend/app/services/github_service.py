"""GitHub service with secure ASKPASS cloning."""

import hashlib
import hmac
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

from app.config import get_settings

settings = get_settings()


@dataclass
class GitHubUser:
    """GitHub user data from OAuth."""

    id: int
    login: str
    email: str | None
    avatar_url: str | None


@dataclass
class GitHubRepo:
    """GitHub repository data."""

    id: int
    name: str
    full_name: str
    owner: str
    private: bool
    default_branch: str


class GitHubService:
    """Service for GitHub API operations with secure authentication.

    Key security features (per V2 architecture):
    - Uses ASKPASS for git cloning (no tokens in URLs)
    - Sanitizes errors to prevent token leakage
    - Verifies webhook signatures with constant-time comparison
    """

    GITHUB_API_BASE = "https://api.github.com"
    GITHUB_OAUTH_URL = "https://github.com/login/oauth"

    def __init__(self):
        self.app_id = settings.github_app_id
        self.private_key = settings.github_app_private_key
        self.client_id = settings.github_client_id
        self.client_secret = settings.github_client_secret
        self.webhook_secret = settings.github_webhook_secret
        self._installation_tokens: dict[int, tuple[str, float]] = {}

    # =========================================================================
    # OAuth Flow
    # =========================================================================

    def get_oauth_url(self, state: str) -> str:
        """Get the GitHub OAuth authorization URL.

        Args:
            state: Random state string for CSRF protection

        Returns:
            OAuth authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": f"{settings.api_url}/auth/callback",
            "scope": "user:email",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.GITHUB_OAUTH_URL}/authorize?{query}"

    async def exchange_code(self, code: str) -> str:
        """Exchange OAuth code for access token.

        Args:
            code: OAuth authorization code

        Returns:
            Access token
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.GITHUB_OAUTH_URL}/access_token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise ValueError(f"OAuth error: {data.get('error_description', data['error'])}")

            return data["access_token"]

    async def get_user(self, access_token: str) -> GitHubUser:
        """Get user info from GitHub.

        Args:
            access_token: OAuth access token

        Returns:
            GitHubUser with user details
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GITHUB_API_BASE}/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            data = response.json()

            # Get primary email if not public
            email = data.get("email")
            if not email:
                emails_response = await client.get(
                    f"{self.GITHUB_API_BASE}/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                if emails_response.status_code == 200:
                    emails = emails_response.json()
                    primary = next((e for e in emails if e.get("primary")), None)
                    if primary:
                        email = primary["email"]

            return GitHubUser(
                id=data["id"],
                login=data["login"],
                email=email,
                avatar_url=data.get("avatar_url"),
            )

    # =========================================================================
    # GitHub App Authentication
    # =========================================================================

    def _create_app_jwt(self) -> str:
        """Create a JWT for GitHub App authentication.

        Returns:
            JWT token for app authentication
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # 1 minute in the past for clock drift
            "exp": now + (10 * 60),  # 10 minutes
            "iss": self.app_id,
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def get_installation_token(self, installation_id: int) -> str:
        """Get an installation access token for API calls.

        Args:
            installation_id: GitHub App installation ID

        Returns:
            Installation access token
        """
        # Check cache
        cached = self._installation_tokens.get(installation_id)
        if cached:
            token, expires = cached
            if time.time() < expires - 300:  # 5 min buffer
                return token

        # Get new token
        app_jwt = self._create_app_jwt()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            data = response.json()

            token = data["token"]
            # Parse expiry (ISO format)
            expires_at = data.get("expires_at", "")
            # Simple parse - tokens last 1 hour
            expires = time.time() + 3600

            self._installation_tokens[installation_id] = (token, expires)
            return token

    # =========================================================================
    # Repository Operations
    # =========================================================================

    async def list_installations(self, access_token: str) -> list[dict]:
        """List user's GitHub App installations.

        Args:
            access_token: User's OAuth access token

        Returns:
            List of installations
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GITHUB_API_BASE}/user/installations",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            return response.json().get("installations", [])

    async def list_installation_repos(self, installation_id: int) -> list[GitHubRepo]:
        """List repositories accessible to an installation.

        Args:
            installation_id: GitHub App installation ID

        Returns:
            List of accessible repositories
        """
        token = await self.get_installation_token(installation_id)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GITHUB_API_BASE}/installation/repositories",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()

            repos = []
            for repo in response.json().get("repositories", []):
                repos.append(
                    GitHubRepo(
                        id=repo["id"],
                        name=repo["name"],
                        full_name=repo["full_name"],
                        owner=repo["owner"]["login"],
                        private=repo["private"],
                        default_branch=repo.get("default_branch", "main"),
                    )
                )
            return repos

    # =========================================================================
    # Secure Git Cloning (ASKPASS method)
    # =========================================================================

    def _create_askpass_script(self, token: str) -> str:
        """Create a temporary ASKPASS script for git authentication.

        This is the secure way to pass tokens to git without:
        - Leaking via shell history
        - Showing in process lists
        - Being logged in error messages

        Args:
            token: GitHub access token

        Returns:
            Path to temporary script
        """
        # Create temp file
        fd, path = tempfile.mkstemp(suffix=".sh", prefix="git-askpass-")
        try:
            # Write script content
            script = f'#!/bin/bash\necho "{token}"\n'
            os.write(fd, script.encode())
        finally:
            os.close(fd)

        # Make executable
        os.chmod(path, stat.S_IRWXU)
        return path

    def _sanitize_error(self, error: str) -> str:
        """Sanitize error message to remove tokens.

        Args:
            error: Raw error message

        Returns:
            Sanitized error message
        """
        # Redact various token patterns
        error = re.sub(r"ghp_[a-zA-Z0-9]+", "[REDACTED]", error)
        error = re.sub(r"ghu_[a-zA-Z0-9]+", "[REDACTED]", error)
        error = re.sub(r"ghs_[a-zA-Z0-9]+", "[REDACTED]", error)
        error = re.sub(r"x-access-token:[^@]+@", "x-access-token:[REDACTED]@", error)
        return error

    async def clone_repo(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        target_dir: str,
        ref: str | None = None,
    ) -> None:
        """Clone a repository using secure ASKPASS method.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            target_dir: Target directory for clone
            ref: Optional branch/tag to checkout
        """
        token = await self.get_installation_token(installation_id)
        askpass_script = self._create_askpass_script(token)

        try:
            # Use HTTPS URL (no token in URL)
            clone_url = f"https://github.com/{owner}/{repo}.git"

            # Set up environment
            env = os.environ.copy()
            env["GIT_ASKPASS"] = askpass_script
            env["GIT_TERMINAL_PROMPT"] = "0"

            # Build command
            cmd = ["git", "clone", "--depth", "1"]
            if ref:
                cmd.extend(["--branch", ref])
            cmd.extend([clone_url, target_dir])

            # Execute
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                error = self._sanitize_error(result.stderr.decode())
                raise RuntimeError(f"Git clone failed: {error}")

        finally:
            # Clean up askpass script
            try:
                os.remove(askpass_script)
            except OSError:
                pass

    # =========================================================================
    # File Content Fetching
    # =========================================================================

    async def get_file_content(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        path: str,
        ref: str | None = None,
    ) -> str:
        """Get file content from GitHub API.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            path: File path
            ref: Optional commit/branch reference

        Returns:
            File content as string
        """
        token = await self.get_installation_token(installation_id)
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        if ref:
            url += f"?ref={ref}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.raw",
                },
            )
            response.raise_for_status()
            return response.text

    async def get_file_lines(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        path: str,
        start_line: int,
        end_line: int,
        ref: str | None = None,
    ) -> str:
        """Get specific lines from a file.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            path: File path
            start_line: Start line (1-indexed)
            end_line: End line (1-indexed, inclusive)
            ref: Optional commit reference

        Returns:
            Content of specified lines
        """
        content = await self.get_file_content(installation_id, owner, repo, path, ref)
        lines = content.split("\n")
        selected = lines[start_line - 1 : end_line]
        return "\n".join(selected)

    # =========================================================================
    # Webhook Verification
    # =========================================================================

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            payload: Raw request body
            signature: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid
        """
        if not signature or not signature.startswith("sha256="):
            return False

        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(f"sha256={expected}", signature)

    # =========================================================================
    # PR Review Posting
    # =========================================================================

    async def get_pr(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> dict[str, Any]:
        """Get PR data.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            pr_number: PR number

        Returns:
            PR data
        """
        token = await self.get_installation_token(installation_id)
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_pr_files(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> list[dict[str, Any]]:
        """Get PR changed files.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            pr_number: PR number

        Returns:
            List of file changes
        """
        token = await self.get_installation_token(installation_id)
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            return response.json()

    async def create_pr_review(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        comments: list[dict[str, Any]] | None = None,
    ) -> dict:
        """Create a PR review with optional inline comments.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            body: Review summary body
            event: APPROVE, REQUEST_CHANGES, or COMMENT
            comments: Optional list of inline comments

        Returns:
            Created review data
        """
        token = await self.get_installation_token(installation_id)
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"

        data: dict[str, Any] = {
            "body": body,
            "event": event,
        }
        if comments:
            data["comments"] = comments

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            return response.json()
