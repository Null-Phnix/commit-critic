"""
Git Utilities Module

Provides clean, reliable access to git repository information using subprocess.
Supports both local repositories and remote repositories (via temporary clone).
"""

import os
import shutil
import subprocess
import tempfile
from typing import Optional


class GitError(RuntimeError):
    """Raised when a git command fails or the repository is in an invalid state."""
    pass


def _run_git(args: list[str], cwd: Optional[str] = None) -> str:
    """Execute a git command safely."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(
            f"Git command failed: git {' '.join(args)}\n{e.stderr.strip()}"
        ) from e


def is_git_repository(path: str = ".") -> bool:
    """Check whether the given path is inside a git repository."""
    try:
        _run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
        return True
    except GitError:
        return False


def get_repo_root(path: str = ".") -> str:
    """Return the absolute path to the root of the current git repository."""
    return _run_git(["rev-parse", "--show-toplevel"], cwd=path)


def get_recent_commits(limit: int = 50, repo_path: Optional[str] = None) -> list[dict]:
    """
    Retrieve recent commits from the repository.

    Args:
        limit: Number of commits to fetch.
        repo_path: Optional path to a different repository (for remote support).

    Returns:
        List of commit dictionaries.
    """
    if limit < 1:
        raise GitError("Commit limit must be at least 1")

    cwd = repo_path or os.getcwd()

    if not is_git_repository(cwd):
        raise GitError("Not inside a git repository")

    field_separator = "\x1f"
    record_separator = "\x1e"

    try:
        output = _run_git([
            "log",
            f"-{limit}",
            f"--pretty=format:%x1e%h%x1f%s%x1f%b",
        ], cwd=cwd)
    except GitError as error:
        message = str(error)
        if "does not have any commits yet" in message or "your current branch" in message:
            return []
        raise

    commits = []
    for record in output.split(record_separator):
        record = record.strip()
        if not record:
            continue

        parts = record.split(field_separator, 2)
        if len(parts) < 2:
            continue

        commit_hash = parts[0].strip()
        subject = parts[1].strip()
        body = parts[2].strip() if len(parts) > 2 else ""

        full_message = subject
        if body:
            full_message += "\n\n" + body

        commits.append({
            "hash": commit_hash,
            "subject": subject,
            "body": body,
            "message": full_message.strip()
        })

    return commits


def get_staged_diff(repo_path: Optional[str] = None) -> str:
    """Return the diff of currently staged changes."""
    cwd = repo_path or os.getcwd()

    if not is_git_repository(cwd):
        raise GitError("Not inside a git repository")

    return _run_git(["diff", "--cached"], cwd=cwd)


def get_staged_stats(repo_path: Optional[str] = None) -> dict:
    """Return structured statistics about staged changes."""
    cwd = repo_path or os.getcwd()

    if not is_git_repository(cwd):
        return {"files_changed": 0, "insertions": 0, "deletions": 0}

    try:
        output = _run_git(["diff", "--cached", "--shortstat"], cwd=cwd)
        if not output:
            return {"files_changed": 0, "insertions": 0, "deletions": 0}

        stats = {"files_changed": 0, "insertions": 0, "deletions": 0}
        parts = [p.strip() for p in output.split(",")]

        for part in parts:
            if "file" in part:
                stats["files_changed"] = int(part.split()[0])
            elif "insertion" in part:
                stats["insertions"] = int(part.split()[0])
            elif "deletion" in part:
                stats["deletions"] = int(part.split()[0])

        return stats
    except Exception:
        return {"files_changed": 0, "insertions": 0, "deletions": 0}


def commit_staged_changes(message: str, repo_path: Optional[str] = None) -> str:
    """
    Create a git commit from the currently staged changes.

    The message is written to a temporary file and passed via `git commit -F`
    so multi-line commit messages are handled without shell quoting issues.
    """
    cwd = repo_path or os.getcwd()
    cleaned_message = message.strip()

    if not cleaned_message:
        raise GitError("Commit message cannot be empty")
    if not is_git_repository(cwd):
        raise GitError("Not inside a git repository")
    if not get_staged_diff(repo_path=cwd):
        raise GitError("No staged changes to commit")

    message_file = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            prefix="commit_critic_message_",
        ) as file:
            file.write(cleaned_message)
            file.write("\n")
            message_file = file.name

        return _run_git(["commit", "-F", message_file], cwd=cwd)
    finally:
        if message_file and os.path.exists(message_file):
            os.unlink(message_file)


# =============================================================================
# Remote Repository Support
# =============================================================================

def clone_remote_repo(url: str, depth: int = 100) -> str:
    """
    Clone a remote repository into a temporary directory.

    Returns the path to the cloned repository.
    """
    temp_dir = tempfile.mkdtemp(prefix="commit_critic_")

    try:
        subprocess.run(
            ["git", "clone", "--depth", str(max(depth, 1)), url, temp_dir],
            capture_output=True,
            text=True,
            check=True,
        )
        return temp_dir
    except subprocess.CalledProcessError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise GitError(f"Failed to clone repository: {e.stderr}") from e


def cleanup_temp_repo(path: str) -> None:
    """Remove a temporary cloned repository."""
    if path and os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
