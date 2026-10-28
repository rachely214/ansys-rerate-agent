"""Load, validate and approve a case.yaml. No defaults: a missing required value is reported, never filled in.

Approval: the engineer approves a draft; approval stores a SHA-256 of the case content. Stage tools refuse to
run unless the current file still matches the approved hash (so an edited case must be re-approved).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import units

SCHEMA_FILE = Path(__file__).parent / "schema" / "case_schema.yaml"


class CaseError(ValueError):
    pass


def load_schema() -> dict:
    return yaml.safe_load(SCHEMA_FILE.read_text(encoding="utf-8"))["fields"]


def _get(d: dict, dotted: str) -> Any:
    cur: Any = d
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def content_hash(path: Path) -> str:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    data.pop("approval", None)
    canon = json.dumps(data, sort_keys=True, default=str).encode()
    return hashlib.sha256(canon).hexdigest()


@dataclass
class Case:
    path: Path
    data: dict
    issues: list[dict] = field(default_factory=list)

    # ---------- access
    def raw(self, dotted: str) -> Any:
        return _get(self.data, dotted)

    def q(self, dotted: str, unit: str) -> float:
        """Quantity in the requested unit. Raises CaseError if missing."""
        v = _get(self.data, dotted)
        if v is None:
            raise CaseError(f"case value '{dotted}' is missing; ask the engineer, do not assume")
        if not isinstance(v, dict) or "value" not in v or "unit" not in v:
            raise CaseError(f"case value '{dotted}' must be {{value, unit, source}}")
        return units.convert(float(v["value"]), str(v["unit"]), unit)

    def val(self, dotted: str) -> Any:
        v = _get(self.data, dotted)
        if v is None:
            raise CaseError(f"case value '{dotted}' is missing; ask the engineer, do not assume")
        return v["value"] if isinstance(v, dict) and "value" in v else v

    def opt(self, dotted: str, unit: str | None = None) -> float | Any | None:
        if _get(self.data, dotted) is None:
            return None
        return self.q(dotted, unit) if unit else self.val(dotted)

    def source(self, dotted: str) -> str | None:
        v = _get(self.data, dotted)
        return v.get("source") if isinstance(v, dict) else None

    def resolve_path(self, dotted: str) -> Path:
        p = Path(str(self.val(dotted)))
        return p if p.is_absolute() else (self.path.parent / p).resolve()

    @property
    def name(self) -> str:
        return str(self.val("case.name"))

    # ---------- approval
    @property
    def approved(self) -> bool:
        a = self.data.get("approval") or {}
        return bool(a.get("approved_by")) and a.get("content_sha256") == content_hash(self.path)

    def require_approved(self) -> None:
        if not self.approved:
            raise CaseError("case.yaml is not approved (or was edited after approval). Show the engineer every "
                            "value with its source and get approval before running any simulation.")

    def require_stage(self, stage: str) -> None:
        """Raise if any required field for this stage is missing or invalid."""
        bad = [i for i in self.issues if stage in i.get("stages", []) or not i.get("stages")]
        if bad:
            raise CaseError(f"case is missing/invalid values needed by stage '{stage}': "
                            + "; ".join(f"{i['field']}: {i['problem']}" for i in bad))


def validate(data: dict, schema: dict | None = None) -> list[dict]:
    schema = schema or load_schema()
    issues = []
    for fname, spec in schema.items():
        v = _get(data, fname)
        stages = spec.get("stages", [])
        if v is None:
            if spec.get("required"):
                issues.append({"field": fname, "problem": "missing (required)", "stages": stages})
            continue
        if "kind" in spec:
            if not isinstance(v, dict) or "value" not in v or "unit" not in v:
                issues.append({"field": fname, "problem": "must be {value, unit, source}", "stages": stages})
                continue
            try:
                float(v["value"])
                k = units.kind(str(v["unit"]))
            except (TypeError, ValueError) as e:
                issues.append({"field": fname, "problem": str(e), "stages": stages})
                continue
            if k != spec["kind"]:
                issues.append({"field": fname, "problem": f"unit '{v['unit']}' is {k}, expected {spec['kind']}",
                               "stages": stages})
            if not v.get("source"):
                issues.append({"field": fname, "problem": "no source given (document and section)",
                               "stages": stages, "severity": "warning"})
        else:
            raw = v["value"] if isinstance(v, dict) and "value" in v else v
            if "allowed" in spec and raw not in spec["allowed"]:
                issues.append({"field": fname, "problem": f"'{raw}' not in {spec['allowed']}", "stages": stages})
            if spec.get("type") == "int" and not isinstance(raw, int):
                issues.append({"field": fname, "problem": "must be an integer", "stages": stages})
    known = set(schema)
    prefixes = {".".join(f.split(".")[:i]) for f in known for i in range(1, f.count(".") + 1)}

    def walk(node: dict, path: str) -> None:
        for k, v in node.items():
            p = f"{path}.{k}"
            if p in known:
                continue
            if p in prefixes and isinstance(v, dict):
                walk(v, p)
            else:
                issues.append({"field": p, "problem": "unknown field (typo?)", "stages": [], "severity": "warning"})

    for top, sub in data.items():
        if top in ("approval", "notes", "schema_version"):
            continue
        if isinstance(sub, dict):
            walk(sub, top)
    return issues


def load(path: str | Path) -> Case:
    p = Path(path).resolve()
    if not p.exists():
        raise CaseError(f"case file not found: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    found = validate(data)
    c = Case(path=p, data=data, issues=[i for i in found if i.get("severity") != "warning"])
    c.warnings = [i for i in found if i.get("severity") == "warning"]  # type: ignore[attr-defined]
    return c


def approve(path: str | Path, approved_by: str) -> dict:
    """Record approval. Only call after the engineer explicitly approved the shown values."""
    if not approved_by or not approved_by.strip():
        raise CaseError("approved_by is required (the engineer's name or initials)")
    c = load(path)
    if c.issues:
        raise CaseError("cannot approve a case with blocking issues: "
                        + "; ".join(f"{i['field']}: {i['problem']}" for i in c.issues))
    import time
    text = Path(c.path).read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    data["approval"] = {"approved_by": approved_by.strip(), "approved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "content_sha256": content_hash(c.path)}
    Path(c.path).write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return data["approval"]


def summary_table(c: Case) -> list[dict]:
    """Every value with unit and source, for showing the engineer before approval."""
    rows = []
    for fname, spec in load_schema().items():
        v = c.raw(fname)
        if v is None:
            rows.append({"field": fname, "value": None, "unit": None, "source": None,
                         "required": bool(spec.get("required")), "note": spec.get("note")})
        elif isinstance(v, dict) and "value" in v:
            rows.append({"field": fname, "value": v["value"], "unit": v.get("unit"), "source": v.get("source"),
                         "required": bool(spec.get("required")), "note": spec.get("note")})
        else:
            rows.append({"field": fname, "value": v, "unit": None, "source": None,
                         "required": bool(spec.get("required")), "note": spec.get("note")})
    return rows
