from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def ensure_state_dir(state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_fallback_log(state_dir: Path, name: str, message: str) -> Path:
    ensure_state_dir(state_dir)
    log_path = state_dir / f"{name}.log"
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}]\n{message}\n\n")
    return log_path
