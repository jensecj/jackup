from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    name: str
    source: str
    destination: str
    order: int
