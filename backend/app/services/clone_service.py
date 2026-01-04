"""Service for securely cloning Git repositories."""

import asyncio
import logging
import os
import re
import shutil
import stat
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class CloneError(Exception):
    """Error during git clone operation."""
    pass


class CloneService:
    """Service for cloning Git repositories locally with security."""

    TEMP_BASE = "/tmp/codeproof"
    MAX_CLONE_TIME = 300  # 5 minutes timeout
    MAX_REPO_SIZE = 500 * 1024 * 1024  # 500MB limit

    # Patterns to redact from error messages
    TOKEN_PATTERNS = [
        r'ghp_[a-zA-Z0-9]{36,}',
        r'github_pat_[a-zA-Z0-9_]{22,}',
        r'ghu_[a-zA-Z0-9]{36,}',
        r'ghs_[a-zA-Z0-9]{36,}',
        r'gho_[a-zA-Z0-9]{36,}',
        r'xoxb-[a-zA-Z0-9-]+',
        r'xoxp-[a-zA-Z0-9-]+',
        r'AKIA[0-9A-Z]{16}',
        r'sk-[a-zA-Z0-9]{48,}',
        r'glpat-[a-zA-Z0-9_-]{20,}',
    ]

    def __init__(self):
        """Initialize clone service and ensure temp directory exists."""
        os.makedirs(self.TEMP_BASE, exist_ok=True)

    def _sanitize_error(self, error: str) -> str:
        """Remove tokens and sensitive data from error messages."""
        sanitized = error
        for pattern in self.TOKEN_PATTERNS:
            sanitized = re.sub(pattern, '[REDACTED]', sanitized)
        sanitized = re.sub(r'://[^:]+:[^@]+@', '://[REDACTED]@', sanitized)
        return sanitized

    def _parse_github_url(self, url: str) -> tuple[str, str]:
        """Parse GitHub URL to extract owner and repo."""
        patterns = [
            r"github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$",
            r"github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1), match.group(2).rstrip('.git')
        raise CloneError(f"Invalid GitHub URL format: {url}")

    async def clone_repo(
        self,
        repo_url: str,
        branch: str | None = None,
        token: str | None = None,
    ) -> tuple[str, str]:
        """
        Clone a repository to temp directory.
        
        Security: Token is NEVER put in URL. Uses GIT_ASKPASS for auth.
        """
        try:
            owner, repo = self._parse_github_url(repo_url)
        except Exception as e:
            raise CloneError(self._sanitize_error(str(e)))

        clone_id = str(uuid.uuid4())[:8]
        clone_path = os.path.join(self.TEMP_BASE, f"{owner}-{repo}-{clone_id}")
        clone_url = f"https://github.com/{owner}/{repo}.git"

        # Build command as list (safe - no shell injection)
        cmd = ["git", "clone", "--depth", "1"]
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([clone_url, clone_path])

        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"

        askpass_script_path = None

        try:
            if token:
                askpass_script_path = await self._create_askpass_script(token)
                env["GIT_ASKPASS"] = askpass_script_path

            logger.info(f"Cloning {owner}/{repo} to {clone_path}")

            # Using create_subprocess_exec (safe - args as list, no shell)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.MAX_CLONE_TIME,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                self.cleanup(clone_path)
                raise CloneError(f"Clone timed out after {self.MAX_CLONE_TIME} seconds")

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace')
                self.cleanup(clone_path)
                raise CloneError(f"Git clone failed: {self._sanitize_error(error_msg)}")

            repo_size = self._get_dir_size(clone_path)
            if repo_size > self.MAX_REPO_SIZE:
                self.cleanup(clone_path)
                raise CloneError(
                    f"Repository too large: {repo_size / 1024 / 1024:.1f}MB "
                    f"(max {self.MAX_REPO_SIZE / 1024 / 1024:.0f}MB)"
                )

            commit_sha = await self._get_commit_sha(clone_path)
            logger.info(f"Cloned {owner}/{repo} at {commit_sha[:8]} ({repo_size / 1024 / 1024:.1f}MB)")

            return clone_path, commit_sha

        finally:
            if askpass_script_path and os.path.exists(askpass_script_path):
                os.remove(askpass_script_path)

    async def _create_askpass_script(self, token: str) -> str:
        """Create temporary GIT_ASKPASS script that echoes the token."""
        fd, script_path = tempfile.mkstemp(prefix="git_askpass_", suffix=".sh")

        try:
            script_content = f'#!/bin/bash\necho "{token}"\n'
            os.write(fd, script_content.encode())
            os.close(fd)
            os.chmod(script_path, stat.S_IRWXU)
            return script_path
        except Exception:
            os.close(fd)
            if os.path.exists(script_path):
                os.remove(script_path)
            raise

    async def _get_commit_sha(self, repo_path: str) -> str:
        """Get the current commit SHA."""
        process = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "HEAD",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        return stdout.decode().strip()

    def _get_dir_size(self, path: str) -> int:
        """Get total size of directory in bytes."""
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            if '.git' in dirpath:
                continue
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total += os.path.getsize(filepath)
                except OSError:
                    pass
        return total

    def cleanup(self, clone_path: str) -> None:
        """Delete cloned repository."""
        if not clone_path or not clone_path.startswith(self.TEMP_BASE):
            logger.warning(f"Refusing to delete path outside temp base: {clone_path}")
            return

        if os.path.exists(clone_path):
            try:
                shutil.rmtree(clone_path)
                logger.info(f"Cleaned up {clone_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup {clone_path}: {e}")

    def cleanup_old(self, max_age_seconds: int = 3600) -> int:
        """Delete repositories older than max_age. Returns count deleted."""
        if not os.path.exists(self.TEMP_BASE):
            return 0

        cutoff_time = datetime.now() - timedelta(seconds=max_age_seconds)
        deleted_count = 0

        for item in os.listdir(self.TEMP_BASE):
            item_path = os.path.join(self.TEMP_BASE, item)
            if not os.path.isdir(item_path):
                continue

            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(item_path))
                if mtime < cutoff_time:
                    shutil.rmtree(item_path)
                    logger.info(f"Cleaned up old repo: {item}")
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to check/cleanup {item_path}: {e}")

        return deleted_count

    def list_cloned_repos(self) -> list[dict]:
        """List all currently cloned repositories."""
        if not os.path.exists(self.TEMP_BASE):
            return []

        repos = []
        for item in os.listdir(self.TEMP_BASE):
            item_path = os.path.join(self.TEMP_BASE, item)
            if os.path.isdir(item_path):
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(item_path))
                    size = self._get_dir_size(item_path)
                    repos.append({
                        "name": item,
                        "path": item_path,
                        "modified": mtime.isoformat(),
                        "size_mb": round(size / 1024 / 1024, 2),
                    })
                except Exception:
                    pass

        return repos
