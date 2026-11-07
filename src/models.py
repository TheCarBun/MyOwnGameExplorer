from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GameEntry:
    name: str
    executable: Path
    folder: Path
    size_bytes: int
