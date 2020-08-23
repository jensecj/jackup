from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    name: str
    src: str
    dest: str
