"""Static repository checks (no Ansys needed):
1. required files exist
2. no machine-specific values outside examples/ (HECC numbers, user paths, usernames, key-like strings)
3. no MCP tool that runs arbitrary code
Exit code 1 on any finding. Run before every commit and before publishing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["LICENSE", "THIRD_PARTY_NOTICES.md", "SECURITY.md", "CONTRIBUTING.md", ".gitignore",
            "runtime/pyproject.toml", "runtime/src/rerate_mcp_v2/schema/case_schema.yaml",
            "setup/requirements.lock", "setup/machine.config.template.yaml",
            "START-HERE.md", "README.md", "docs/HOW-IT-WORKS.md", "docs/TROUBLESHOOTING.md",
            "setup/check.py", "setup/install_runtime.py",
            "setup/setup-agent/SOUL.md", "setup/setup-agent/distribution.yaml", "setup/setup-agent/config.yaml",
            "setup/setup-agent/skills/setup-run/SKILL.md", "setup/setup-agent/skills/setup-diagnose/SKILL.md",
            "setup/setup-agent/skills/ansys-host-diagnostics/SKILL.md",
            "agent/distribution.yaml", "agent/SOUL.md", "agent/config.yaml", "agent/mcp_servers.json",
            "agent/skills/rerate-run/SKILL.md", "agent/skills/rerate-intake/SKILL.md",
            "agent/skills/rerate-sizing/SKILL.md", "agent/skills/rerate-geometry/SKILL.md",
            "agent/skills/rerate-meshing/SKILL.md", "agent/skills/rerate-cfd/SKILL.md",
            "agent/skills/rerate-structural/SKILL.md", "agent/skills/rerate-report/SKILL.md",
            "docs/VALIDATION.md", "docs/DECISIONS.md", "docs/ROADMAP.md",
            "examples/01_nasa_hecc/case.yaml", "examples/01_nasa_hecc/prompt.md", "examples/01_nasa_hecc/README.md",
            "docs/examples/01_nasa_hecc_expected.md", "tests/test_core.py"]
SKIP_DIRS = {".git", ".venv", ".local", "runs", "work", "__pycache__", "examples"}
SCAN_EXT = {".py", ".md", ".yaml", ".yml", ".ps1", ".toml", ".txt", ".json"}
# docs that intentionally discuss these values (scan report, validation evidence, history) are exempted by name
EXEMPT = {"docs/VALIDATION.md", "setup/verify_layout.py",
          "setup/requirements.lock", "THIRD_PARTY_NOTICES.md"}
PATTERNS = {
    "HECC number": r"(?<![\d.])(10\.85|11\.5|4\.68|4\.60|0\.609|0\.650|21789|21,789|22878|75842|228\.3|228300|"
                   r"121347|121\.35|0\.706|0\.6115|8\.4997|8\.804|12\.59)(?![\d])",
    "HECC test condition": r"120\s?kPa|120000|11\s?psia",
    "HECC name": r"\bHECC\b",
    "user path": r"[A-Za-z]:[\\/]+(Users|Program Files|ProgramData)[\\/]",
    "absolute temp path": r"(?<![\w.])/tmp/|AppData[\\/]+Local[\\/]+Temp",
    "username": r"\bNVIDIA[\\/]|Users[\\/]NVIDIA",
    "key/token": r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}",
}
ARBITRARY = r"def\s+(run_code|run_python|run_script|run_mechanical_script|run_design_script|exec_code)\s*\("


def scan() -> list[str]:
    out = []
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT).as_posix()
        if p.is_dir() or p.suffix not in SCAN_EXT or any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if rel not in EXEMPT:
            for name, pat in PATTERNS.items():
                for m in re.finditer(pat, txt):
                    line = txt.count("\n", 0, m.start()) + 1
                    out.append(f"{rel}:{line}: {name}: '{m.group(0)}'")
        if rel.startswith("runtime/") and p.suffix == ".py" and re.search(ARBITRARY, txt):
            out.append(f"{rel}: defines an arbitrary-code tool")
    return out


def main() -> int:
    missing = [f for f in REQUIRED if not (ROOT / f).exists()]
    hits = scan()
    for f in missing:
        print(f"MISSING {f}")
    for h in hits:
        print(f"FOUND   {h}")
    print(f"layout: {len(REQUIRED) - len(missing)}/{len(REQUIRED)} required files; scan findings: {len(hits)}")
    return 1 if (missing or hits) else 0


if __name__ == "__main__":
    sys.exit(main())
