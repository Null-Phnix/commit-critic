# Design Notes

## What The Tool Does

Commit Critic has two workflows:

- `--analyze` reads recent Git commit messages and asks an LLM to score them, explain weaknesses, and suggest clearer alternatives.
- `--write` reads `git diff --staged` and asks an LLM to produce a concise commit message. With `--commit`, the tool creates the commit after confirmation.

The key design choice is that Git remains the source of truth. The LLM is used for judgment and language, while deterministic code handles repository access, staged diffs, output formatting, and safety checks.

## Architecture

- `commit_critic.py` owns CLI parsing and workflow orchestration.
- `git_utils.py` wraps Git subprocess calls and keeps shell quoting out of the application.
- `llm_client.py` exposes a small provider interface for Ollama and OpenAI-compatible APIs.
- `prompts.py` keeps prompt templates versioned separately from workflow code.
- `formatter.py` keeps terminal output consistent and easy to scan.

The code intentionally uses the Python standard library for Git operations instead of GitPython. The required Git commands are simple, and subprocess calls make the behavior close to what developers already use in the terminal.

## LLM Strategy

Analysis mode asks for structured JSON so the CLI can compute stats and render consistent output. The prompt requests a single JSON object with a `commits` array because OpenAI-compatible JSON mode expects an object at the top level.

The parser still accepts a few common alternate shapes, such as a top-level array, because smaller or local models may not perfectly follow instructions. This tolerance is limited to response shape; scoring and critique still come from the model.

Write mode asks for plain text because the desired output is a commit message, not a data structure. The CLI strips common Markdown code fences in case a model wraps the answer.

Large diffs and long commit bodies are truncated before prompting, with an explicit truncation marker. This avoids silently dropping context and makes the model aware that it is seeing a partial diff.

## Safety And UX

`--write` only reads staged changes. It does not fall back to unstaged changes, because the challenge specifically asks for `git diff --staged` and because staged changes represent what the user intends to commit.

Creating a commit is opt-in through `--write --commit`. The default `--write` flow prints the accepted message but does not mutate the repository. When `--commit` is used, the message is written to a temporary file and passed to `git commit -F`, which safely handles multi-line commit messages without shell quoting.

Remote repository analysis clones into a temporary directory and cleans it up afterward. The local working tree is not modified.

## Testing Strategy

Unit tests avoid live LLM calls so they are deterministic and can run without credentials. The tests cover:

- Git log parsing, including commit bodies.
- Empty repositories.
- Staged-only diff behavior.
- Staged stats parsing.
- Multi-line commit creation in a temporary repository.
- LLM critique normalization.
- Safe suggestion-only write mode.
- Opt-in commit creation through the interactive workflow.

Live provider behavior is best verified with smoke tests because model output quality and API availability are external dependencies.

## Tradeoffs

This implementation does not add a TUI framework, database, background service, or persistent scoring history. Those would add complexity without improving the core challenge. The current scope favors a small, inspectable developer tool with clear boundaries and enough polish to be used from a real terminal.

Future improvements could include richer diff summarization, configurable scoring rubrics, output as JSON for CI use, and optional commit message linting before calling the LLM.

## Interview Talk Track

The project separates deterministic tooling from probabilistic model behavior. Git operations, safety checks, and display logic are regular Python code. The LLM is isolated behind a provider interface and used only where language judgment is useful. Tests cover the deterministic core, while live smoke tests validate provider integration.
