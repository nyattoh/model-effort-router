"""Measure dispatch-context payloads with explicit reference tokenizers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import tiktoken
except ImportError as exc:
    raise SystemExit("Install benchmark support with: python -m pip install -e .[benchmark]") from exc


JsonObject = dict[str, Any]
ENCODINGS = ("cl100k_base", "o200k_base")
EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4}


def serialise(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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


def build_payloads(document: JsonObject) -> tuple[str, list[JsonObject]]:
    candidate = document["candidates"][0]
    rows = []
    for task in candidate["tasks"]:
        pair = choose_pair(task, document["models"])
        rows.append({
            "task_id": task["id"],
            "model": pair["model"],
            "effort": pair["effort"],
            "baseline": {
                "request": document["request"],
                "constraints": document.get("constraints", {}),
                "all_candidates": document["candidates"],
                "all_models": document["models"],
                "task": task,
            },
            "routed": {
                "request": document["request"],
                "constraints": document.get("constraints", {}),
                "task": task,
                "assignment": pair,
            },
        })
    return candidate["id"], rows


def measure(document: JsonObject, encoding_names: tuple[str, ...] = ENCODINGS) -> JsonObject:
    candidate_id, payloads = build_payloads(document)
    measurements = []
    for encoding_name in encoding_names:
        encoding = tiktoken.get_encoding(encoding_name)
        per_task = []
        for row in payloads:
            baseline = len(encoding.encode(serialise(row["baseline"])))
            routed = len(encoding.encode(serialise(row["routed"])))
            per_task.append({
                "task_id": row["task_id"],
                "model": row["model"],
                "effort": row["effort"],
                "baseline_tokens": baseline,
                "routed_tokens": routed,
                "reduction_tokens": baseline - routed,
                "reduction_percent": round((baseline - routed) / baseline * 100, 2),
            })
        baseline_total = sum(row["baseline_tokens"] for row in per_task)
        routed_total = sum(row["routed_tokens"] for row in per_task)
        measurements.append({
            "encoding": encoding_name,
            "baseline_total_tokens": baseline_total,
            "routed_total_tokens": routed_total,
            "reduction_tokens": baseline_total - routed_total,
            "reduction_percent": round((baseline_total - routed_total) / baseline_total * 100, 2),
            "per_task": per_task,
        })

    reductions = [row["reduction_percent"] for row in measurements]
    return {
        "method": "OpenAI tiktoken reference encodings",
        "tiktoken_version": tiktoken.__version__,
        "scope": "synthetic per-worker dispatch payloads; not observed session usage, billing, latency, quality, or model performance",
        "fixture": "examples/request.json",
        "candidate_id": candidate_id,
        "assumptions": {
            "candidate_selection": "first candidate in the fixture",
            "assignment_policy": "lowest declared eligible effort, then model id",
            "baseline": "full request, all candidates, and all models repeated for every worker",
            "routed": "request, constraints, selected task, and selected assignment per worker",
            "excluded": "system prompts, tool schemas, provider wrappers, runtime results, retries, and cache effects"
        },
        "reduction_percent_range": {"min": min(reductions), "max": max(reductions)},
        "measurements": measurements
    }


def render_svg(result: JsonObject) -> str:
    measurements = result["measurements"]
    maximum = max(row["baseline_total_tokens"] for row in measurements)
    chart_left, chart_top, chart_height = 90, 80, 225
    scale = chart_height / maximum
    colours = {"baseline": "#8b5cf6", "routed": "#0284c7"}
    marks = []
    labels = []
    for group_index, row in enumerate(measurements):
        group_x = 185 + group_index * 300
        for bar_index, key in enumerate(("baseline_total_tokens", "routed_total_tokens")):
            value = row[key]
            x = group_x + bar_index * 90
            height = round(value * scale, 1)
            y = round(chart_top + chart_height - height, 1)
            colour = colours["baseline" if bar_index == 0 else "routed"]
            marks.append(f'<rect x="{x}" y="{y}" width="64" height="{height}" fill="{colour}"/>')
            labels.append(f'<text x="{x + 32}" y="{round(y - 8, 1)}" text-anchor="middle">{value}</text>')
        labels.append(f'<text x="{group_x + 77}" y="330" text-anchor="middle">{row["encoding"]}</text>')
        labels.append(f'<text x="{group_x + 77}" y="350" text-anchor="middle" fill="#087f5b">-{row["reduction_percent"]}%</text>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="820" height="410" viewBox="0 0 820 410" role="img" aria-labelledby="title desc">
<title id="title">Dispatch-context token counts using reference encodings</title>
<desc id="desc">Full-context and task-handoff payload token counts using cl100k_base and o200k_base.</desc>
<rect width="820" height="410" fill="white"/>
<text x="410" y="28" text-anchor="middle" font-family="sans-serif" font-size="18" font-weight="bold">Dispatch-context token counts</text>
<text x="410" y="48" text-anchor="middle" font-family="sans-serif" font-size="12">Synthetic fixture; excludes system, tool, runtime, retry, and cache overhead</text>
<line x1="{chart_left}" y1="{chart_top + chart_height}" x2="740" y2="{chart_top + chart_height}" stroke="#333"/>
{''.join(marks)}
{''.join(labels)}
<rect x="275" y="378" width="14" height="14" fill="{colours["baseline"]}"/>
<text x="296" y="390" font-family="sans-serif" font-size="12">Full context per worker</text>
<rect x="470" y="378" width="14" height="14" fill="{colours["routed"]}"/>
<text x="491" y="390" font-family="sans-serif" font-size="12">Task handoff</text>
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
