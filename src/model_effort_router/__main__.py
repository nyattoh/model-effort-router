"""JSON file/stdin to JSON stdout. Diagnostics never include raw exceptions."""

import argparse
import json
import os
import sys
from pathlib import Path

from .router import RouterError, review_checkpoint, route


def main() -> int:
    parser = argparse.ArgumentParser(description="Select task plans and model/effort pairs using Jev.")
    parser.add_argument("request", nargs="?", default="-", help="JSON file, or - for stdin")
    parser.add_argument("--checkpoint", action="store_true",
                        help="review one worker checkpoint instead of routing a request")
    parser.add_argument("--check-api-key", action="store_true",
                        help="report whether TYPESAFE_API_KEY is configured without printing it")
    parser.add_argument("--dry-run", action="store_true", help="emit decision payloads; never call Jev")
    parser.add_argument("--min-confidence", type=float, default=0.5,
                        help="user policy threshold (0 to 1; default 0.5 is not empirically calibrated)")
    parser.add_argument("--jev-model", default="jev-latest")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.check_api_key:
        print(json.dumps({
            "TYPESAFE_API_KEY_configured": bool(os.environ.get("TYPESAFE_API_KEY", "").strip())
        }))
        return 0
    try:
        raw = sys.stdin.read() if args.request == "-" else Path(args.request).read_text(encoding="utf-8-sig")
        document = json.loads(raw)
        if args.checkpoint:
            result = review_checkpoint(document, dry_run=args.dry_run,
                                       min_confidence=args.min_confidence,
                                       jev_model=args.jev_model, timeout=args.timeout)
        else:
            result = route(document, dry_run=args.dry_run, min_confidence=args.min_confidence,
                           jev_model=args.jev_model, timeout=args.timeout)
        code = 0 if result["status"] != "needs_review" else 3
    except RouterError as exc:
        result, code = {"ok": False, "error": str(exc)}, 2
    except (OSError, ValueError, UnicodeError):
        result, code = {"ok": False, "error": "invalid_or_unreadable_json"}, 2
    # ASCII JSON remains portable when Windows stdout uses a legacy code page.
    rendered = json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False)
    secret = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if secret:
        rendered = rendered.replace(json.dumps(secret, ensure_ascii=True)[1:-1], "[REDACTED]")
    print(rendered)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
