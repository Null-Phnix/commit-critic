import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from commit_critic import (
    clean_generated_message,
    interactive_write,
    normalize_critiques,
    normalize_repo_url,
    truncate_for_prompt,
)


class FakeClient:
    def get_provider_name(self):
        return "fake-test-provider"

    def generate(self, prompt, system_prompt=None):
        return "fix(app): add staged greeting"


class CommitCriticTests(unittest.TestCase):
    def test_normalize_critiques_joins_model_feedback_to_messages(self):
        commits = [{
            "hash": "abc1234",
            "subject": "fixed bug",
            "body": "",
            "message": "fixed bug",
        }]
        result = {
            "commits": [{
                "hash": "abc1234",
                "score": "2",
                "issue": "Too vague",
                "suggestion": "fix(auth): handle expired tokens",
                "reason": "Adds scope and behavior.",
            }]
        }

        critiques = normalize_critiques(result, commits)

        self.assertEqual(len(critiques), 1)
        self.assertEqual(critiques[0]["message"], "fixed bug")
        self.assertEqual(critiques[0]["score"], 2)
        self.assertEqual(critiques[0]["issue"], "Too vague")

    def test_normalize_critiques_accepts_legacy_array_shape(self):
        commits = [{
            "hash": "def5678",
            "subject": "feat(api): add caching",
            "body": "",
            "message": "feat(api): add caching",
        }]

        critiques = normalize_critiques([{"hash": "def5678", "score": 9}], commits)

        self.assertEqual(critiques[0]["message"], "feat(api): add caching")
        self.assertEqual(critiques[0]["issue"], "None")

    def test_normalize_repo_url_accepts_markdown_angle_brackets(self):
        self.assertEqual(
            normalize_repo_url("<https://github.com/steel-dev/steel-browser>"),
            "https://github.com/steel-dev/steel-browser",
        )

    def test_truncate_for_prompt_marks_omitted_text(self):
        truncated = truncate_for_prompt("abcdef", max_chars=3)

        self.assertIn("abc", truncated)
        self.assertIn("Diff truncated: 3 additional characters omitted", truncated)

    def test_clean_generated_message_removes_code_fence(self):
        message = clean_generated_message("```text\nfix(app): handle error\n```")

        self.assertEqual(message, "fix(app): handle error")

    def test_interactive_write_suggestion_mode_does_not_commit(self):
        with tempfile.TemporaryDirectory() as repo:
            self._init_repo(repo)
            self._stage_change(repo)

            output = io.StringIO()
            with patch("commit_critic.get_llm_client", return_value=FakeClient()):
                with patch("builtins.input", return_value=""):
                    with contextlib.redirect_stdout(output):
                        interactive_write(commit=False, repo_path=repo)

            latest_subject = self._git(repo, "log", "-1", "--pretty=%s")
            staged_files = self._git(repo, "diff", "--cached", "--name-only")

            self.assertEqual(latest_subject, "feat(app): add greeting")
            self.assertEqual(staged_files, "app.txt")
            self.assertIn("Commit message accepted:", output.getvalue())

    def test_interactive_write_commit_mode_creates_commit(self):
        with tempfile.TemporaryDirectory() as repo:
            self._init_repo(repo)
            self._stage_change(repo)

            output = io.StringIO()
            with patch("commit_critic.get_llm_client", return_value=FakeClient()):
                with patch("builtins.input", return_value=""):
                    with contextlib.redirect_stdout(output):
                        interactive_write(commit=True, repo_path=repo)

            latest_subject = self._git(repo, "log", "-1", "--pretty=%s")
            staged_files = self._git(repo, "diff", "--cached", "--name-only")

            self.assertEqual(latest_subject, "fix(app): add staged greeting")
            self.assertEqual(staged_files, "")
            self.assertIn("Created commit:", output.getvalue())

    def _init_repo(self, repo):
        self._git(repo, "init")
        self._git(repo, "config", "user.email", "test@example.com")
        self._git(repo, "config", "user.name", "Test User")
        with open(os.path.join(repo, "app.txt"), "w", encoding="utf-8") as file:
            file.write("hello\n")
        self._git(repo, "add", "app.txt")
        self._git(repo, "commit", "-m", "feat(app): add greeting")

    def _stage_change(self, repo):
        with open(os.path.join(repo, "app.txt"), "a", encoding="utf-8") as file:
            file.write("next\n")
        self._git(repo, "add", "app.txt")

    def _git(self, repo, *args):
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()


if __name__ == "__main__":
    unittest.main()
