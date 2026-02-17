"""Download engine for UK Liveability Index datasets.

Usage:
    python -m src.download --phase 1        # download all Phase 1 datasets
    python -m src.download --slug nspl      # download a single dataset
    python -m src.download --force          # re-download even if cached
"""

import argparse
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from tqdm import tqdm

from src.utils import ensure_dirs, get_config, get_project_root, setup_logging

logger = setup_logging("download")


def _meta_path(dest_dir: Path) -> Path:
    return dest_dir / ".meta.json"


def _read_meta(dest_dir: Path) -> dict:
    mp = _meta_path(dest_dir)
    if mp.exists():
        with open(mp) as f:
            return json.load(f)
    return {}


def _write_meta(dest_dir: Path, meta: dict) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with open(_meta_path(dest_dir), "w") as f:
        json.dump(meta, f, indent=2)


def _safe_extract(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    """Extract ZIP archive with path traversal protection (Zip Slip guard)."""
    dest_dir = dest_dir.resolve()
    for member in zf.infolist():
        member_path = (dest_dir / member.filename).resolve()
        if not str(member_path).startswith(str(dest_dir)):
            raise ValueError(
                f"ZIP entry {member.filename!r} would extract outside destination directory"
            )
    zf.extractall(dest_dir)


def download_dataset(slug: str, force: bool = False) -> Path:
    """Download a single dataset by its slug from datasets.yaml.

    Returns the path to the downloaded (and possibly extracted) directory.
    """
    datasets = get_config("datasets")
    if slug not in datasets:
        raise ValueError(f"Unknown dataset slug: {slug!r}. Available: {list(datasets.keys())}")

    ds = datasets[slug]
    url = ds["download_url"]
    fmt = ds.get("format", "csv")
    dest_base = ds.get("dest_dir", f"data/raw/{slug}")
    root = get_project_root()
    dest_dir = root / dest_base

    # Check cache
    meta = _read_meta(dest_dir)
    if not force and meta.get("completed"):
        logger.info(f"[{slug}] Already downloaded — skipping (use --force to re-download)")
        return dest_dir

    dest_dir.mkdir(parents=True, exist_ok=True)

    # Build request headers
    headers = {"User-Agent": "uk-liveability-index/0.1"}
    if not force and meta.get("last_modified"):
        headers["If-Modified-Since"] = meta["last_modified"]

    logger.info(f"[{slug}] Downloading from {url}")
    # Use tuple timeout: (connect_timeout, read_timeout)
    # Large files like price_paid (4.3GB) need generous read timeouts
    resp = requests.get(url, headers=headers, stream=True, timeout=(30, 300))

    if resp.status_code == 304:
        logger.info(f"[{slug}] Not modified since last download — skipping")
        # Mark as completed since server confirms data hasn't changed
        meta["completed"] = True
        _write_meta(dest_dir, meta)
        return dest_dir

    resp.raise_for_status()

    # Determine output filename
    if fmt == "zip":
        out_file = dest_dir / f"{slug}.zip"
    elif fmt == "gpkg":
        out_file = dest_dir / f"{slug}.gpkg"
    elif fmt == "xlsx":
        out_file = dest_dir / f"{slug}.xlsx"
    else:
        out_file = dest_dir / f"{slug}.csv"

    # Stream download to a temp file first, then atomically move to dest.
    # This prevents partial files from being consumed by downstream modules.
    try:
        total_size = 0
        try:
            total_size = int(resp.headers.get("content-length", 0))
        except (ValueError, TypeError):
            total_size = 0

        tmp_fd, tmp_path = tempfile.mkstemp(dir=dest_dir, suffix=".download")
        try:
            with os.fdopen(tmp_fd, "wb") as f, tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                desc=slug,
                disable=total_size == 0,
            ) as pbar:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    pbar.update(len(chunk))

            # Atomic move from temp to final destination
            os.replace(tmp_path, out_file)
        except BaseException:
            # Clean up temp file on any failure (including KeyboardInterrupt)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except BaseException:
        logger.error(f"[{slug}] Download interrupted — no partial files left on disk")
        raise

    logger.info(
        f"[{slug}] Saved to {out_file} ({out_file.stat().st_size / 1e6:.1f} MB)"
    )

    # Extract ZIP if needed
    if fmt == "zip":
        logger.info(f"[{slug}] Extracting ZIP archive...")
        with zipfile.ZipFile(out_file) as zf:
            _safe_extract(zf, dest_dir)
        out_file.unlink()
        logger.info(f"[{slug}] Extracted to {dest_dir}")

    # Update metadata
    new_meta = {
        "slug": slug,
        "url": url,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "last_modified": resp.headers.get("Last-Modified"),
        "completed": True,
    }
    _write_meta(dest_dir, new_meta)

    return dest_dir


def download_all(phase: int | None = None, force: bool = False) -> dict[str, Path]:
    """Download all datasets, optionally filtered by phase."""
    datasets = get_config("datasets")
    results = {}

    for slug, ds in datasets.items():
        if phase is not None and ds.get("phase") != phase:
            continue
        try:
            results[slug] = download_dataset(slug, force=force)
        except Exception:
            logger.exception(f"[{slug}] Download failed")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Download UK Liveability Index datasets")
    parser.add_argument("--slug", type=str, help="Download a single dataset by slug")
    parser.add_argument("--phase", type=int, help="Download all datasets for a given phase")
    parser.add_argument("--force", action="store_true", help="Force re-download even if cached")
    args = parser.parse_args()

    ensure_dirs()

    if args.slug:
        download_dataset(args.slug, force=args.force)
    else:
        phase = args.phase
        download_all(phase=phase, force=args.force)


if __name__ == "__main__":
    main()
