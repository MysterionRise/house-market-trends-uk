"""``lix`` command line: fetch raw data, stage it to Parquet.

lix fetch --slug nspl          # one dataset
lix fetch --all                # every dataset in config/datasets.yaml
lix stage --slug price_paid    # one stager
lix stage --all                # every stager whose raw data is present
"""

import argparse

from lix_core.config import get_config
from lix_core.log import setup_logging
from lix_core.paths import data_dir, ensure_dirs
from lix_pipeline.fetch.http import download_all, download_dataset
from lix_pipeline.stage import save_staged, stagers

logger = setup_logging("cli")


def _fetch(args: argparse.Namespace) -> None:
    if args.slug:
        download_dataset(args.slug, force=args.force)
    else:
        download_all(phase=args.phase, force=args.force)


def _stage(args: argparse.Namespace) -> None:
    available = stagers()
    if args.slug and args.slug not in available:
        raise SystemExit(f"Unknown slug: {args.slug!r}. Available: {list(available)}")

    for slug in [args.slug] if args.slug else list(available):
        if args.all and not (data_dir("raw") / slug / ".meta.json").exists():
            logger.info(f"[{slug}] No raw data — skipping (run `lix fetch --slug {slug}` first)")
            continue
        save_staged(available[slug](), slug)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lix", description="UK Liveability Index pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Download raw datasets into data/raw/")
    which = fetch.add_mutually_exclusive_group(required=True)
    which.add_argument("--slug", choices=sorted(get_config("datasets")), help="One dataset")
    which.add_argument("--phase", type=int, help="Every dataset in a phase")
    which.add_argument("--all", action="store_true", help="Every dataset")
    fetch.add_argument("--force", action="store_true", help="Re-download even if cached")
    fetch.set_defaults(func=_fetch)

    stage = sub.add_parser("stage", help="Stage raw datasets to data/staged/*.parquet")
    which = stage.add_mutually_exclusive_group(required=True)
    which.add_argument("--slug", help="One stager")
    which.add_argument("--all", action="store_true", help="Every stager with raw data")
    stage.set_defaults(func=_stage)

    args = parser.parse_args(argv)
    ensure_dirs()
    args.func(args)


if __name__ == "__main__":
    main()
