"""Download the example geometry data from its public source (the data is never committed to the repository).

  python setup/fetch_example_data.py --example 01_nasa_hecc [--home DIR] [--zip PATH] [--from-dir DIR]

Reads examples/<example>/data_source.yaml (URL, file name, members to extract, expected files). Downloads the
archive into <install home>/downloads with resume support, then extracts only the listed members into
<install home>/example-data/<example>/<extract_to>. Re-running is safe: complete files are kept.
--zip uses an archive you already downloaded. --from-dir copies an existing extracted folder (for testing).
"""
from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "setup"))
from check import install_home  # noqa: E402

CHUNK = 1 << 20


def download(url: str, dest: Path, expected_bytes: int | None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    have = dest.stat().st_size if dest.exists() else 0
    if expected_bytes and have == expected_bytes:
        print(f"already downloaded: {dest} ({have:,} bytes)")
        return dest
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        start = have if (have and r.status == 206) else 0  # server ignored the range: start over
        total = int(r.headers.get("Content-Length", 0)) + start
        print(f"downloading {url}\n  -> {dest} ({total:,} bytes, starting at {start:,})", flush=True)
        with open(dest, "ab" if start else "wb") as f:
            done, last = start, start
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
        sys.exit(f"Download incomplete ({dest.stat().st_size:,} of {expected_bytes:,} bytes). "
                 "Run the same command again; it continues where it stopped.")
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
                shutil.copyfileobj(src, dst)
            n += 1
    return n


def copy_dir(src: Path, out_dir: Path) -> int:
    n = 0
    for f in src.rglob("*"):
        if f.is_file():
            t = out_dir / f.relative_to(src)
            if t.exists() and t.stat().st_size == f.stat().st_size:
                continue
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            n += 1
    return n


def fetch(example: str, home: Path, zip_path: str | None = None, from_dir: str | None = None) -> int:
    src = yaml.safe_load((ROOT / "examples" / example / "data_source.yaml").read_text(encoding="utf-8"))
    out_dir = home / "example-data" / example / src["extract_to"]
    expected = src["expected_files"]
    if not [f for f in expected if not (out_dir / f).exists()]:
        print(f"all {len(expected)} expected files already present in {out_dir}")
        return 0
    if from_dir:
        if not Path(from_dir).is_dir():
            print(f"Folder not found: {from_dir}")
            return 1
        n = copy_dir(Path(from_dir), out_dir)
        how = f"copied {n} files from {from_dir}"
    else:
        zpath = Path(zip_path) if zip_path else download(src["url"], home / "downloads" / src["file_name"],
                                                         src.get("bytes"))
        n = extract(zpath, src["members_prefix"], out_dir)
        how = f"extracted {n} files from {zpath}"
    still = [f for f in expected if not (out_dir / f).exists()]
    print(f"{how} to {out_dir}; missing afterwards: {', '.join(still) if still else 'none'}")
    return 1 if still else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--example", default="01_nasa_hecc")
    p.add_argument("--home", help="install home (default: ANSYS_RERATE_HOME or LOCALAPPDATA/ansys-rerate-agent)")
    p.add_argument("--zip", help="use an archive you already downloaded")
    p.add_argument("--from-dir", help="copy an existing extracted geometry_data folder (testing only)")
    a = p.parse_args()
    return fetch(a.example, install_home(a.home), a.zip, a.from_dir)


if __name__ == "__main__":
    sys.exit(main())
