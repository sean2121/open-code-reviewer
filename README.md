# OpenCodeReviewer

> AI code review, the empirical way.

OpenCodeReviewer is an open-source AI code reviewer that enriches pull request context — git blame, fan-out files, and static analysis — before passing it to an LLM for review.

## Features

- **PR context**: fetches title, description, commits, and linked issues from GitHub
- **AST symbol extraction**: identifies functions and classes touched by the diff
- **Git blame**: surfaces the history and intent behind changed lines
- **Fan-out detection**: includes files directly imported by changed files
- **Static analysis**: runs [Opengrep](https://opengrep.dev) rules before the LLM sees the diff
- **Custom instructions**: drop `.md` files in `instructions/` to add your own review criteria
- **Inline comments**: posts findings as inline PR review comments on GitHub

## Usage

```bash
ACTOR_REVIEW_GITHUB_TOKEN=ghp_xxx poetry run python -m open_code_reviewer.main <owner/repo> <pr_number> [repo_path] [--comment]
```

- `repo_path` — path to a local clone of the repository (enables blame and fan-out)
- `--comment` — post findings as inline comments on the PR

## Custom instructions

Add `.md` files to the `instructions/` directory to extend the review criteria:

```
instructions/
  security.md      # your security guidelines
  architecture.md  # your architectural rules
```

## Benchmark

Accuracy is measured against the [CodeReview dataset](https://github.com/microsoft/CodeBERT) using LLM-as-Judge and CodeBERTScore:

```bash
poetry run python tests/benchmark.py 100
```

## Configuration

Set the model in `src/open_code_reviewer/config.py`:

```python
REVIEW_MODEL = "openai/gpt-4o"
JUDGE_MODEL  = "openai/gpt-4o"
```

Any model supported by [LiteLLM](https://docs.litellm.ai) can be used.
