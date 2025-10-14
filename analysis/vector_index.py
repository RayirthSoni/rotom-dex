"""Utility functions to build and query a small vector index."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokenise(text: str) -> List[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


@dataclass
class SimpleVectorIndex:
    """A lightweight tf-idf based vector index for evaluation scripts."""

    doc_ids: Sequence[str]
    doc_vectors: List[Dict[int, float]]
    vocab_index: Dict[str, int]
    idf: Dict[int, float]
    doc_norms: List[float]

    @classmethod
    def from_documents(cls, documents: Dict[str, str]) -> "SimpleVectorIndex":
        tokens_per_doc: Dict[str, List[str]] = {
            doc_id: _tokenise(text) for doc_id, text in documents.items()
        }
        vocab: Dict[str, int] = {}
        document_frequencies: Counter[str] = Counter()
        for tokens in tokens_per_doc.values():
            document_frequencies.update(set(tokens))
            for token in tokens:
                if token not in vocab:
                    vocab[token] = len(vocab)

        doc_ids = list(documents.keys())
        num_docs = len(doc_ids)
        vocab_size = len(vocab)
        idf: Dict[int, float] = {}
        for token, idx in vocab.items():
            df = document_frequencies[token]
            idf[idx] = math.log((1 + num_docs) / (1 + df)) + 1.0

        doc_vectors: List[Dict[int, float]] = []
        doc_norms: List[float] = []
        for doc_id in doc_ids:
            tokens = tokens_per_doc[doc_id]
            if not tokens:
                doc_vectors.append({})
                doc_norms.append(0.0)
                continue
            counts = Counter(tokens)
            length = len(tokens)
            vector: Dict[int, float] = {}
            norm = 0.0
            for token, freq in counts.items():
                idx = vocab[token]
                value = (freq / length) * idf[idx]
                vector[idx] = value
                norm += value * value
            doc_vectors.append(vector)
            doc_norms.append(math.sqrt(norm))

        return cls(
            doc_ids=doc_ids,
            doc_vectors=doc_vectors,
            vocab_index=vocab,
            idf=idf,
            doc_norms=doc_norms,
        )

    @classmethod
    def from_metadata(cls, metadata_path: str | Path) -> "SimpleVectorIndex":
        with open(metadata_path, "r", encoding="utf-8") as fh:
            metadata = json.load(fh)
        documents = {}
        for entry in metadata:
            name = entry["name"]
            text = " ".join(
                [
                    name,
                    " ".join(entry.get("types", [])),
                    entry.get("generation", ""),
                ]
            )
            documents[name] = text
        return cls.from_documents(documents)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        tokens = _tokenise(query)
        if not tokens:
            return []
        counts = Counter(tokens)
        length = len(tokens)
        query_vector: Dict[int, float] = {}
        query_norm = 0.0
        for token, freq in counts.items():
            if token not in self.vocab_index:
                continue
            idx = self.vocab_index[token]
            weight = (freq / length) * self.idf[idx]
            query_vector[idx] = weight
            query_norm += weight * weight

        query_norm = math.sqrt(query_norm)
        if query_norm == 0:
            return []

        scores: List[Tuple[str, float]] = []
        for doc_id, vector, norm in zip(self.doc_ids, self.doc_vectors, self.doc_norms):
            if norm == 0:
                scores.append((doc_id, 0.0))
                continue
            dot = 0.0
            for idx, weight in query_vector.items():
                dot += weight * vector.get(idx, 0.0)
            cosine = dot / (norm * query_norm)
            scores.append((doc_id, cosine))

        scores.sort(key=lambda item: item[1], reverse=True)
        return scores[:top_k]

    def __len__(self) -> int:
        return len(self.doc_ids)
