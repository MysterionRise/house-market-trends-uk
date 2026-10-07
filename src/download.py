"""Download engine for UK Liveability Index datasets.

Usage:
    python -m src.download --phase 1        # download all Phase 1 datasets
    python -m src.download --slug nspl      # download a single dataset
    python -m src.download --force          # re-download even if cached
"""

import argparse
import fnmatch
import hashlib
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

from src.utils import ensure_dirs, get_config, get_project_root, setup_logging

logger = setup_logging("download")

CHUNK_SIZE = 1024 * 1024

# Leading bytes each binary format must start with. ArcGIS and GOV.UK sometimes answer
# a bad request with HTTP 200 and a JSON or HTML error body, so we check before trusting it.
MAGIC_BYTES = {
    "zip": [b"PK\x03\x04"],
    "xlsx": [b"PK\x03\x04"],
    "ods": [b"PK\x03\x04"],
    "gpkg": [b"SQLite format 3\x00"],
    "parquet": [b"PAR1"],
}
ERROR_BODY_PREFIXES = (b"{", b"<!doctype", b"<html", b"<?xml")


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


def _safe_extract(
    zf: zipfile.ZipFile, dest_dir: Path, patterns: list[str] | None = None
) -> list[str]:
    """Extract a ZIP archive with path traversal protection (Zip Slip guard).

    If ``patterns`` is given, only members matching one of the glob patterns are extracted.
    Returns the names of the extracted members.
    """
    dest_dir = dest_dir.resolve()
    members = [m for m in zf.infolist() if not m.is_dir()]
    for member in zf.infolist():
        member_path = (dest_dir / member.filename).resolve()
        # is_relative_to, not str.startswith: "data/nspl_evil" starts with "data/nspl"
        if not member_path.is_relative_to(dest_dir):
            raise ValueError(
                f"ZIP entry {member.filename!r} would extract outside destination directory"
            )
    if patterns:
        members = [m for m in members if any(fnmatch.fnmatch(m.filename, p) for p in patterns)]
        if not members:
            raise ValueError(f"No ZIP entries match {patterns!r}")
    for member in members:
        zf.extract(member, dest_dir)
    return [m.filename for m in members]


def _session() -> requests.Session:
    """HTTP session that retries transient failures with exponential backoff."""
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "uk-liveability-index/0.1"
    return session


def _check_payload(path: Path, fmt: str) -> None:
    """Raise if the downloaded file is an error page instead of the expected format."""
    with open(path, "rb") as f:
        head = f.read(64)
    expected = MAGIC_BYTES.get(fmt)
    if expected is not None:
        if not any(head.startswith(m) for m in expected):
            raise ValueError(f"Downloaded file is not a valid {fmt} (starts with {head[:32]!r})")
    elif head.lstrip().lower().startswith(ERROR_BODY_PREFIXES) and fmt not in (
        "json",
        "geojson",
        "xml",
    ):
        raise ValueError(f"Downloaded {fmt} looks like an error page: {head[:32]!r}")


def download_dataset(slug: str, force: bool = False) -> Path:
    """Download a single dataset by its slug from datasets.yaml.

    Downloads stream to ``{file}.part`` and resume with an HTTP Range request if a
    previous attempt was interrupted. The finished file is moved into place atomically.

    Returns the path to the downloaded (and possibly extracted) directory.
    """
    datasets = get_config("datasets")
    if slug not in datasets:
        raise ValueError(f"Unknown dataset slug: {slug!r}. Available: {list(datasets.keys())}")

    ds = datasets[slug]
    url = ds["download_url"]
    fmt = ds.get("format", "csv")
    dest_dir = get_project_root() / "data" / "raw" / slug

    # Check cache
    meta = _read_meta(dest_dir)
    if not force and meta.get("completed"):
        logger.info(f"[{slug}] Already downloaded — skipping (use --force to re-download)")
        return dest_dir

    dest_dir.mkdir(parents=True, exist_ok=True)
    out_file = dest_dir / f"{slug}.{fmt}"
    part_file = out_file.with_name(out_file.name + ".part")
    if force and part_file.exists():
        part_file.unlink()

    headers = {}
    resume_from = part_file.stat().st_size if part_file.exists() else 0
    # Only resume against the same remote version: If-Range makes the server send the
    # whole file (200) instead of a range if it changed since the partial was written.
    partial_validator = meta.get("partial_etag") or meta.get("partial_last_modified")
    if resume_from and partial_validator:
        headers["Range"] = f"bytes={resume_from}-"
        headers["If-Range"] = partial_validator
    elif resume_from:
        resume_from = 0
    if not resume_from and not force and meta.get("last_modified"):
        headers["If-Modified-Since"] = meta["last_modified"]

    logger.info(f"[{slug}] Downloading from {url}")
    # (connect, read) timeout; large files like price_paid (5.5GB) need generous reads
    resp = _session().get(url, headers=headers, stream=True, timeout=(30, 300))

    if resp.status_code == 304:
        logger.info(f"[{slug}] Not modified since last download — skipping")
        # Mark as completed since server confirms data hasn't changed
        meta["completed"] = True
        _write_meta(dest_dir, meta)
        return dest_dir

    resp.raise_for_status()

    sha256 = hashlib.sha256()
    if resume_from and resp.status_code == 206:
        logger.info(f"[{slug}] Resuming at {resume_from / 1e6:.1f} MB")
        with open(part_file, "rb") as f:
            for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                sha256.update(chunk)
        mode = "ab"
    else:
        # Nothing to resume, or the server sent the whole file (version changed or
        # Range unsupported): start over
        resume_from = 0
        mode = "wb"
        _write_meta(
            dest_dir,
            {
                "slug": slug,
                "url": url,
                "completed": False,
                "partial_etag": resp.headers.get("ETag"),
                "partial_last_modified": resp.headers.get("Last-Modified"),
            },
        )

    try:
        total_size = int(resp.headers.get("content-length", 0)) + resume_from
    except (ValueError, TypeError):
        total_size = 0

    try:
        with (
            open(part_file, mode) as f,
            tqdm(
                total=total_size,
                initial=resume_from,
                unit="B",
                unit_scale=True,
                desc=slug,
                disable=total_size == 0,
            ) as pbar,
        ):
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                f.write(chunk)
                sha256.update(chunk)
                pbar.update(len(chunk))
    except BaseException:
        # Keep the .part file so the next run can resume; never leave a file at out_file
        logger.error(f"[{slug}] Download interrupted — partial data kept in {part_file.name}")
        raise

    try:
        _check_payload(part_file, fmt)
    except ValueError:
        part_file.unlink()
        raise

    os.replace(part_file, out_file)
    size = out_file.stat().st_size
    logger.info(f"[{slug}] Saved to {out_file} ({size / 1e6:.1f} MB)")

    extracted = None
    if fmt == "zip":
        logger.info(f"[{slug}] Extracting ZIP archive...")
        with zipfile.ZipFile(out_file) as zf:
            extracted = _safe_extract(zf, dest_dir, ds.get("extract"))
        out_file.unlink()
        logger.info(f"[{slug}] Extracted {len(extracted)} file(s) to {dest_dir}")

    new_meta = {
        "slug": slug,
        "url": url,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "last_modified": resp.headers.get("Last-Modified"),
        "etag": resp.headers.get("ETag"),
        "bytes": size,
        "sha256": sha256.hexdigest(),
        "extracted": extracted,
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
