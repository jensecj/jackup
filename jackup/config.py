from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    jackup_path: str
    log_path: str
