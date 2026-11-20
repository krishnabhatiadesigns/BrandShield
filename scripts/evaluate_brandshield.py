"""Labelled synthetic evaluation harness.

These fixtures measure deterministic regression behavior only. They are not a
claim of real-world AI precision or recall.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.checks.deterministic import BrandContext, run_deterministic_checks


def main() -> int:
    dataset_path = ROOT / "backend" / "evaluation_dataset.json"
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    predicted_true = 0
    expected_true = 0
    matched_true = 0

    for case in cases:
        context = BrandContext(
            workspace_id=0,
            prohibited_terms=[],
            approved_terms=[],
            facts=[],
            passages=[],
            palette=[],
            assets=[],
            required_disclaimer=None,
            content_type="document",
            rules=[],
        )
        findings = run_deterministic_checks(case["body"], context)
        affected = [finding.affected_text.lower() for finding in findings]
        expected = [text.lower() for text in case["expected"]]
        predicted_true += sum(1 for text in affected if text)
        expected_true += len(expected)
        matched_true += sum(1 for text in expected if text in " ".join(affected))

    precision = matched_true / predicted_true if predicted_true else 1.0
    recall = matched_true / expected_true if expected_true else 1.0
    print(
        json.dumps(
            {
                "scope": "synthetic_deterministic_regression_only",
                "cases": len(cases),
                "precision_proxy": round(precision, 3),
                "recall_proxy": round(recall, 3),
                "not_real_world_accuracy": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
