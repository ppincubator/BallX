"""Run pinned local artifacts without network access and emit an auditable report."""

import argparse
import json
import sys
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from ballx.db.session import get_engine
from ballx.ingestion.manifest import load_manifest
from ballx.ingestion.pilot import prepare
from ballx.ingestion.pipeline import run_manifest
from ballx.ingestion.report import quality_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser(
        "run", help="Replay at most 25 matches; preserve rejected raw records"
    )
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--report", type=Path, required=True)
    sample = commands.add_parser(
        "prepare", help="Download and freeze the fixed five-match real pilot"
    )
    sample.add_argument("--directory", type=Path, required=True)
    sample.add_argument("--cache", type=Path, default=Path("work/provider-cache"))
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            print(prepare(args.directory, args.cache))
            return 0
        manifest, digest = load_manifest(args.manifest)
        with Session(get_engine()) as session, session.begin():
            ingestion_run = run_manifest(session, manifest, digest, args.manifest.parent)
            report = quality_report(session, ingestion_run)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "report": str(args.report),
                    "counts": report["counts"],
                    "passed": report["validation"]["passed"],
                }
            )
        )
        return 0 if report["validation"]["passed"] else 2
    except (ValueError, OSError, httpx.HTTPError) as exc:
        print(f"Ingestion failed before completion: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
