"""

"""

from dataclasses import dataclass


@dataclass(kw_only=True)
class Pokemon:

    name: str
    national_dex_number: int
    type: list[str]
    species: str
    height: float
    weight: float
    abilities: list[str]

    # base stats
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int

    # training
    ev_yield: dict[str, int]
    catch_rate: int
    base_friendship: int
    base_experience: int
    growth_rate: str

    # breeding
    egg_groups: list[str]
    gender_ratio: dict[str, float]
    egg_cycles: int


    @property
    def total_stats(self) -> int:
        return self.hp + self.attack + self.defense + self.special_attack + self.special_defense + self.speed

    @property
    def average_stats(self) -> float:
        return self.total_stats / 6