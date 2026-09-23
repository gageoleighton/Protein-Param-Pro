"""Local persistence for the protein library."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from protein import Protein


APP_DIR = Path.home() / ".protein_param_pro"
DATA_FILE = APP_DIR / "sequences.json"
UI_STATE_FILE = APP_DIR / "ui_state.json"


def load_proteins() -> list[Protein]:
    """Load saved proteins, returning an empty library when no valid data exists."""
    try:
        return [Protein(**row) for row in json.loads(DATA_FILE.read_text())]
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return []


def save_proteins(proteins: list[Protein]) -> None:
    """Persist the complete library to the app's local data file."""
    APP_DIR.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps([asdict(protein) for protein in proteins], indent=2))


def load_collapsed_folders() -> set[str]:
    """Load folder paths that the user left collapsed in the navigation tree."""
    try:
        state = json.loads(UI_STATE_FILE.read_text())
        folders = state.get("collapsed_folders", [])
        if not isinstance(folders, list) or not all(isinstance(folder, str) for folder in folders):
            return set()
        return set(folders)
    except (FileNotFoundError, OSError, json.JSONDecodeError, AttributeError, TypeError):
        return set()


def save_collapsed_folders(folders: set[str]) -> None:
    """Persist folder expansion state independently from the protein library."""
    APP_DIR.mkdir(exist_ok=True)
    UI_STATE_FILE.write_text(json.dumps({"collapsed_folders": sorted(folders)}, indent=2))


def load_folders() -> set[str]:
    """Load folders independently of their protein contents."""
    try:
        folders = json.loads((APP_DIR / "folders.json").read_text())
        if isinstance(folders, list) and all(isinstance(folder, str) and folder for folder in folders):
            return set(folders)
    except (OSError, ValueError):
        pass
    return set()


def save_folders(folders: set[str]) -> None:
    APP_DIR.mkdir(exist_ok=True)
    (APP_DIR / "folders.json").write_text(json.dumps(sorted(folders), indent=2))
