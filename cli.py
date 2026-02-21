"""
rotom-dex unified CLI.

Single entry point for all project operations.

Usage
-----
# Scraping
python cli.py scrape pokeapi                    # full Gen 1-4 scrape
python cli.py scrape pokeapi --start 1 --end 151  # Gen 1 only
python cli.py scrape pokemondb                  # all games
python cli.py scrape pokemondb --game platinum  # one game
python cli.py scrape all                        # run both scrapers

# Pipeline
python cli.py pipeline build-docs               # Phase 2: JSON → text documents
python cli.py pipeline embed                    # Phase 3: embed + store in ChromaDB
python cli.py pipeline refresh                  # build-docs + embed in one shot

# Chatbot
python cli.py chat "best team for elite 4 in platinum"   # single query
python cli.py chat --interactive                          # REPL mode

# Dev / debug
python cli.py debug search "haunter location platinum"   # inspect retriever
python cli.py debug stats                                 # show DB stats
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Logging setup — must happen before importing project modules
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------


def cmd_scrape_pokeapi(args: argparse.Namespace) -> None:
    from src.scraper.pokeapi import GEN1_4_RANGE, PokeAPIScraper
    from src.scraper.base import ScrapeConfig

    config = ScrapeConfig(
        cache_dir=Path(args.cache_dir),
        output_dir=Path(args.output_dir),
        calls_per_second=args.rps,
    )
    scraper = PokeAPIScraper(config=config)
    dex_range = range(args.start, args.end + 1)

    if args.only:
        dispatch = {
            "pokemon": lambda: scraper.scrape_all_pokemon(dex_range=dex_range),
            "moves": scraper.scrape_all_moves,
            "abilities": scraper.scrape_all_abilities,
            "types": scraper.scrape_all_types,
        }
        dispatch[args.only]()
    else:
        scraper.scrape_all(dex_range=dex_range)


def cmd_scrape_pokemondb(args: argparse.Namespace) -> None:
    from src.scraper.pokemondb import ALL_VERSION_GROUPS, PokemonDBScraper
    from src.scraper.base import ScrapeConfig

    config = ScrapeConfig(
        cache_dir=Path(args.cache_dir),
        output_dir=Path(args.output_dir),
        calls_per_second=args.rps,
    )
    scraper = PokemonDBScraper(config=config)

    if args.game and args.game != "all":
        scraper.scrape_version_group(args.game)
    else:
        scraper.scrape_all()


def cmd_scrape_all(args: argparse.Namespace) -> None:
    """Run both scrapers sequentially."""
    cmd_scrape_pokeapi(args)
    cmd_scrape_pokemondb(args)


def cmd_build_docs(args: argparse.Namespace) -> None:
    """Phase 2: convert raw JSON → text documents."""
    from pipeline.document_builder import DocumentBuilder  # implement next

    builder = DocumentBuilder(
        raw_dir=Path(args.raw_dir),
        output_dir=Path(args.docs_dir),
    )
    builder.build_all()


def cmd_embed(args: argparse.Namespace) -> None:
    """Phase 3: embed documents and store in ChromaDB."""
    from pipeline.embedder import Embedder  # implement next

    embedder = Embedder(
        docs_dir=Path(args.docs_dir),
        vector_store_dir=Path(args.vector_store_dir),
    )
    embedder.embed_all()


def cmd_chat(args: argparse.Namespace) -> None:
    """Run a single query or start an interactive REPL."""
    from src.chatbot.engine import ChatEngine  # implement next

    engine = ChatEngine()

    if args.interactive:
        print("Rotom-Dex interactive mode. Type 'quit' to exit.\n")
        while True:
            try:
                question = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if question.lower() in ("quit", "exit", "q"):
                break
            if not question:
                continue
            answer = engine.answer(question, game=args.game)
            print(f"\nRotom-Dex: {answer}\n")
    elif args.question:
        answer = engine.answer(args.question, game=args.game)
        print(answer)
    else:
        print("Provide a question or use --interactive.", file=sys.stderr)
        sys.exit(1)


def cmd_debug_search(args: argparse.Namespace) -> None:
    """Show raw retriever output for a query — useful during development."""
    from src.chatbot.retriever import Retriever  # implement next

    retriever = Retriever()
    results = retriever.search(args.query, game_filter=args.game, top_k=args.top_k)
    for i, doc in enumerate(results, 1):
        print(f"\n{'─' * 60}")
        print(f"[{i}] score={doc.get('score', '?'):.3f}  id={doc.get('id', '?')}")
        print(f"metadata: {doc.get('metadata', {})}")
        print(doc.get("text", "")[:500])
    print(f"\n{'─' * 60}")
    print(f"{len(results)} documents retrieved.")


def cmd_debug_stats(args: argparse.Namespace) -> None:
    """Print a summary of the vector store and raw data directories."""
    raw_dir = Path(args.raw_dir)
    print("\n📁 Raw data summary")
    for subdir in sorted(raw_dir.iterdir()):
        if subdir.is_dir() and subdir.name != "scraper_cache":
            count = sum(1 for _ in subdir.rglob("*.json"))
            print(f"  {subdir.name:30s} {count:>5} JSON files")

    vector_store = Path(args.vector_store_dir)
    if vector_store.exists():
        size_mb = sum(f.stat().st_size for f in vector_store.rglob("*") if f.is_file()) / 1e6
        print(f"\n🗄️  Vector store: {vector_store}  ({size_mb:.1f} MB)")
    else:
        print(f"\n🗄️  Vector store not yet built at {vector_store}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="rotom-dex",
        description="rotom-dex Pokemon RAG chatbot — unified CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    root.add_argument("-v", "--verbose", action="store_true", help="Debug logging")

    # ---- shared / default paths ----
    root.add_argument("--raw-dir", default="data/raw", metavar="DIR")
    root.add_argument("--docs-dir", default="data/docs", metavar="DIR")
    root.add_argument("--vector-store-dir", default="data/vector_store", metavar="DIR")
    root.add_argument("--cache-dir", default="data/raw/scraper_cache", metavar="DIR")
    root.add_argument("--output-dir", default="data/raw", metavar="DIR")

    subparsers = root.add_subparsers(dest="command", required=True)

    # ================================================================
    # scrape
    # ================================================================
    scrape_p = subparsers.add_parser("scrape", help="Fetch data from upstream sources")
    scrape_sub = scrape_p.add_subparsers(dest="source", required=True)

    # -- scrape pokeapi --
    pa = scrape_sub.add_parser("pokeapi", help="Scrape https://pokeapi.co")
    pa.add_argument("--start", type=int, default=1, help="First national dex number")
    pa.add_argument("--end", type=int, default=493, help="Last national dex number")
    pa.add_argument("--rps", type=float, default=1.5, help="Requests per second")
    pa.add_argument(
        "--only",
        choices=["pokemon", "moves", "abilities", "types"],
        default=None,
        help="Scrape only one category",
    )
    pa.set_defaults(func=cmd_scrape_pokeapi)

    # -- scrape pokemondb --
    pb = scrape_sub.add_parser("pokemondb", help="Scrape https://pokemondb.net")
    pb.add_argument(
        "--game",
        default="all",
        help="Version-group slug or 'all'  (e.g. platinum)",
    )
    pb.add_argument("--rps", type=float, default=0.8)
    pb.set_defaults(func=cmd_scrape_pokemondb)

    # -- scrape all --
    pa2 = scrape_sub.add_parser("all", help="Run all scrapers")
    pa2.add_argument("--start", type=int, default=1)
    pa2.add_argument("--end", type=int, default=493)
    pa2.add_argument("--rps", type=float, default=1.5)
    pa2.set_defaults(func=cmd_scrape_all)

    # ================================================================
    # pipeline
    # ================================================================
    pipe_p = subparsers.add_parser("pipeline", help="Build and embed documents")
    pipe_sub = pipe_p.add_subparsers(dest="step", required=True)

    pipe_sub.add_parser("build-docs", help="Convert raw JSON → text documents").set_defaults(
        func=cmd_build_docs
    )
    pipe_sub.add_parser("embed", help="Embed documents into ChromaDB").set_defaults(
        func=cmd_embed
    )
    refresh = pipe_sub.add_parser("refresh", help="build-docs + embed")
    refresh.set_defaults(func=lambda a: (cmd_build_docs(a), cmd_embed(a)))

    # ================================================================
    # chat
    # ================================================================
    chat_p = subparsers.add_parser("chat", help="Query the chatbot")
    chat_p.add_argument("question", nargs="?", help="Question to ask")
    chat_p.add_argument("--game", default=None, help="Filter by game version-group")
    chat_p.add_argument("-i", "--interactive", action="store_true", help="REPL mode")
    chat_p.set_defaults(func=cmd_chat)

    # ================================================================
    # debug
    # ================================================================
    debug_p = subparsers.add_parser("debug", help="Development / inspection tools")
    debug_sub = debug_p.add_subparsers(dest="tool", required=True)

    ds = debug_sub.add_parser("search", help="Show raw retriever results")
    ds.add_argument("query", help="Search query")
    ds.add_argument("--game", default=None)
    ds.add_argument("--top-k", type=int, default=5)
    ds.set_defaults(func=cmd_debug_search)

    debug_sub.add_parser("stats", help="Print data directory summary").set_defaults(
        func=cmd_debug_stats
    )

    return root


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose)

    # Dispatch to the appropriate handler
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
