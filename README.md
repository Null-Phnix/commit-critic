# Commit Critic

Commit Critic is an AI-powered terminal tool that reviews Git commit message quality and helps developers write clearer commit messages from staged changes.

It was built for the Steel Applied AI coding challenge. The goal is not to replace judgment with an LLM, but to use an LLM where it is useful: critiquing vague commit messages, suggesting more specific alternatives, and summarizing staged diffs into a good commit message.

## Features

- Analyze the last N commits in the current repository.
- Analyze a remote GitHub repository by URL.
- Score commit messages with LLM-generated critique and suggestions.
- Generate a commit message from `git diff --staged`.
- Optionally create the commit with `--write --commit` after user confirmation.
- Supports both Ollama and OpenAI-compatible APIs.

## Requirements

- Python 3.10+
- Git
- One LLM backend:
  - Ollama running locally, or
  - an OpenAI-compatible API key, or
  - a DeepSeek API key

## Installation

```bash
git clone https://github.com/Null-Phnix/commit-critic.git
cd commit-critic
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The challenge examples also work directly:

```bash
python commit_critic.py --analyze
python commit_critic.py --write
```

After installation, use the CLI command:

```bash
commit-critic --help
```

## LLM Configuration

Commit Critic uses Ollama by default:

```bash
export LLM_PROVIDER=ollama
export OLLAMA_MODEL=qwen2.5-coder:14b
commit-critic --analyze
```

For OpenAI or an OpenAI-compatible provider:

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4o-mini
commit-critic --analyze
```

For compatible providers such as OpenRouter, Grok, Together, or a self-hosted gateway, set `OPENAI_BASE_URL`:

```bash
export OPENAI_BASE_URL=https://api.example.com/v1
```

For DeepSeek:

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=...
export DEEPSEEK_MODEL=deepseek-v4-flash
commit-critic --analyze --limit 5
```

`DEEPSEEK_MODEL` defaults to `deepseek-v4-flash`. You can set it to another DeepSeek chat model such as `deepseek-v4-pro` if your API account supports it.

## Usage

Analyze the last 50 commits in the current repository:

```bash
commit-critic --analyze
```

Analyze a custom number of commits:

```bash
commit-critic --analyze --limit 30
```

Analyze a remote repository:

```bash
commit-critic --analyze --url https://github.com/steel-dev/steel-browser
```

Suggest a commit message from staged changes:

```bash
git add path/to/file.py
commit-critic --write
```

Create a commit after accepting or editing the suggestion:

```bash
git add path/to/file.py
commit-critic --write --commit
```

Plain `--write` is suggestion-only. It never creates a commit. `--commit` is intentionally opt-in so the tool is safe to run while experimenting.

## Example Output

```text
Analyzing last 50 commits...

Provider: openai (gpt-4o-mini)

============================================================
  COMMITS THAT NEED WORK
============================================================
Commit: "fixed bug"
Score:  2/10
Issue:  Too vague - does not identify the affected behavior
Better: fix(auth): handle expired session tokens

============================================================
  YOUR STATS
============================================================
Average score:    6.8/10
Vague commits:    12 (24%)
One-word commits: 3 (6%)
Total analyzed:   50
```

## Testing

```bash
python -m unittest discover -v
python -m compileall commit_critic.py formatter.py git_utils.py llm_client.py prompts.py tests
```

The unit tests avoid live LLM calls. They cover Git parsing, staged-only diff behavior, critique normalization, prompt truncation, suggestion-only write mode, and opt-in commit creation.

Live smoke testing requires an actual provider:

```bash
commit-critic --analyze --limit 5
commit-critic --write
```

## Design Notes

See `DESIGN.md` for architecture, prompt strategy, provider tradeoffs, and testing decisions.

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `LLM_PROVIDER` | `ollama`, `openai`, or `deepseek` | `ollama` |
| `OLLAMA_MODEL` | Model name for Ollama | `llama3.1:8b` |
| `OPENAI_API_KEY` | Required when `LLM_PROVIDER=openai` | - |
| `OPENAI_MODEL` | OpenAI-compatible model name | `gpt-4o-mini` |
| `OPENAI_BASE_URL` | Optional custom API base URL | - |
| `DEEPSEEK_API_KEY` | Required when `LLM_PROVIDER=deepseek` | - |
| `DEEPSEEK_MODEL` | DeepSeek model name | `deepseek-v4-flash` |
| `DEEPSEEK_BASE_URL` | Optional DeepSeek-compatible base URL | `https://api.deepseek.com` |
