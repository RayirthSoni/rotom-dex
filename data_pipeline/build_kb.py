"""Utilities to normalise scraped data and build the knowledge base."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import pandas as pd

from configs.constants import Constants

LOGGER = logging.getLogger(__name__)


GENERATION_ALIASES = {
    "1": "generation-i",
    "i": "generation-i",
    "kanto": "generation-i",
    "2": "generation-ii",
    "ii": "generation-ii",
    "johto": "generation-ii",
    "3": "generation-iii",
    "iii": "generation-iii",
    "hoenn": "generation-iii",
    "4": "generation-iv",
    "iv": "generation-iv",
    "sinnoh": "generation-iv",
    "5": "generation-v",
    "v": "generation-v",
    "unova": "generation-v",
    "6": "generation-vi",
    "vi": "generation-vi",
    "kalos": "generation-vi",
    "7": "generation-vii",
    "vii": "generation-vii",
    "alola": "generation-vii",
    "8": "generation-viii",
    "viii": "generation-viii",
    "galar": "generation-viii",
    "hisui": "generation-viii",
    "9": "generation-ix",
    "ix": "generation-ix",
    "paldea": "generation-ix",
}


@dataclass
class DocumentRecord:
    """Simple representation of a document before chunking."""

    id: str
    text: str
    metadata: Dict[str, Any]


@dataclass
class DocumentChunk:
    """Representation of a chunk ready for embedding."""

    id: str
    text: str
    metadata: Dict[str, Any]


def load_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        LOGGER.warning("Missing JSON file: %s", path)
        return []
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def ensure_generation(entry: Dict[str, Any]) -> Dict[str, Any]:
    slug = entry.get("generation")
    label = entry.get("generation_label")
    if slug in Constants.GENERATION_CONFIG:
        config = Constants.GENERATION_CONFIG[slug]
        entry.setdefault("generation_label", config["label"])
        return entry
    if label:
        slug_from_label = resolve_generation(label)
        if slug_from_label:
            entry["generation"] = slug_from_label
            entry.setdefault("generation_label", Constants.GENERATION_CONFIG[slug_from_label]["label"])
            return entry
    if slug:
        slug_from_value = resolve_generation(slug)
        if slug_from_value:
            entry["generation"] = slug_from_value
            entry.setdefault("generation_label", Constants.GENERATION_CONFIG[slug_from_value]["label"])
    return entry


def resolve_generation(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower()
    lowered = lowered.replace("pokémon", "").strip()
    match = re.search(r"generation\s*([ivx0-9-]+)", lowered)
    token = match.group(1) if match else lowered
    token = token.replace("-", " ")
    token = token.strip()
    for part in token.split():
        if part in GENERATION_ALIASES:
            slug = GENERATION_ALIASES[part]
            return slug
    if token in GENERATION_ALIASES:
        return GENERATION_ALIASES[token]
    return None


def normalize_move_tutors(data: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    for entry in data:
        entry = ensure_generation(dict(entry))
        record = {
            "generation": entry.get("generation"),
            "generation_label": entry.get("generation_label"),
            "regions": entry.get("regions") or [],
            "pokemon": entry.get("pokemon"),
            "move": entry.get("move"),
            "version_group": entry.get("version_group"),
            "source": entry.get("source"),
            "location": entry.get("location"),
            "notes": entry.get("notes"),
        }
        records.append(record)
    return pd.DataFrame(records)


def normalize_machines(data: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    for entry in data:
        entry = ensure_generation(dict(entry))
        records.append(
            {
                "generation": entry.get("generation"),
                "generation_label": entry.get("generation_label"),
                "machine_id": entry.get("machine_id"),
                "machine_number": entry.get("machine_number"),
                "move": entry.get("move"),
                "move_type": entry.get("move_type"),
                "move_damage_class": entry.get("move_damage_class"),
                "version_group": entry.get("version_group"),
                "region": entry.get("region"),
            }
        )
    return pd.DataFrame(records)


def normalize_encounters(data: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    for entry in data:
        entry = ensure_generation(dict(entry))
        records.append(
            {
                "generation": entry.get("generation"),
                "generation_label": entry.get("generation_label"),
                "region": entry.get("region"),
                "location": entry.get("location"),
                "location_area": entry.get("location_area"),
                "pokemon": entry.get("pokemon"),
                "version_group": entry.get("version_group"),
                "method": entry.get("method"),
                "chance": entry.get("chance"),
                "min_level": entry.get("min_level"),
                "max_level": entry.get("max_level"),
            }
        )
    return pd.DataFrame(records)


def normalize_trainers(data: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    for entry in data:
        entry = ensure_generation(dict(entry))
        records.append(
            {
                "generation": entry.get("generation"),
                "generation_label": entry.get("generation_label"),
                "trainer_id": entry.get("trainer_id"),
                "trainer_name": entry.get("trainer_name"),
                "trainer_class": entry.get("trainer_class"),
                "location": entry.get("location"),
                "version_group": entry.get("version_group"),
                "reward": entry.get("reward"),
                "team": entry.get("team") or [],
                "region": entry.get("region"),
            }
        )
    return pd.DataFrame(records)


def normalize_items(data: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    for entry in data:
        entry = ensure_generation(dict(entry))
        records.append(
            {
                "generation": entry.get("generation"),
                "generation_label": entry.get("generation_label"),
                "item_id": entry.get("item_id"),
                "item": entry.get("item"),
                "category": entry.get("category"),
                "cost": entry.get("cost"),
                "fling_power": entry.get("fling_power"),
                "effect": entry.get("effect"),
                "version_group": entry.get("version_group"),
                "region": entry.get("region"),
            }
        )
    return pd.DataFrame(records)


def normalize_pokemon_metadata(data: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    for entry in data:
        name = entry.get("name")
        slug = name.lower() if name else None
        generation_slug = resolve_generation(entry.get("generation"))
        generation_label = (
            Constants.GENERATION_CONFIG[generation_slug]["label"]
            if generation_slug
            else entry.get("generation")
        )
        records.append(
            {
                "name": slug,
                "display_name": name,
                "types": entry.get("types") or [],
                "image": entry.get("image"),
                "generation": generation_slug,
                "generation_label": generation_label,
            }
        )
    return pd.DataFrame(records)


def normalize_pokemon_stats(data: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    for entry in data:
        name = entry.get("name")
        slug = name.lower() if name else None
        types = entry.get("types")
        type_list = types.replace("/", " ").split() if isinstance(types, str) else []
        records.append(
            {
                "name": slug,
                "display_name": name,
                "types": type_list,
                "total": entry.get("total"),
                "hp": entry.get("hp"),
                "attack": entry.get("attack"),
                "defense": entry.get("defense"),
                "sp_atk": entry.get("sp_atk"),
                "sp_def": entry.get("sp_def"),
                "speed": entry.get("speed"),
            }
        )
    return pd.DataFrame(records)


def normalize_pokemon_evolutions(data: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    for entry in data:
        name = entry.get("name")
        slug = name.lower() if name else None
        records.append(
            {
                "name": slug,
                "display_name": name,
                "level": entry.get("level"),
                "evolution_paths": entry.get("evolution_paths") or [],
            }
        )
    df = pd.DataFrame(records)
    if df.empty:
        return df
    return df.drop_duplicates(subset=["name"])


def _serialise_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    def convert(value: Any) -> Any:
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return value

    return df.applymap(convert)


def _clean_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, list):
            cleaned[key] = ", ".join(map(str, value))
        else:
            cleaned[key] = value
    return cleaned


def _ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return [value]
        return [value]
    return [value]


def build_move_tutor_documents(df: pd.DataFrame) -> List[DocumentRecord]:
    documents: List[DocumentRecord] = []
    if df.empty:
        return documents
    for row in df.to_dict(orient="records"):
        regions = _ensure_list(row.get("regions"))
        text = (
            f"Move tutor entry: {row.get('pokemon')} can learn {row.get('move')} "
            f"in {row.get('generation_label')} ({row.get('version_group')}). "
        )
        if row.get("location"):
            text += f"Location: {row.get('location')}. "
        if row.get("notes"):
            text += f"Notes: {row.get('notes')}"
        metadata = _clean_metadata(
            {
                "entity_type": "move_tutor",
                "generation": row.get("generation"),
                "generation_label": row.get("generation_label"),
                "game": row.get("version_group"),
                "region": regions[0] if regions else None,
                "pokemon": row.get("pokemon"),
                "move": row.get("move"),
            }
        )
        documents.append(DocumentRecord(str(uuid.uuid4()), text.strip(), metadata))
    return documents


def build_machine_documents(df: pd.DataFrame) -> List[DocumentRecord]:
    documents: List[DocumentRecord] = []
    if df.empty:
        return documents
    for row in df.to_dict(orient="records"):
        text = (
            f"TM/HM entry: {row.get('machine_number')} teaches {row.get('move')} "
            f"({row.get('move_type')} {row.get('move_damage_class')}) in {row.get('generation_label')} "
            f"({row.get('version_group')})."
        )
        if row.get("region"):
            text += f" Region: {row.get('region')}."
        metadata = _clean_metadata(
            {
                "entity_type": "machine",
                "generation": row.get("generation"),
                "generation_label": row.get("generation_label"),
                "game": row.get("version_group"),
                "region": row.get("region"),
                "move": row.get("move"),
                "machine_number": row.get("machine_number"),
                "move_type": row.get("move_type"),
            }
        )
        documents.append(DocumentRecord(str(uuid.uuid4()), text.strip(), metadata))
    return documents


def build_encounter_documents(df: pd.DataFrame) -> List[DocumentRecord]:
    documents: List[DocumentRecord] = []
    if df.empty:
        return documents
    for row in df.to_dict(orient="records"):
        text = (
            f"Encounter: {row.get('pokemon')} appears via {row.get('method')} at {row.get('location')} "
            f"in {row.get('region')} ({row.get('generation_label')} {row.get('version_group')})."
        )
        if row.get("chance") is not None:
            text += f" Chance: {row.get('chance')}%."
        min_level = row.get("min_level")
        max_level = row.get("max_level")
        if min_level is not None or max_level is not None:
            min_text = min_level if min_level is not None else "?"
            max_text = max_level if max_level is not None else "?"
            text += f" Levels {min_text}-{max_text}"
        metadata = _clean_metadata(
            {
                "entity_type": "encounter",
                "generation": row.get("generation"),
                "generation_label": row.get("generation_label"),
                "game": row.get("version_group"),
                "region": row.get("region"),
                "pokemon": row.get("pokemon"),
                "method": row.get("method"),
            }
        )
        documents.append(DocumentRecord(str(uuid.uuid4()), text.strip(), metadata))
    return documents


def build_trainer_documents(df: pd.DataFrame) -> List[DocumentRecord]:
    documents: List[DocumentRecord] = []
    if df.empty:
        return documents
    for row in df.to_dict(orient="records"):
        team_entries = _ensure_list(row.get("team"))
        team_text = ", ".join(
            f"{member.get('pokemon')} (Lv. {member.get('level')})"
            for member in team_entries
        )
        text = (
            f"Trainer {row.get('trainer_name')} ({row.get('trainer_class')}) battled in {row.get('location')} "
            f"during {row.get('generation_label')} ({row.get('version_group')})."
        )
        if team_text:
            text += f" Team: {team_text}."
        if row.get("reward"):
            text += f" Reward: {row.get('reward')} PokéDollars."
        metadata = _clean_metadata(
            {
                "entity_type": "trainer",
                "generation": row.get("generation"),
                "generation_label": row.get("generation_label"),
                "game": row.get("version_group"),
                "region": row.get("region"),
                "trainer_class": row.get("trainer_class"),
                "trainer_name": row.get("trainer_name"),
            }
        )
        documents.append(DocumentRecord(str(uuid.uuid4()), text.strip(), metadata))
    return documents


def build_item_documents(df: pd.DataFrame) -> List[DocumentRecord]:
    documents: List[DocumentRecord] = []
    if df.empty:
        return documents
    for row in df.to_dict(orient="records"):
        text = (
            f"Item {row.get('item')} ({row.get('category')}) appears in {row.get('generation_label')} "
            f"({row.get('version_group')})."
        )
        if row.get("effect"):
            text += f" Effect: {row.get('effect')}"
        if row.get("cost"):
            text += f" Cost: {row.get('cost')} PokéDollars."
        metadata = _clean_metadata(
            {
                "entity_type": "item",
                "generation": row.get("generation"),
                "generation_label": row.get("generation_label"),
                "game": row.get("version_group"),
                "region": row.get("region"),
                "category": row.get("category"),
                "item": row.get("item"),
            }
        )
        documents.append(DocumentRecord(str(uuid.uuid4()), text.strip(), metadata))
    return documents


def build_pokemon_documents(df: pd.DataFrame) -> List[DocumentRecord]:
    documents: List[DocumentRecord] = []
    if df.empty:
        return documents
    for row in df.to_dict(orient="records"):
        types = _ensure_list(row.get("types"))
        type_text = "/".join(types) if types else "unknown type"
        text = (
            f"{row.get('display_name')} is a {type_text} Pokémon from {row.get('generation_label')}. "
        )
        stats = [
            ("HP", row.get("hp")),
            ("Attack", row.get("attack")),
            ("Defense", row.get("defense")),
            ("Sp. Atk", row.get("sp_atk")),
            ("Sp. Def", row.get("sp_def")),
            ("Speed", row.get("speed")),
        ]
        stat_text = ", ".join(f"{label} {value}" for label, value in stats if value is not None)
        if stat_text:
            text += f"Base stats: {stat_text}. "
        evolution_paths = _ensure_list(row.get("evolution_paths"))
        if evolution_paths:
            evo_texts = []
            for path in evolution_paths:
                if isinstance(path, dict):
                    evo_texts.append(f"evolves to {path.get('evolves_to')} ({path.get('condition')})")
            if evo_texts:
                text += f"Evolution: {', '.join(evo_texts)}."
        metadata = _clean_metadata(
            {
                "entity_type": "pokemon",
                "pokemon": row.get("display_name"),
                "generation": row.get("generation"),
                "generation_label": row.get("generation_label"),
                "types": types,
            }
        )
        documents.append(DocumentRecord(str(uuid.uuid4()), text.strip(), metadata))
    return documents


def chunk_documents(
    documents: Sequence[DocumentRecord],
    chunk_size: int = 160,
    chunk_overlap: int = 40,
) -> List[DocumentChunk]:
    chunks: List[DocumentChunk] = []
    for document in documents:
        words = document.text.split()
        if not words:
            continue
        start = 0
        index = 0
        step = chunk_size - chunk_overlap if chunk_size > chunk_overlap else chunk_size
        while start < len(words):
            chunk_words = words[start : start + chunk_size]
            chunk_text = " ".join(chunk_words)
            metadata = dict(document.metadata)
            metadata["chunk_index"] = index
            chunks.append(
                DocumentChunk(
                    id=f"{document.id}-{index}",
                    text=chunk_text,
                    metadata=_clean_metadata(metadata),
                )
            )
            index += 1
            start += step
    return chunks


def write_structured_outputs(
    tables: Dict[str, pd.DataFrame],
    sqlite_path: Path,
    structured_dir: Path,
    postgres_url: str | None = None,
) -> None:
    structured_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        for name, df in tables.items():
            LOGGER.info("Writing table %s (%d rows)", name, len(df))
            df.to_sql(name, conn, if_exists="replace", index=False)
            df.to_csv(structured_dir / f"{name}.csv", index=False)
    if postgres_url:
        try:
            import sqlalchemy
        except ImportError as exc:  # pragma: no cover - optional dependency
            LOGGER.warning("SQLAlchemy not available, skipping Postgres load: %s", exc)
        else:  # pragma: no cover - optional external service
            engine = sqlalchemy.create_engine(postgres_url)
            with engine.begin() as conn:
                for name, df in tables.items():
                    LOGGER.info("Uploading %s to Postgres", name)
                    df.to_sql(name, conn, if_exists="replace", index=False)


def write_documents_jsonl(chunks: Sequence[DocumentChunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            payload = {
                "id": chunk.id,
                "text": chunk.text,
                "metadata": chunk.metadata,
            }
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def embed_and_index(
    chunks: Sequence[DocumentChunk],
    vector_store_path: Path,
    collection_name: str,
    model_name: str,
) -> None:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "sentence-transformers is required for embedding. Install it via pip."
        ) from exc
    try:
        import chromadb
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("chromadb is required for vector storage. Install it via pip.") from exc

    vector_store_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(vector_store_path))
    collection = client.get_or_create_collection(name=collection_name)
    if collection.count() > 0:
        collection.delete(where={})

    model = SentenceTransformer(model_name)
    documents = [chunk.text for chunk in chunks]
    embeddings = model.encode(documents, batch_size=64, show_progress_bar=False)
    metadata = [_clean_metadata(chunk.metadata) for chunk in chunks]
    collection.upsert(
        ids=[chunk.id for chunk in chunks],
        documents=documents,
        metadatas=metadata,
        embeddings=[embedding.tolist() for embedding in embeddings],
    )
    LOGGER.info("Indexed %d document chunks into %s", len(chunks), collection_name)


def build_pokemon_dataframe(
    metadata_df: pd.DataFrame,
    stats_df: pd.DataFrame,
    evolution_df: pd.DataFrame,
) -> pd.DataFrame:
    if metadata_df.empty:
        return metadata_df
    df = metadata_df.copy()
    if not stats_df.empty:
        df = df.merge(stats_df, on=["name", "display_name"], how="left", suffixes=("", "_stat"))
        if "types_stat" in df.columns:
            df["types"] = df["types"].where(
                df["types"].apply(lambda value: bool(value)), df["types_stat"]
            )
            df = df.drop(columns=["types_stat"])
    if not evolution_df.empty:
        df = df.merge(evolution_df, on=["name", "display_name"], how="left")
    return df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--metadata-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--sqlite-path", type=Path)
    parser.add_argument("--vector-store-path", type=Path)
    parser.add_argument("--documents-path", type=Path)
    parser.add_argument("--collection-name", default="pokemon-kb")
    parser.add_argument("--model-name", default="all-MiniLM-L6-v2")
    parser.add_argument("--chunk-size", type=int, default=160)
    parser.add_argument("--chunk-overlap", type=int, default=40)
    parser.add_argument("--postgres-url")
    parser.add_argument("--skip-embeddings", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = args.sqlite_path or output_dir / "pokemon_kb.sqlite"
    vector_store_path = args.vector_store_path or output_dir / "vector_store"
    documents_path = args.documents_path or output_dir / "documents.jsonl"
    structured_dir = output_dir / "structured"

    move_tutor_df = normalize_move_tutors(load_json(args.raw_dir / "move_tutors.json"))
    machines_df = normalize_machines(load_json(args.raw_dir / "machines.json"))
    encounters_df = normalize_encounters(load_json(args.raw_dir / "encounters.json"))
    trainers_df = normalize_trainers(load_json(args.raw_dir / "trainer_rosters.json"))
    items_df = normalize_items(load_json(args.raw_dir / "items.json"))

    metadata_df = normalize_pokemon_metadata(
        load_json(args.metadata_dir / "pokemon_metadata.json")
    )
    stats_df = normalize_pokemon_stats(load_json(args.metadata_dir / "pokemon_stats.json"))
    evolution_df = normalize_pokemon_evolutions(
        load_json(args.metadata_dir / "pokemon_evolution_data.json")
    )
    pokemon_df = build_pokemon_dataframe(metadata_df, stats_df, evolution_df)

    tables = {
        "move_tutors": _serialise_dataframe(move_tutor_df),
        "machines": _serialise_dataframe(machines_df),
        "encounters": _serialise_dataframe(encounters_df),
        "trainer_rosters": _serialise_dataframe(trainers_df),
        "items": _serialise_dataframe(items_df),
        "pokemon": _serialise_dataframe(pokemon_df),
    }
    write_structured_outputs(tables, sqlite_path, structured_dir, args.postgres_url)

    documents: List[DocumentRecord] = []
    documents.extend(build_move_tutor_documents(move_tutor_df))
    documents.extend(build_machine_documents(machines_df))
    documents.extend(build_encounter_documents(encounters_df))
    documents.extend(build_trainer_documents(trainers_df))
    documents.extend(build_item_documents(items_df))
    documents.extend(build_pokemon_documents(pokemon_df))

    chunks = chunk_documents(documents, args.chunk_size, args.chunk_overlap)
    write_documents_jsonl(chunks, documents_path)

    if not args.skip_embeddings:
        embed_and_index(chunks, vector_store_path, args.collection_name, args.model_name)
    LOGGER.info("Knowledge base build completed.")


if __name__ == "__main__":
    main()
