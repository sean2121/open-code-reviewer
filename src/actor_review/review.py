from litellm import completion

from actor_review.config import REVIEW_MODEL

SYSTEM_PROMPT = """You are an expert code reviewer. Analyze the given pull request information and provide feedback.

## Available context
- PR title, description, commit messages: use to understand the intent of the change
- Git blame: use to understand when, by whom, and why the changed lines were originally written
- Code diff: the actual changes

## Review criteria
- Security vulnerabilities
- Logic errors and bugs
- Code style and readability
- Consistency with past implementation intent

## Output format
For each issue, describe:
- File and location
- Severity (high / medium / low)
- Description of the problem
- Suggested fix

Only report issues you are highly confident about. Avoid noise."""


def review_diff(diff: str, model: str = REVIEW_MODEL) -> str:
    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Review the following diff:\n\n{diff}"},
        ],
        max_tokens=4096,
    )

    return response.choices[0].message.content
