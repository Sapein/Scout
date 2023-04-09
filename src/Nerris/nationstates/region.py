from dataclasses import dataclass

@dataclass(frozen=True)
class Region:
    name: str
    nations: list[str]
