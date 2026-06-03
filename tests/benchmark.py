import json
import sys
from pathlib import Path

from bert_score import score as bert_score
from litellm import completion

from open_code_reviewer.config import JUDGE_MODEL, REVIEW_MODEL
from open_code_reviewer.review import review_diff


DATA_PATH = Path(__file__).parent.parent / "data" / "Comment_Generation" / "msg-test.jsonl"

JUDGE_PROMPT = """You are evaluating an AI code review tool.

Expected review comment (ground truth):
{expected}

Generated review comment:
{generated}

Does the generated comment identify the same issue as the expected comment?
Answer with only "yes" or "no"."""


def load_samples(n: int = 100) -> list[dict]:
    samples = []
    with open(DATA_PATH) as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            samples.append(json.loads(line))
    return samples


def judge(expected: str, generated: str, model: str = JUDGE_MODEL) -> bool:
    response = completion(
        model=model,
        messages=[
            {
                "role": "user",
                "content": JUDGE_PROMPT.format(expected=expected, generated=generated),
            }
        ],
        max_tokens=10,
    )
    answer = response.choices[0].message.content.strip().lower()
    return answer.startswith("yes")


def compute_bertscore(expected_list: list[str], generated_list: list[str]) -> list[float]:
    _, _, f1 = bert_score(
        generated_list,
        expected_list,
        lang="en",
        model_type="roberta-large",
        verbose=False,
    )
    return f1.tolist()


def evaluate(samples: list[dict], review_model: str = REVIEW_MODEL, judge_model: str = JUDGE_MODEL) -> list[dict]:
    results = []
    expected_list = []
    generated_list = []

    for i, sample in enumerate(samples):
        print(f"[{i+1}/{len(samples)}] reviewing...")
        patch = sample["patch"]
        expected = sample["msg"]

        try:
            generated = review_diff(patch, model=review_model)
            is_correct = judge(expected, generated, model=judge_model)

            results.append({
                "id": sample["id"],
                "expected": expected,
                "generated": generated,
                "correct": is_correct,
                "lang": sample.get("lang", ""),
            })
            expected_list.append(expected)
            generated_list.append(generated)

            print(f"  {'✓' if is_correct else '✗'}  expected: {expected[:60]}")
        except Exception as e:
            print(f"  error: {e}")
            continue

    print("\nComputing CodeBERTScore...")
    bert_scores = compute_bertscore(expected_list, generated_list)
    for r, s in zip(results, bert_scores):
        r["bertscore"] = round(s, 4)

    total = len(results)
    correct = sum(r["correct"] for r in results)
    avg_bertscore = sum(r["bertscore"] for r in results) / total if total > 0 else 0

    print(f"\n=== Result ===")
    print(f"Review model:    {review_model}")
    print(f"Judge model:     {judge_model}")
    print(f"LLM-as-Judge:    {correct}/{total} ({correct/total:.1%})")
    print(f"CodeBERTScore:   {avg_bertscore:.4f}")

    return results


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    review_model = sys.argv[2] if len(sys.argv) > 2 else REVIEW_MODEL
    judge_model = sys.argv[3] if len(sys.argv) > 3 else JUDGE_MODEL

    print(f"Loading {n} samples...")
    samples = load_samples(n)

    print("Starting evaluation...")
    results = evaluate(samples, review_model=review_model, judge_model=judge_model)

    output_path = Path(__file__).parent.parent / "data" / "benchmark_results.jsonl"
    with open(output_path, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
