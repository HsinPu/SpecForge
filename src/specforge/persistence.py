from __future__ import annotations

import json
from pathlib import Path

from specforge.models import (
    Gap,
    ProjectFacts,
    TraceClaim,
    gap_from_dict,
    project_facts_from_dict,
    trace_claim_from_dict,
)


def load_fact_bundle(path: str | Path) -> tuple[ProjectFacts, list[TraceClaim], list[Gap]]:
    bundle_path = Path(path)
    facts = project_facts_from_dict(_read_json(bundle_path / "facts.json"))
    claims = [
        trace_claim_from_dict(item)
        for item in _read_json(bundle_path / "traceability.json")
    ]
    gaps_path = bundle_path / "gaps.json"
    gaps = [gap_from_dict(item) for item in _read_json(gaps_path)] if gaps_path.exists() else []
    return facts, claims, gaps


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))
