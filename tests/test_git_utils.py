import os
import subprocess
import tempfile
import unittest

from git_utils import (
    GitError,
    commit_staged_changes,
    get_recent_commits,
    get_staged_diff,
    get_staged_stats,
)


class GitUtilsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = self.temp_dir.name
        self._git("init")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test User")

        with open(os.path.join(self.repo, "app.txt"), "w", encoding="utf-8") as file:
            file.write("hello\n")
        self._git("add", "app.txt")
        self._git("commit", "-m", "feat(app): add greeting", "-m", "Initial body line")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, *args):
        subprocess.run(
            ["git", *args],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_get_recent_commits_preserves_body_text(self):
        commits = get_recent_commits(repo_path=self.repo)

        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]["subject"], "feat(app): add greeting")
        self.assertIn("Initial body line", commits[0]["body"])
        self.assertIn("Initial body line", commits[0]["message"])

    def test_get_recent_commits_handles_empty_repository(self):
        with tempfile.TemporaryDirectory() as repo:
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

            self.assertEqual(get_recent_commits(repo_path=repo), [])

    def test_get_staged_diff_does_not_fall_back_to_unstaged_changes(self):
        with open(os.path.join(self.repo, "app.txt"), "a", encoding="utf-8") as file:
            file.write("unstaged\n")

        self.assertEqual(get_staged_diff(repo_path=self.repo), "")

    def test_get_staged_diff_and_stats_report_staged_changes(self):
        with open(os.path.join(self.repo, "app.txt"), "a", encoding="utf-8") as file:
            file.write("staged\n")
        self._git("add", "app.txt")

        diff = get_staged_diff(repo_path=self.repo)
        stats = get_staged_stats(repo_path=self.repo)

        self.assertIn("+staged", diff)
        self.assertEqual(stats["files_changed"], 1)
        self.assertEqual(stats["insertions"], 1)
        self.assertEqual(stats["deletions"], 0)

    def test_commit_staged_changes_creates_multiline_commit(self):
        with open(os.path.join(self.repo, "app.txt"), "a", encoding="utf-8") as file:
            file.write("committed\n")
        self._git("add", "app.txt")

        output = commit_staged_changes(
            "fix(app): persist greeting\n\nCover staged write path.",
            repo_path=self.repo,
        )
        message = subprocess.run(
            ["git", "log", "-1", "--pretty=%s%n%b"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        self.assertIn("fix(app): persist greeting", output)
        self.assertIn("fix(app): persist greeting", message)
        self.assertIn("Cover staged write path.", message)

    def test_commit_staged_changes_rejects_empty_message(self):
        with self.assertRaises(GitError):
            commit_staged_changes("  ", repo_path=self.repo)


if __name__ == "__main__":
    unittest.main()
