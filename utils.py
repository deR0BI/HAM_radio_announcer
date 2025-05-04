# utils.py
import json
from pathlib import Path
from typing import Iterable

from config import STATE_FILE

_state_path = Path(STATE_FILE)


def load_state() -> set[str]:
    if _state_path.is_file():
        with _state_path.open("r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_state(ids: Iterable[str]) -> None:
    with _state_path.open("w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)


def diff(new_ids: set[str], old_ids: set[str]) -> set[str]:
    """Вернёт *только новые* id анонсов."""
    return new_ids - old_ids
