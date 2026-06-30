"""

"""

from dataclasses import dataclass

@dataclass(kw_only=True)
class Accessory:

    name: str
    description: str
    effect: str
    category: str
    generation_introduced: int
