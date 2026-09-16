"""Run from the repository root: python3 -m src.cli --help."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from src.database.connection import connect
from src.ingestion.emerald import import_emerald, table_counts, validate_database
from src.repositories.pokemon import lookup_pokemon, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline Emerald data foundation")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("import", "query", "coverage", "check"):
        command = sub.add_parser(name)
        command.add_argument("--db", type=Path, default=Path("data/rotom.sqlite3"))
        if name == "query":
            command.add_argument(
                "pokemon", help="Slug or national Pokédex number in the sample"
            )
            command.add_argument(
                "--game", required=True, help="Exact game, e.g. emerald"
            )
            command.add_argument("--level", type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            args.db.parent.mkdir(parents=True, exist_ok=True)
            result = import_emerald(args.db)
        else:
            db = connect(args.db, readonly=True)
            try:
                if args.command == "query":
                    result = lookup_pokemon(db, args.pokemon, args.game, args.level)
                elif args.command == "coverage":
                    result = rows(
                        db,
                        "SELECT g.slug AS game,c.* FROM coverage c JOIN game_versions g ON g.id=c.game_id ORDER BY game,subject,feature",
                    )
                else:
                    validate_database(db)
                    result = {"status": "ok", "counts": table_counts(db)}
            finally:
                db.close()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
