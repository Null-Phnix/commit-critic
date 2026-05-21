"""
Commit Critic - Main CLI Application

High-quality AI-powered tool for analyzing git commit message quality
and generating better commit messages.
"""

import argparse
import sys
from typing import Any, Optional

from git_utils import (
    is_git_repository,
    get_recent_commits,
    get_staged_diff,
    get_staged_stats,
    commit_staged_changes,
    clone_remote_repo,
    cleanup_temp_repo,
    GitError,
)
from llm_client import get_llm_client, LLMError
from prompts import build_critique_prompt, build_generation_prompt
import formatter as fmt


MAX_DIFF_CHARS = 24_000
MAX_COMMIT_MESSAGE_CHARS = 1_000


def ensure_git_repo(repo_path: Optional[str] = None) -> None:
    """Raise a clear error if not inside a git repository."""
    if not is_git_repository(repo_path or "."):
        raise GitError("You must be inside a git repository.")


def normalize_repo_url(repo_url: str) -> str:
    """Accept pasted markdown-style URLs such as <https://github.com/x/y>."""
    return repo_url.strip().strip("<>")


def _score(value: Any) -> int:
    """Coerce model-provided scores into the expected 1-10 range."""
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(score, 10))


def _extract_critique_items(result: Any) -> list[dict]:
    """Handle common JSON shapes returned by different models/providers."""
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]

    if isinstance(result, dict):
        for key in ("commits", "critiques", "results", "analysis"):
            items = result.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]

    return []


def _find_commit(hash_value: str, commits: list[dict]) -> Optional[dict]:
    """Find a commit by exact or prefix hash match."""
    if not hash_value:
        return None

    for commit in commits:
        commit_hash = commit["hash"]
        if commit_hash == hash_value:
            return commit
        if commit_hash.startswith(hash_value) or hash_value.startswith(commit_hash):
            return commit
    return None


def normalize_critiques(result: Any, commits: list[dict]) -> list[dict]:
    """
    Merge model critique data with the original git log data.

    The LLM only needs to return hashes and feedback. The CLI still needs the
    original message for display and statistics, so we join the two here.
    """
    normalized = []
    items = _extract_critique_items(result)

    for index, item in enumerate(items):
        hash_value = str(item.get("hash", "")).strip()
        commit = _find_commit(hash_value, commits)
        if commit is None and index < len(commits):
            commit = commits[index]

        subject = item.get("subject") or (commit or {}).get("subject", "")
        message = item.get("message") or (commit or {}).get("message", subject)
        score = _score(item.get("score"))
        issue = item.get("issue") or item.get("issues")

        normalized.append({
            "hash": hash_value or (commit or {}).get("hash", ""),
            "subject": subject,
            "message": message,
            "score": score,
            "issue": issue or ("None" if score > 6 else "No specific feedback"),
            "suggestion": (
                item.get("suggestion")
                or item.get("better")
                or item.get("better_message")
                or ""
            ),
            "reason": item.get("reason") or item.get("why_good") or "",
        })

    return normalized


def build_commits_text(commits: list[dict]) -> str:
    """Format commits for the critique prompt without losing body text."""
    blocks = []
    for commit in commits:
        message = truncate_for_prompt(
            commit["message"],
            MAX_COMMIT_MESSAGE_CHARS,
            label="Commit message",
        )
        blocks.append(
            f"Hash: {commit['hash']}\n"
            f"Message:\n{message}"
        )
    return "\n\n---\n\n".join(blocks)


def truncate_for_prompt(
    text: str,
    max_chars: int = MAX_DIFF_CHARS,
    label: str = "Diff",
) -> str:
    """Keep prompt size bounded while making truncation explicit to the model."""
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return (
        text[:max_chars].rstrip()
        + f"\n\n[{label} truncated: {omitted} additional characters omitted.]"
    )


def clean_generated_message(message: str) -> str:
    """Remove common model formatting wrappers from a commit message."""
    cleaned = message.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned.strip('"').strip()


def analyze_commits(limit: int = 50, repo_url: Optional[str] = None) -> None:
    """
    Analyze recent commits using the LLM.
    Supports both local and remote repositories.
    """
    temp_repo_path = None

    try:
        if repo_url:
            repo_url = normalize_repo_url(repo_url)
            print(f"Cloning remote repository: {repo_url}")
            temp_repo_path = clone_remote_repo(repo_url, depth=max(limit, 100))
            repo_path = temp_repo_path
        else:
            ensure_git_repo()
            repo_path = None

        print(f"Analyzing last {limit} commits...\n")

        commits = get_recent_commits(limit=limit, repo_path=repo_path)

        if not commits:
            print("No commits found.")
            return

        commits_text = build_commits_text(commits)

        system_prompt, user_prompt = build_critique_prompt(commits_text)

        client = get_llm_client()
        print(f"Provider: {client.get_provider_name()}\n")
        result = client.generate_json(user_prompt, system_prompt)

        critiques = normalize_critiques(result, commits)
        if not critiques:
            raise LLMError("The model did not return usable critique data.")

        fmt.display_analysis_results(critiques)

    finally:
        if temp_repo_path:
            cleanup_temp_repo(temp_repo_path)


def get_changes_summary(diff: str, max_items: int = 5) -> list[str]:
    """
    Create meaningful, human-readable descriptions of the staged changes
    by analyzing the actual diff content.
    """
    lines = diff.splitlines()
    changes = []
    current_file = None
    added_lines = 0
    removed_lines = 0
    has_function_change = False
    has_error_handling = False
    has_tests = False

    i = 0
    while i < len(lines) and len(changes) < max_items:
        line = lines[i]

        if line.startswith("diff --git"):
            # Process previous file
            if current_file and (added_lines + removed_lines) > 0:
                desc = describe_change(
                    current_file, added_lines, removed_lines,
                    has_function_change, has_error_handling, has_tests
                )
                if desc:
                    changes.append(desc)

            # Start new file
            parts = line.split()
            if len(parts) >= 3:
                current_file = parts[2].replace("a/", "").replace("b/", "")
            added_lines = 0
            removed_lines = 0
            has_function_change = False
            has_error_handling = False
            has_tests = bool(current_file and (
                "test" in current_file.lower() or "spec" in current_file.lower()
            ))

        elif line.startswith("+") and not line.startswith("+++"):
            added_lines += 1
            if "def " in line or "function " in line:
                has_function_change = True
            if "error" in line.lower() or "except" in line.lower():
                has_error_handling = True
            if current_file and (
                "test" in current_file.lower() or "spec" in current_file.lower()
            ):
                has_tests = True

        elif line.startswith("-") and not line.startswith("---"):
            removed_lines += 1

        i += 1

    # Process last file
    if current_file and (added_lines + removed_lines) > 0:
        desc = describe_change(
            current_file, added_lines, removed_lines,
            has_function_change, has_error_handling, has_tests
        )
        if desc:
            changes.append(desc)

    if not changes:
        changes.append("Modified staged files")

    return changes


def describe_change(filename: str, added: int, removed: int,
                    has_function: bool, has_error: bool, has_tests: bool) -> str:
    """Generate a human-readable description of the change."""
    if has_tests:
        return f"Updated tests in {filename}"
    if has_error:
        return f"Improved error handling in {filename}"
    if has_function and added > removed:
        return f"Added new functionality in {filename}"
    if removed > added:
        return f"Simplified {filename} by removing logic"
    if added > 0 and removed == 0:
        return f"Added new logic to {filename}"
    return f"Updated {filename}"


def interactive_write(commit: bool = False, repo_path: Optional[str] = None) -> None:
    """
    Generate a commit message from staged changes.
    Matches the challenge spec output style as closely as possible.
    """
    ensure_git_repo(repo_path)

    diff = get_staged_diff(repo_path=repo_path)
    if not diff:
        print("No staged changes detected. Stage changes with git add before using --write.")
        return

    stats = get_staged_stats(repo_path=repo_path)
    files_changed = stats["files_changed"]
    insertions = stats["insertions"]
    deletions = stats["deletions"]

    print(f"Analyzing staged changes... ({files_changed} files changed, +{insertions} -{deletions} lines)\n")

    changes = get_changes_summary(diff)
    print("Changes detected:")
    for change in changes:
        print(f"- {change}")
    print()

    system_prompt, user_prompt = build_generation_prompt(
        diff=truncate_for_prompt(diff),
        files_changed=files_changed,
        insertions=insertions,
        deletions=deletions,
    )

    client = get_llm_client()
    print(f"Provider: {client.get_provider_name()}\n")
    suggestion = clean_generated_message(client.generate(user_prompt, system_prompt))

    if not suggestion:
        raise LLMError("The model returned an empty commit message.")

    fmt.print_suggested_message(suggestion)

    try:
        choice = input("Press Enter to accept, or type your own message:\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return

    final_message = suggestion if choice == "" else choice

    if commit:
        output = commit_staged_changes(final_message, repo_path=repo_path)
        print("\nCreated commit:")
        print(output)
    else:
        print("\nCommit message accepted:")
        print(final_message)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI-powered commit message critic and generator."
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze recent commits and critique their quality",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Generate a commit message from staged changes",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="With --write, create a git commit using the accepted message",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of commits to analyze (default: 50)",
    )
    parser.add_argument(
        "--repo",
        "--url",
        dest="repo_url",
        help="Analyze a remote repository (e.g. https://github.com/user/repo.git)",
    )

    args = parser.parse_args()

    if args.analyze and args.write:
        parser.error("--analyze and --write cannot be used together")
    if args.commit and not args.write:
        parser.error("--commit can only be used with --write")

    try:
        if args.analyze:
            analyze_commits(limit=args.limit, repo_url=args.repo_url)
        elif args.write:
            interactive_write(commit=args.commit)
        else:
            parser.print_help()
        return 0
    except (GitError, LLMError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
