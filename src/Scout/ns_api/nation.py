from dataclasses import dataclass


@dataclass(frozen=True)
class Nation:
    name: str
    region: str
