"""Add new keys from the config template to an existing .local/rerate.config.yaml without changing set values.

  python scripts/setup/upgrade_config.py [--config <path>]
Run after pulling a newer version (setup.ps1 calls it). Prints the keys it added.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "harnesses" / "hermes" / "rerate.config.template.yaml"


def _is_placeholder(v) -> bool:
    return isinstance(v, str) and v.startswith("<") and v.endswith(">")


def merge_missing(dst: dict, src: dict, prefix: str = "") -> list[str]:
    """Copy keys missing in dst from src, recursively. Placeholders (<LIKE_THIS>) are never copied."""
    added = []
    for k, v in src.items():
        if isinstance(v, dict):
            if k not in dst:
                dst[k] = {}
                sub = merge_missing(dst[k], v, prefix + k + ".")
                if not dst[k]:
                    del dst[k]
                elif sub:
                    added.append(prefix + k)
            elif isinstance(dst[k], dict):
                added += merge_missing(dst[k], v, prefix + k + ".")
        elif k not in dst and not _is_placeholder(v):
            dst[k] = v
            added.append(prefix + k)
    return added


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=str(ROOT / ".local" / "rerate.config.yaml"))
    a = p.parse_args()
    cfg_path = Path(a.config)
    tmpl = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8").replace("<", "'<").replace(">", ">'")
                          .replace("''<", "'<").replace(">''", ">'"))
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    added = merge_missing(cfg, tmpl)
    if added:
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    print(f"{cfg_path}: added {added or 'nothing'}")


if __name__ == "__main__":
    main()
