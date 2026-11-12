#!/usr/bin/env python3
"""Deterministic CV-fit arithmetic for the cv-optimizer skill.

The model judges each dimension (0-100); THIS script does the math, so totals are never miscomputed
by an LLM. It also computes exact tenure from dates and applies the decision rule.

Usage
  python fit_score.py score --dims must_haves=35,keywords=65,experience=40,tools=35,domain=75 \
                            [--weights must_haves=35,keywords=15,experience=20,tools=20,domain=10] \
                            [--critical-gap "5+ years required, candidate has ~3"]...
  python fit_score.py score --json input.json
  python fit_score.py tenure --start 2023-01 [--end 2026-11]

Output is JSON on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

DIMENSIONS = ("must_haves", "keywords", "experience", "tools", "domain")
DEFAULT_WEIGHTS = {"must_haves": 35, "keywords": 15, "experience": 20, "tools": 20, "domain": 10}
PROCEED_AT = 50.0


def parse_pairs(raw: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        key, _, value = part.partition("=")
        out[key.strip()] = float(value)
    return out


def weighted_score(dims: dict[str, float], weights: dict[str, float] | None = None) -> float:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    missing = [d for d in DIMENSIONS if d not in dims]
    if missing:
        raise ValueError(f"missing dimension scores: {', '.join(missing)}")
    for name, value in dims.items():
        if not 0 <= value <= 100:
            raise ValueError(f"{name}={value} must be between 0 and 100")
    total_weight = sum(weights[d] for d in DIMENSIONS)
    if total_weight <= 0:
        raise ValueError("weights must sum to more than zero")
    return sum(dims[d] * weights[d] for d in DIMENSIONS) / total_weight


def decide(total: float, critical_gaps: list[str]) -> tuple[str, str]:
    if critical_gaps and total >= PROCEED_AT:
        return (
            "proceed_with_caution",
            "Score is above 50% but a mandatory requirement is clearly unmet; the role may be unrealistic. "
            "Tailor only if the gap is flexible or can be bridged honestly.",
        )
    if critical_gaps:
        return "skip_or_stretch", "Below 50% and a mandatory requirement is unmet: treat as a stretch application at most."
    if total >= PROCEED_AT:
        return "proceed", "Reasonable foundation: worth tailoring the CV."
    return "stretch", "Below 50%: do not invest heavily in tailoring; consider adjacent roles that fit better."


def score(dims: dict[str, float], weights: dict[str, float] | None, critical_gaps: list[str]) -> dict:
    total = weighted_score(dims, weights)
    decision, advice = decide(total, critical_gaps)
    used = {**DEFAULT_WEIGHTS, **(weights or {})}
    return {
        "total": round(total, 1),
        "decision": decision,
        "advice": advice,
        "dimensions": dims,
        "weights": {d: used[d] for d in DIMENSIONS},
        "contributions": {d: round(dims[d] * used[d] / sum(used[x] for x in DIMENSIONS), 2) for d in DIMENSIONS},
        "critical_gaps": critical_gaps,
        "disclaimer": "An informed estimate, not a statistical probability of getting an interview.",
    }


def _ym(value: str) -> tuple[int, int]:
    year, _, month = value.partition("-")
    return int(year), int(month or 1)


def tenure(start: str, end: str | None = None) -> dict:
    sy, sm = _ym(start)
    if end:
        ey, em = _ym(end)
    else:
        today = date.today()
        ey, em = today.year, today.month
    months = (ey - sy) * 12 + (em - sm)
    if months < 0:
        raise ValueError("end is before start")
    years, rem = divmod(months, 12)
    if years == 0:
        phrase = f"{rem} months"
    elif rem >= 9:
        phrase = f"nearly {years + 1} years"
    elif rem == 0:
        phrase = f"{years} years"
    else:
        phrase = f"{years}+ years"
    return {"months": months, "years": years, "extra_months": rem, "cv_phrase": phrase}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score")
    s.add_argument("--dims", help="must_haves=..,keywords=..,experience=..,tools=..,domain=..")
    s.add_argument("--weights")
    s.add_argument("--critical-gap", action="append", default=[])
    s.add_argument("--json", help="path to a JSON file with dims/weights/critical_gaps ('-' for stdin)")

    t = sub.add_parser("tenure")
    t.add_argument("--start", required=True, help="YYYY-MM")
    t.add_argument("--end", help="YYYY-MM (default: now)")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "tenure":
            print(json.dumps(tenure(args.start, args.end), indent=2))
            return 0
        if args.json:
            raw = sys.stdin.read() if args.json == "-" else open(args.json, encoding="utf-8").read()
            data = json.loads(raw)
            dims, weights, gaps = data["dims"], data.get("weights"), data.get("critical_gaps", [])
        else:
            if not args.dims:
                ap.error("--dims or --json is required")
            dims = parse_pairs(args.dims)
            weights = parse_pairs(args.weights) if args.weights else None
            gaps = args.critical_gap
        print(json.dumps(score(dims, weights, gaps), indent=2))
        return 0
    except (ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
