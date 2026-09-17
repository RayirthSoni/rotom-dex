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
    p.add_argument("--format", choices=("json", "markdown", "backlog"), default="json")

    p = sub.add_parser("content-audit", help="Review knowledge applicability, sources, conflicts and capability inventories")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--publish", type=Path, default=None, help="Write a new immutable sidecar snapshot after checks")

    p = sub.add_parser("query", help="Look up a Pokémon in an exact game")
    p.add_argument("pokemon", help="Slug or national number")
    p.add_argument("--game", required=True)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--level", type=int)

    p = sub.add_parser("eval", help="Grade the reviewed question set against the domain services")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--questions", type=Path, default=None)
    p.add_argument("--category", default=None, help="Grade only one category")
    p.add_argument("--live", action="store_true", help="Also grade model-written answers (needs a provider credential)")

    p = sub.add_parser("serve", help="Run the FastAPI server")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true", help="Restart on source changes (development)")
    p.add_argument(
        "--cors",
        nargs="*",
        default=None,
        metavar="ORIGIN",
        help="Allow these browser origins. Omit when the frontend is proxied or served from web/dist.",
    )
    p.add_argument("--no-web", dest="web", action="store_false", help="Serve the API only, ignoring web/dist")
    p.set_defaults(web=True)

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
            if args.cors:
                os.environ["ROTOM_CORS_ORIGINS"] = ",".join(args.cors)
            if not args.web:
                os.environ["ROTOM_SERVE_WEB"] = "0"
            uvicorn.run("rotom_dex.api.app:app", host=args.host, port=args.port, reload=args.reload)
            return 0
        else:
            from rotom_dex.db.connection import connect
            from rotom_dex.db.migrations import check_current

            db = connect(args.db, readonly=True)
            try:
                check_current(db)
                if args.command == "content-audit":
                    from rotom_dex.services import content

                    result = content.publish(db, args.publish) if args.publish else content.audit(db)
                elif args.command == "check":
                    from rotom_dex.ingestion.pipeline import table_counts, validate_database

                    validate_database(db)
                    result = {"status": "ok", "counts": table_counts(db)}
                elif args.command == "eval":
                    from rotom_dex.chat.config import ChatConfig
                    from rotom_dex.evaluation import runner as eval_runner

                    questions = eval_runner.load(args.questions) if args.questions else eval_runner.load()
                    if args.category:
                        questions = [q for q in questions if q["category"] == args.category]
                    report = eval_runner.run(db, questions)
                    result = report.summary()
                    result["skipped"] = report.skipped
                    if args.live:
                        config = ChatConfig.from_env()
                        if not config.enabled:
                            result["live_error"] = "Set ROTOM_GEMINI_API_KEY for explicitly requested local live evaluation."
                        else:
                            from rotom_dex.evaluation.live import run as run_live

                            result["live"] = run_live(db, questions, config)
                            result["live_graded"] = True
                elif args.command == "coverage":
                    from rotom_dex.repositories.coverage import coverage_report, render_backlog, render_markdown

                    report = coverage_report(db, args.game)
                    if args.format == "markdown":
                        print(render_markdown(report))
                        return 0
                    if args.format == "backlog":
                        print(render_backlog(report))
                        return 0
                    result = report
                else:
                    from rotom_dex.repositories.pokemon import pokemon_detail

                    result = pokemon_detail(db, args.game, args.pokemon, args.level)
            finally:
                db.close()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if result.get("failed", 0) or result.get("errors") or result.get("conflicts") or result.get("live_error") or result.get("live", {}).get("failed", 0) else 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
