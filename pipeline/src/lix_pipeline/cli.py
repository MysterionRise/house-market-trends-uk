"""``lix`` command line.

lix resolve --all              # pin every dataset's current URL in datasets.lock.json
lix resolve --check --all      # is every source still reachable? (nightly link check)
lix fetch --theme geography    # download what the lockfile pins
lix stage --all                # every stager whose inputs are fetched
lix validate geo               # check the geography backbone
"""

import argparse
import sys

from lix_core.config import load_registry
from lix_core.log import setup_logging
from lix_core.paths import data_dir, ensure_dirs
from lix_pipeline.fetch import (
    ManualDownloadRequired,
    check_link,
    fetch,
    resolve_and_lock,
    select,
)
from lix_pipeline.fetch.session import make_session
from lix_pipeline.stage import STAGE_INPUTS, save_staged, stagers

logger = setup_logging("cli")


def _selected(args: argparse.Namespace) -> list[str]:
    return select(
        load_registry(),
        slugs=[args.slug] if args.slug else None,
        theme=args.theme,
        priority=args.priority,
    )


def _resolve(args: argparse.Namespace) -> int:
    registry, session = load_registry(), make_session()
    failures = 0
    for slug in _selected(args):
        if args.check:
            ok, note = check_link(slug, registry[slug], session)
            print(f"{'ok  ' if ok else 'FAIL'} {slug:24} {note}")
            failures += not ok
        else:
            resolved = resolve_and_lock(slug, registry[slug], session)
            print(f"{slug:24} {resolved.get('title') or ''} {resolved.get('version') or ''}")
    return 1 if failures else 0


def _fetch(args: argparse.Namespace) -> int:
    registry, session = load_registry(), make_session()
    missing_manual, failed = [], []
    for slug in _selected(args):
        try:
            fetch(slug, force=args.force, strict=args.strict, session=session, registry=registry)
        except ManualDownloadRequired as e:
            missing_manual.append(str(e))
        except Exception:
            logger.exception(f"[{slug}] Fetch failed")
            failed.append(slug)
    for msg in missing_manual:
        logger.warning(msg)
    if failed:
        logger.error(f"Failed: {failed}")
    return 1 if failed else 0


def _has_inputs(slug: str) -> bool:
    raw = data_dir("raw")
    return all((raw / s / ".meta.json").exists() for s in STAGE_INPUTS.get(slug, [slug]))


def _stage(args: argparse.Namespace) -> int:
    available = stagers()
    if args.slug and args.slug not in available:
        raise SystemExit(f"Unknown stager: {args.slug!r}. Available: {list(available)}")

    for slug in [args.slug] if args.slug else list(available):
        if args.all and not _has_inputs(slug):
            logger.info(f"[{slug}] Inputs not fetched — skipping")
            continue
        save_staged(available[slug](), slug)
    return 0


def _validate(args: argparse.Namespace) -> int:
    from lix_pipeline.qa.validate import VALIDATORS

    problems = VALIDATORS[args.target]()
    for p in problems:
        print(f"FAIL {p}")
    print(f"{args.target}: {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


def _add_selection(parser: argparse.ArgumentParser) -> None:
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--slug", help="One dataset")
    which.add_argument("--theme", help="Every dataset in a theme (e.g. geography)")
    which.add_argument("--priority", choices=["P0", "P1", "P2"], help="Every dataset of a priority")
    which.add_argument("--all", action="store_true", help="Every dataset")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lix", description="UK Liveability Index pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve", help="Pin each dataset's current URL in the lockfile")
    _add_selection(resolve)
    resolve.add_argument(
        "--check", action="store_true", help="Only check sources are reachable; exit 1 if not"
    )
    resolve.set_defaults(func=_resolve)

    fetch_p = sub.add_parser("fetch", help="Download datasets into data/raw/")
    _add_selection(fetch_p)
    fetch_p.add_argument("--force", action="store_true", help="Re-download even if cached")
    fetch_p.add_argument(
        "--strict", action="store_true", help="Fail if a file differs from the lockfile checksum"
    )
    fetch_p.set_defaults(func=_fetch)

    stage = sub.add_parser("stage", help="Stage raw datasets to data/staged/*.parquet")
    which = stage.add_mutually_exclusive_group(required=True)
    which.add_argument("--slug", help="One stager")
    which.add_argument("--all", action="store_true", help="Every stager whose inputs are fetched")
    stage.set_defaults(func=_stage)

    validate = sub.add_parser("validate", help="Check staged outputs")
    validate.add_argument("target", choices=["geo"])
    validate.set_defaults(func=_validate)

    args = parser.parse_args(argv)
    ensure_dirs()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
