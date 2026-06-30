"""

"""


from dataclasses import dataclass


@dataclass(kw_only=True)
class Ability:

    name: str
    description: str
    is_hidden: bool
    generation_introduced: int
