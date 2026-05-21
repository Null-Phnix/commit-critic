"""
Formatter Module

Provides clean, consistent, and professional terminal output formatting
for the Commit Critic tool, styled to match the challenge requirements.
"""


def print_header(title: str, emoji: str = "") -> None:
    """Print a clean section header with optional emoji."""
    line = "━" * 60
    if emoji:
        print(f"\n{line}")
        print(f"  {emoji} {title}")
        print(f"{line}")
    else:
        print(f"\n{line}")
        print(f"  {title}")
        print(f"{line}")


def _get_display_message(item: dict, max_length: int = 180) -> str:
    """Safely extract a commit message for terminal display."""
    message = (item.get("message") or item.get("subject") or item.get("hash", "")).strip()
    if not message:
        return "Unknown commit"
    if len(message) <= max_length:
        return message
    return message[: max_length - 1].rstrip() + "..."


def _print_commit_message(item: dict) -> None:
    """Print a commit message while preserving useful body formatting."""
    message = _get_display_message(item)
    indented = message.replace("\n", "\n         ")
    print(f'Commit: "{indented}"')


def print_commit_critique(item: dict) -> None:
    """Print a formatted critique for a single commit."""
    _print_commit_message(item)
    print(f"Score:  {item.get('score', '?')}/10")
    print(f"Issue:  {item.get('issue') or item.get('issues') or 'No specific feedback'}")
    if item.get("suggestion"):
        print(f"Better: {item['suggestion']}")
    print()


def print_good_commit(item: dict) -> None:
    """Print a formatted entry for a well-written commit."""
    _print_commit_message(item)
    print(f"Score:  {item.get('score', '?')}/10")
    reason = item.get("reason") or item.get("why_good") or "Clear and descriptive"
    print(f"Why it's good: {reason}")
    print()


def display_analysis_results(critiques: list) -> None:
    """
    Display full analysis results in a style close to the challenge spec.
    """
    bad_commits = [c for c in critiques if c.get("score", 0) <= 6]
    good_commits = [c for c in critiques if c.get("score", 0) > 6]

    if bad_commits:
        print_header("COMMITS THAT NEED WORK", "💩")
        for item in bad_commits:
            print_commit_critique(item)

    if good_commits:
        print_header("WELL-WRITTEN COMMITS", "💎")
        for item in good_commits[:5]:
            print_good_commit(item)

    total = len(critiques)
    avg_score = sum(c.get("score", 0) for c in critiques) / total if total > 0 else 0
    vague_count = len(bad_commits)
    vague_pct = (vague_count / total) * 100 if total > 0 else 0

    one_word_count = sum(1 for c in critiques if len((c.get("subject") or "").split()) == 1)
    one_word_pct = (one_word_count / total) * 100 if total > 0 else 0

    print_header("YOUR STATS", "📊")
    print(f"Average score:    {avg_score:.1f}/10")
    print(f"Vague commits:    {vague_count} ({vague_pct:.0f}%)")
    print(f"One-word commits: {one_word_count} ({one_word_pct:.0f}%)")
    print(f"Total analyzed:   {total}")


def print_suggested_message(message: str) -> None:
    """Print a suggested commit message in a highlighted block."""
    print_header("SUGGESTED COMMIT MESSAGE")
    print(message)
    print()
