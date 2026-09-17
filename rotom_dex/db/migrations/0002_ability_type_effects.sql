-- Reviewed, type-based defensive damage modifiers granted by abilities.
--
-- Separate from `ability_effects`, which holds the source's prose. This table carries only what can
-- be applied arithmetically: a factor against one attacking type, or against super-effective /
-- non-super-effective moves as a class. Scoped per generation like `type_effectiveness`, because the
-- modifier's starting generation is not always the ability's introduction (Lightning Rod and Storm
-- Drain granted no immunity before Generation V).
CREATE TABLE ability_type_effects (
    id TEXT PRIMARY KEY,
    ability_id INTEGER NOT NULL REFERENCES abilities (id),
    generation_id INTEGER NOT NULL REFERENCES generations (id),
    applies_to TEXT NOT NULL CHECK (applies_to IN ('type', 'super-effective', 'non-super-effective')),
    type_id INTEGER REFERENCES types (id),
    damage_factor INTEGER NOT NULL CHECK (damage_factor IN (0, 25, 50, 75, 125, 200)),
    note TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL,
    evidence_id TEXT NOT NULL REFERENCES evidence (id),
    CHECK ((applies_to = 'type') = (type_id IS NOT NULL)),
    UNIQUE (ability_id, generation_id, applies_to, type_id)
);

CREATE INDEX ability_type_effects_by_generation ON ability_type_effects (generation_id, ability_id);
