from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.run_eval import DEFAULT_DATASET, evaluate


def compare_runs(*, dataset_path: str | Path, runs: list[str], k: int, output: str | Path | None = None) -> dict:
    results = {}
    for run in runs:
        if "=" not in run:
            raise ValueError("Each run must use name=path format")
        name, path = run.split("=", 1)
        results[name] = evaluate(dataset_path=dataset_path, predictions_path=path, k=k).model_dump()

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_to_markdown(results), encoding="utf-8")
    return results


def _to_markdown(results: dict) -> str:
    metric_names = []
    for result in results.values():
        for metric_name in result["metrics"]:
            if metric_name not in metric_names:
                metric_names.append(metric_name)

    lines = ["# Sprint 2 Retrieval Quality Report", "", "| metric | " + " | ".join(results.keys()) + " |", "|---|" + "---|" * len(results)]
    for metric_name in metric_names:
        values = []
        for result in results.values():
            value = result["metrics"].get(metric_name)
            values.append("" if value is None else str(round(value, 4) if isinstance(value, float) else value))
        lines.append(f"| {metric_name} | " + " | ".join(map(str, values)) + " |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare multiple retrieval prediction runs.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--runs", nargs="+", required=True, help="Run specs in name=path format")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", default="../Docs/Sprint2RetrievalQualityReport.md")
    args = parser.parse_args()

    results = compare_runs(dataset_path=args.dataset, runs=args.runs, k=args.k, output=args.output)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
