"""Measure compact dispatch-context savings and render a dependency-free SVG chart."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]
EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4}


def estimate_tokens(value: Any) -> int:
    """Use a transparent 4-characters-per-token estimate, not a provider tokenizer."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return max(1, math.ceil(len(text) / 4))


def eligible_pairs(task: JsonObject, models: list[JsonObject]) -> list[JsonObject]:
    allowed = task.get("allowed_pairs")
    pairs = []
    for model in models:
        for effort in model["efforts"]:
            pair = {"model": model["id"], "provider": model["provider"], "effort": effort}
            if task.get("requirements", []) and not set(task["requirements"]) <= set(model.get("capabilities", [])):
                continue
            if allowed and not any(item == {"model": model["id"], "effort": effort} for item in allowed):
                continue
            pairs.append(pair)
    return pairs


def choose_pair(task: JsonObject, models: list[JsonObject]) -> JsonObject:
    pairs = eligible_pairs(task, models)
    if not pairs:
        raise ValueError(f"no eligible model-effort pair for {task['id']}")
    return min(pairs, key=lambda pair: (EFFORT_ORDER.get(pair["effort"], 99), pair["model"]))


def measure(document: JsonObject) -> JsonObject:
    candidate = document["candidates"][0]
    rows = []
    for task in candidate["tasks"]:
        pair = choose_pair(task, document["models"])
        baseline = {
            "request": document["request"],
            "constraints": document.get("constraints", {}),
            "all_candidates": document["candidates"],
            "all_models": document["models"],
            "task": task,
        }
        routed = {
            "request": document["request"],
            "constraints": document.get("constraints", {}),
            "task": task,
            "assignment": pair,
        }
        baseline_tokens = estimate_tokens(baseline)
        routed_tokens = estimate_tokens(routed)
        rows.append({
            "task_id": task["id"],
            "model": pair["model"],
            "effort": pair["effort"],
            "baseline_estimated_tokens": baseline_tokens,
            "routed_estimated_tokens": routed_tokens,
            "estimated_reduction_percent": round((baseline_tokens - routed_tokens) / baseline_tokens * 100, 2),
        })

    baseline_total = sum(row["baseline_estimated_tokens"] for row in rows)
    routed_total = sum(row["routed_estimated_tokens"] for row in rows)
    reduction = baseline_total - routed_total
    return {
        "method": "4 characters per token estimate",
        "scope": "per-worker dispatch context; not provider billing or model performance",
        "fixture": "examples/request.json",
        "candidate_id": candidate["id"],
        "baseline_total_estimated_tokens": baseline_total,
        "routed_total_estimated_tokens": routed_total,
        "estimated_reduction_tokens": reduction,
        "estimated_reduction_percent": round(reduction / baseline_total * 100, 2),
        "per_task": rows,
    }


def render_svg(result: JsonObject) -> str:
    baseline = result["baseline_total_estimated_tokens"]
    routed = result["routed_total_estimated_tokens"]
    chart_left, chart_top, chart_width, chart_height = 90, 45, 520, 230
    scale = chart_height / max(baseline, routed)
    bars = [("Full context", baseline, "#9b5de5"), ("Task handoff", routed, "#00bbf9")]
    rects = []
    labels = []
    for index, (label, value, colour) in enumerate(bars):
        x = chart_left + 75 + index * 220
        height = round(value * scale, 1)
        y = chart_top + chart_height - height
        rects.append(f'<rect x="{x}" y="{y}" width="110" height="{height}" fill="{colour}"/>')
        labels.append(f'<text x="{x + 55}" y="{chart_top + chart_height + 22}" text-anchor="middle">{label}</text>')
        labels.append(f'<text x="{x + 55}" y="{y - 8}" text-anchor="middle">{value}</text>')
    reduction = result["estimated_reduction_percent"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="350" viewBox="0 0 720 350" role="img" aria-labelledby="title desc">
<title id="title">Estimated dispatch-context token reduction</title>
<desc id="desc">Full context {baseline} estimated tokens versus task handoff {routed}; estimated reduction {reduction}%.</desc>
<rect width="720" height="350" fill="white"/>
<text x="360" y="25" text-anchor="middle" font-family="sans-serif" font-size="18" font-weight="bold">Estimated dispatch-context tokens</text>
<text x="360" y="325" text-anchor="middle" font-family="sans-serif" font-size="13">Estimate: 4 characters per token; fixture: examples/request.json</text>
<line x1="{chart_left}" y1="{chart_top + chart_height}" x2="{chart_left + chart_width}" y2="{chart_top + chart_height}" stroke="#333"/>
{''.join(rects)}
{''.join(labels)}
<text x="360" y="285" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#087f5b">Estimated reduction: {reduction}%</text>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--svg-out", type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.input.read_text(encoding="utf-8"))
    result = measure(document)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.svg_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.svg_out.write_text(render_svg(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
