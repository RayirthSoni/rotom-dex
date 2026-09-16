# Sources, reuse review and provenance

Reviewed 2026-09-17. Every fact in the database carries an `evidence_id` that resolves to one or more
`sources` rows (URL, retrieval or access time, SHA-256 for datasets, license, review status) plus a
selector naming the raw rows or the normalization rule used.

## Candidate assessment

| Candidate | What it offers | Reuse conditions found | Decision |
| --- | --- | --- | --- |
| [PokéAPI CSV repository](https://github.com/PokeAPI/pokeapi/tree/39bc03a43df25a1898f5aa03cbc2a0abbeea30e8/data/v2/csv) (pinned commit `39bc03a4`) | Structured species/forms, per-generation history tables (types, stats, abilities, type chart), per-version-group learnsets, machines, move changelog, move/ability/item effect prose, per-version-group flavor text, item prices, exact-version encounters and held items, evolution rules, locations, Pokédex numbers. | [BSD-3-Clause](../data/sources/pokeapi/LICENSE.md): redistribution allowed with notice; Pokémon names are Nintendo trademarks. The live API's fair-use policy asks for local caching; the CSV repository avoids live calls entirely. | **Primary source.** 108 unmodified gzip-compressed CSVs cached with hashes in [`manifest.json`](../data/sources/pokeapi/manifest.json). Imports and API requests never touch the network. |
| [PokéAPI REST API](https://pokeapi.co/docs/v2) | Same underlying data. | Fair-use policy: cache locally. | Not used at runtime; the CSVs are the same data in reproducible form. |
| [Bulbapedia](https://bulbapedia.bulbagarden.net/) | Progression, gym teams, shops, TM locations, mechanics history. | [CC BY-NC-SA 2.5](https://bulbapedia.bulbagarden.net/wiki/Bulbapedia:Copyrights): attribution, **non-commercial**, share-alike. No statement on bulk extraction. | **Read for verification only.** Individual pages were read to confirm curated facts (mechanics flags, Emerald first-Gym content, validation records). Their URLs are stored as `reference` sources; no prose was copied and nothing was scraped in bulk. The non-commercial clause matters if this project ever becomes commercial: re-derive curated facts from other sources first. |
| [Pokémon Database](https://pokemondb.net/about) | Rich reference pages. | "Do not steal our content"; no API or database offered; robots.txt blocks `wget` and sets crawl delays. | **Not used.** The old scraper placeholder was deleted. |
| [Serebii](https://www.serebii.net/) | Reference pages. | "All Content is © Copyright of Serebii.net"; no reuse terms. | **Not used.** |
| [veekun/pokedex](https://github.com/veekun/pokedex) | MIT-licensed ancestor of the PokéAPI CSVs. | MIT. | Not needed; same lineage as the primary source. |
| [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) | MIT-licensed battle data including `data/mods/gen1..gen8` behaviour overrides. | MIT. | **Deferred.** Candidate for historical move *effect* models later; competitive legality is not story acquisition. |
| pret decompilations | Exact game scripts (trainers, shops, item locations). | No reuse permission for game content established. | **Not used.** |

## What the primary source does not contain

Recorded explicitly as coverage `missing` and as `data_issues` rows rather than inferred:

- shop inventories and shop-specific prices (only a generic item cost plus a few per-version-group price rows);
- TM/HM/TR and tutor **locations**, costs and one-time availability (machines are linked to moves only);
- trainer battles, milestones, story gates and any reachability information;
- encounters for Brilliant Diamond/Shining Pearl, Legends: Arceus, Scarlet/Violet (and expansions) and
  Legends: Z-A;
- learnsets for Legends: Z-A (and, as separate rows, for expansion pseudo-versions; those inherit the base
  version group, see the registry);
- historical wording of move, ability and item effects (only current wording; in-game flavor text is
  per version group from Generation III on);
- Generation I stat history beyond the `special` stat of the 151 original species.

## Source kinds in the database

| `sources.kind` | Meaning | Hash |
| --- | --- | --- |
| `dataset` | A cached PokéAPI CSV file. | SHA-256 of the decompressed bytes. |
| `game-pack` | A reviewed JSON file in this repository (registry, mechanics, per-game packs). | SHA-256 of the file. |
| `reference` | A web page read to verify curated facts; stored with the access date and license. | none |
| `code` | The normalizer version, cited when a value results from a documented rule (history rewind, damage class, derivations). | hash of the version string |

Changing any dataset, pack or the normalizer version changes the snapshot id; an existing database with a
different snapshot refuses further imports so published facts are never silently replaced.

## Extending the cache

```sh
uv run rotom fetch-sources                  # restore missing files from the pinned revision
uv run rotom fetch-sources --add berries    # add a CSV at the same pinned revision (network)
```

Adding files changes the manifest and therefore the snapshot; rebuild databases afterwards. To move to a
newer PokéAPI revision, create a new manifest deliberately and review the diff in coverage before
publishing.
