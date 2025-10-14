"""Command line utility to evaluate retrieval quality of the vector index."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.vector_index import SimpleVectorIndex


@dataclass
class Question:
    question: str
    answers: Sequence[str]


@dataclass
class EvaluationResult:
    hit_rate: float
    mrr: float
    details: List[Dict[str, object]]


def load_questions(path: str | Path) -> List[Question]:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return [Question(question=item["question"], answers=item["answers"]) for item in payload]


def evaluate(
    index: SimpleVectorIndex, questions: Iterable[Question], top_k: int
) -> EvaluationResult:
    total = 0
    hits = 0
    mrr_total = 0.0
    details: List[Dict[str, object]] = []

    for query in questions:
        total += 1
        results = index.search(query.question, top_k=top_k)
        ranked_ids = [doc_id for doc_id, _ in results]
        reciprocal_rank = 0.0
        for position, doc_id in enumerate(ranked_ids, start=1):
            if doc_id in query.answers:
                hits += 1
                reciprocal_rank = 1.0 / position
                break
        else:
            details.append({
                "question": query.question,
                "answers": list(query.answers),
                "ranking": ranked_ids,
                "hit": False,
            })
            continue

        mrr_total += reciprocal_rank
        details.append({
            "question": query.question,
            "answers": list(query.answers),
            "ranking": ranked_ids,
            "hit": True,
            "reciprocal_rank": reciprocal_rank,
        })

    hit_rate = hits / total if total else 0.0
    mrr = mrr_total / total if total else 0.0
    return EvaluationResult(hit_rate=hit_rate, mrr=mrr, details=details)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metadata",
        default=Path("data/pokemon_metadata.json"),
        help="Path to the Pokémon metadata JSON file used to build the index.",
    )
    parser.add_argument(
        "--questions",
        default=Path("data/retrieval_questions.json"),
        help="Path to labelled evaluation questions.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of documents to retrieve.")
    parser.add_argument(
        "--min-hit-rate",
        type=float,
        default=0.0,
        help="Fail the evaluation if hit-rate falls below this threshold.",
    )
    parser.add_argument(
        "--min-mrr",
        type=float,
        default=0.0,
        help="Fail the evaluation if MRR falls below this threshold.",
    )
    args = parser.parse_args()

    index = SimpleVectorIndex.from_metadata(args.metadata)
    questions = load_questions(args.questions)
    result = evaluate(index, questions, top_k=args.top_k)

    print(json.dumps({"hit_rate": result.hit_rate, "mrr": result.mrr, "details": result.details}, indent=2))

    if result.hit_rate < args.min_hit_rate or result.mrr < args.min_mrr:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
