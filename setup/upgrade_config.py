"""Add new keys from the config template to an existing machine config without changing values already set.

  python setup/upgrade_config.py [--config PATH] [--home DIR]

Default config: <install home>/machine.config.yaml, where the install home is --home, else ANSYS_RERATE_HOME,
else %LOCALAPPDATA%/ansys-rerate-agent. Run after updating this repository. Prints the keys it added.
A copy of the old file is kept as machine.config.yaml.bak when something changes.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "setup" / "machine.config.template.yaml"
sys.path.insert(0, str(ROOT / "setup"))
from check import install_home  # noqa: E402


def _is_placeholder(v) -> bool:
    return isinstance(v, str) and v.startswith("<") and v.endswith(">")


def load_template() -> dict:
    """Template with <PLACEHOLDER> values quoted so it parses (placeholders are never copied)."""
    txt = re.sub(r":(\s+)(<[A-Z_]+>)", r":\1'\2'", TEMPLATE.read_text(encoding="utf-8"))
    return yaml.safe_load(txt) or {}


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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help="machine config file to upgrade")
    p.add_argument("--home", help="install home (default: ANSYS_RERATE_HOME or LOCALAPPDATA/ansys-rerate-agent)")
    a = p.parse_args()
    cfg_path = Path(a.config) if a.config else install_home(a.home) / "machine.config.yaml"
    if not cfg_path.exists():
        print(f"No machine config at {cfg_path}. Create it first: python setup/install_runtime.py config")
        return 1
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    added = merge_missing(cfg, load_template())
    if added:
        shutil.copy2(cfg_path, cfg_path.with_suffix(".yaml.bak"))
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    print(f"{cfg_path}: added {', '.join(added) if added else 'nothing (already up to date)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
