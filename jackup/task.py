from dataclasses import dataclass

@dataclass
class Task:
    name: str
    source: str
    destination: str
    order: int
