"""Local persistence for the protein library."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from protein import Protein


APP_DIR = Path.home() / ".protein_param_pro"
DATA_FILE = APP_DIR / "sequences.json"


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
