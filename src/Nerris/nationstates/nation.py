from dataclasses import dataclass

@dataclass(frozen=True)
class Nation:
    name: str
    url_name: str
    region: str
    region_url_name: str
