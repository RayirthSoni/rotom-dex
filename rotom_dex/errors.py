"""Read-side error vocabulary, shared by repositories, calculators, services and the API.

The distinction matters at the HTTP boundary: a `SemanticError` is the caller asking something the
game cannot answer (Fairy in Generation I), while a bare `ValueError` escaping the read path is a bug
and must surface as a 500 rather than masquerading as a client error.
"""

from __future__ import annotations


class NotFound(ValueError):
    """An identifier that does not exist in the catalog: game, Pokémon, move, item, evidence id."""


class SemanticError(ValueError):
    """A request that is well-formed but meaningless inside the requested game."""


class StaleDatabase(ValueError):
    """The database predates the code's migrations; it must be rebuilt, not patched."""
