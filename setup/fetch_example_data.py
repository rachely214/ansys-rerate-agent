"""Download example geometry data from its public source (not committed to the repository).

  python scripts/setup/fetch_example_data.py --example 01_nasa_hecc [--zip <already downloaded zip>]

Reads examples/<example>/data_source.yaml (URL, file name, which members to extract, expected files), downloads
the archive into work/downloads with resume support, then extracts only the listed members into the example's
geometry_data folder. Prints what was done. Re-running is safe: existing complete files are kept.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CHUNK = 1 << 20


def download(url: str, dest: Path, expected_bytes: int | None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    have = dest.stat().st_size if dest.exists() else 0
    if expected_bytes and have == expected_bytes:
        print(f"already downloaded: {dest} ({have:,} bytes)")
        return dest
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "ab" if have else "wb") as f:
        total = int(r.headers.get("Content-Length", 0)) + have
        print(f"downloading {url} -> {dest} ({total:,} bytes, resuming at {have:,})", flush=True)
        done, last = have, 0
        while True:
            b = r.read(CHUNK)
            if not b:
                break
            f.write(b)
            done += len(b)
            if done - last > 200 * CHUNK:
                print(f"  {done / max(total, 1):.0%}", flush=True)
                last = done
    if expected_bytes and dest.stat().st_size != expected_bytes:
        sys.exit(f"size mismatch: got {dest.stat().st_size:,}, expected {expected_bytes:,}; rerun to resume")
    return dest


def extract(zpath: Path, members_prefix: str, out_dir: Path) -> int:
    n = 0
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(members_prefix):
                continue
            target = out_dir / Path(info.filename).relative_to(Path(members_prefix).parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_size == info.file_size:
                continue
            with z.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            n += 1
    return n


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--example", required=True)
    p.add_argument("--zip", help="use an archive you already downloaded")
    a = p.parse_args()
    ex = ROOT / "examples" / a.example
    src = yaml.safe_load((ex / "data_source.yaml").read_text(encoding="utf-8"))
    out_dir = ex / src["extract_to"]
    missing = [f for f in src["expected_files"] if not (out_dir / f).exists()]
    if not missing:
        print(f"all {len(src['expected_files'])} expected files present in {out_dir}")
        return
    zpath = Path(a.zip) if a.zip else download(src["url"], ROOT / "work" / "downloads" / src["file_name"],
                                               src.get("bytes"))
    n = extract(zpath, src["members_prefix"], out_dir)
    still = [f for f in src["expected_files"] if not (out_dir / f).exists()]
    print(f"extracted {n} files to {out_dir}; missing after extract: {still or 'none'}")
    if still:
        sys.exit(1)


if __name__ == "__main__":
    main()
