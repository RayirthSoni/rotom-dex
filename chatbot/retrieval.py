"""Utilities to query the Pokémon knowledge base."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.errors import InvalidCollectionError

try:  # pragma: no cover - optional dependency during runtime
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - optional dependency
    BM25Okapi = None  # type: ignore

LOGGER = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Structure returned by the retrieval helpers."""

    id: str
    text: str
    score: float
    metadata: Dict[str, Any]


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


class KnowledgeBaseRetriever:
    """Wrapper around the vector store with optional BM25 scoring."""

    def __init__(
        self,
        vector_store_path: Path,
        collection_name: str = "pokemon-kb",
        documents_path: Optional[Path] = None,
        enable_bm25: bool = True,
    ) -> None:
        self._client = chromadb.PersistentClient(path=str(vector_store_path))
        try:
            self._collection = self._client.get_collection(collection_name)
        except InvalidCollectionError:
            LOGGER.info("Collection %s did not exist. Creating a new one.", collection_name)
            self._collection = self._client.get_or_create_collection(collection_name)
        self._documents_map: Dict[str, Dict[str, Any]] = {}
        self._bm25 = None
        self._bm25_ids: List[str] = []
        if documents_path and documents_path.exists():
            self._load_documents(documents_path)
        if enable_bm25 and BM25Okapi and self._documents_map:
            tokenised_corpus = [_tokenize(doc["text"]) for doc in self._documents_map.values()]
            self._bm25 = BM25Okapi(tokenised_corpus)
            self._bm25_ids = list(self._documents_map.keys())
        elif enable_bm25 and not BM25Okapi:
            LOGGER.warning("rank-bm25 is not installed; hybrid retrieval disabled.")

    def _load_documents(self, path: Path) -> None:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                payload = json.loads(line)
                doc_id = payload["id"]
                self._documents_map[doc_id] = {
                    "text": payload.get("text", ""),
                    "metadata": payload.get("metadata", {}),
                }

    def semantic_search(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        include_scores: bool = False,
    ) -> List[RetrievalResult]:
        raw = self._collection.query(
            query_texts=[query],
            n_results=limit,
            where=self._format_filters(filters),
        )
        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        ids = raw.get("ids", [[]])[0]
        distances = raw.get("distances", [[]])[0]
        results: List[RetrievalResult] = []
        for doc_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
            score = self._distance_to_score(distance)
            result = RetrievalResult(
                id=doc_id,
                text=text,
                score=score,
                metadata=metadata or {},
            )
            results.append(result)
        if include_scores:
            return results
        return [RetrievalResult(r.id, r.text, r.score, r.metadata) for r in results]

    @staticmethod
    def _distance_to_score(distance: float) -> float:
        return 1.0 / (1.0 + distance)

    def _format_filters(self, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not filters:
            return {}
        formatted = {}
        for key, value in filters.items():
            if isinstance(value, (list, tuple, set)):
                formatted[key] = {"$in": list(value)}
            else:
                formatted[key] = value
        return formatted

    def facet_counts(
        self, field: str, filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for doc in self._documents_map.values():
            metadata = doc.get("metadata", {})
            if not self._metadata_matches(metadata, filters):
                continue
            value = metadata.get(field)
            if value is None:
                continue
            if isinstance(value, str):
                counts[value] = counts.get(value, 0) + 1
            else:
                counts[str(value)] = counts.get(str(value), 0) + 1
        return counts

    def hybrid_search(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        alpha: float = 0.5,
    ) -> List[RetrievalResult]:
        semantic_results = self.semantic_search(
            query, limit=limit * 2, filters=filters, include_scores=True
        )
        scores: Dict[str, float] = {}
        for result in semantic_results:
            scores[result.id] = result.score
        if not self._bm25:
            ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
            return [self._result_from_id(doc_id, score) for doc_id, score in ranked]

        bm25_scores = self._bm25_rank(query, filters)
        all_ids = set(scores) | set(bm25_scores)
        if not all_ids:
            return []
        max_semantic = max(scores.values() or [1.0])
        max_bm25 = max(bm25_scores.values() or [1.0])
        combined: List[tuple[str, float]] = []
        for doc_id in all_ids:
            semantic_score = scores.get(doc_id, 0.0) / (max_semantic or 1.0)
            bm25_score = bm25_scores.get(doc_id, 0.0) / (max_bm25 or 1.0)
            final_score = alpha * semantic_score + (1 - alpha) * bm25_score
            combined.append((doc_id, final_score))
        combined.sort(key=lambda item: item[1], reverse=True)
        combined = combined[:limit]
        return [self._result_from_id(doc_id, score) for doc_id, score in combined]

    def _bm25_rank(
        self, query: str, filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        if not self._bm25:
            return {}
        tokenized_query = _tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)
        results: Dict[str, float] = {}
        for doc_id, score in zip(self._bm25_ids, scores):
            if not self._metadata_matches(
                self._documents_map.get(doc_id, {}).get("metadata", {}), filters
            ):
                continue
            results[doc_id] = float(score)
        return results

    def _metadata_matches(
        self, metadata: Dict[str, Any], filters: Optional[Dict[str, Any]]
    ) -> bool:
        if not filters:
            return True
        for key, expected in filters.items():
            value = metadata.get(key)
            if value is None:
                return False
            value_str = str(value).lower()
            if isinstance(expected, (list, tuple, set)):
                if not any(str(item).lower() in value_str for item in expected):
                    return False
            else:
                if str(expected).lower() not in value_str:
                    return False
        return True

    def _result_from_id(self, doc_id: str, score: float) -> RetrievalResult:
        if doc_id in self._documents_map:
            entry = self._documents_map[doc_id]
            text = entry.get("text", "")
            metadata = entry.get("metadata", {})
        else:
            fetched = self._collection.get(ids=[doc_id])
            text = fetched.get("documents", [[]])[0][0]
            metadata = fetched.get("metadatas", [[]])[0][0]
        return RetrievalResult(doc_id, text, score, metadata or {})


__all__ = ["KnowledgeBaseRetriever", "RetrievalResult"]
