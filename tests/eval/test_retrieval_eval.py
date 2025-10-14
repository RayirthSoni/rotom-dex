from pathlib import Path

from analysis.vector_index import SimpleVectorIndex
from eval.retrieval_eval import evaluate, load_questions


def test_retrieval_evaluation_scores_are_reasonable():
    metadata_path = Path("data/pokemon_metadata.json")
    questions_path = Path("data/retrieval_questions.json")
    index = SimpleVectorIndex.from_metadata(metadata_path)
    questions = load_questions(questions_path)

    result = evaluate(index, questions, top_k=5)

    assert result.hit_rate >= 0.5
    assert result.mrr >= 0.5
    assert len(result.details) == len(questions)
