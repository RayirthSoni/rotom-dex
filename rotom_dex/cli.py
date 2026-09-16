"""Command line: `rotom import|check|coverage|query|serve|fetch-sources`."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from rotom_dex.settings import DEFAULT_DB


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="rotom", description="Offline multi-game Pokémon data foundation")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("import", help="Import selected games into a SQLite database (idempotent)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument(
        "--games",
        default="all",
        help="Comma-separated game slugs, or 'all' for every importable main-series game",
    )

    p = sub.add_parser("check", help="Run integrity and invariant checks")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)

    p = sub.add_parser("coverage", help="Print the coverage report (JSON or Markdown)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--game", default=None)
    p.add_argument("--format", choices=("json", "markdown"), default="json")

    p = sub.add_parser("query", help="Look up a Pokémon in an exact game")
    p.add_argument("pokemon", help="Slug or national number")
    p.add_argument("--game", required=True)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--level", type=int)

    p = sub.add_parser("serve", help="Run the FastAPI server")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)

    p = sub.add_parser("fetch-sources", help="Restore or extend the pinned source cache (network)")
    p.add_argument("--add", nargs="*", default=None, metavar="NAME")

    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            from rotom_dex.ingestion.pipeline import import_games

            games = None if args.games == "all" else [g.strip() for g in args.games.split(",") if g.strip()]
            result = import_games(args.db, games)
        elif args.command == "fetch-sources":
            from rotom_dex.ingestion import fetch

            result = fetch.add(args.add) if args.add is not None else {"restored": fetch.restore()}
        elif args.command == "serve":
            import os

            import uvicorn

            os.environ["ROTOM_DB"] = str(args.db)
            uvicorn.run("rotom_dex.api.app:app", host=args.host, port=args.port)
            return 0
        else:
            from rotom_dex.db.connection import connect
            from rotom_dex.db.migrations import check_current

            db = connect(args.db, readonly=True)
            try:
                check_current(db)
                if args.command == "check":
                    from rotom_dex.ingestion.pipeline import table_counts, validate_database

                    validate_database(db)
                    result = {"status": "ok", "counts": table_counts(db)}
                elif args.command == "coverage":
                    from rotom_dex.repositories.coverage import coverage_report, render_markdown

                    report = coverage_report(db, args.game)
                    if args.format == "markdown":
                        print(render_markdown(report))
                        return 0
                    result = report
                else:
                    from rotom_dex.repositories.pokemon import pokemon_detail

                    result = pokemon_detail(db, args.game, args.pokemon, args.level)
            finally:
                db.close()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
