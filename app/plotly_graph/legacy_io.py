from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd

@dataclass(frozen=True)
class LegacyRow:
    person1: str
    relation: str
    person2: Optional[str] = None
    gender: Optional[str] = None
    details: Optional[str] = None

def read_legacy_file(path: str) -> List[LegacyRow]:
    """
    Reads CSV or TXT-with-CSV (your Kaggle file style).
    Supports comment lines starting with '#'.
    """
    df = pd.read_csv(path, comment="#")

    # Clean whitespace for expected columns if present
    for col in ["Person 1", "Person 2", "Relation", "Gender", "Details"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    required = {"Person 1", "Relation"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)} in file {path}")

    rows: List[LegacyRow] = []
    for _, r in df.iterrows():
        rows.append(
            LegacyRow(
                person1=str(r.get("Person 1", "")).strip(),
                relation=str(r.get("Relation", "")).strip(),
                person2=(None if "Person 2" not in df.columns else str(r.get("Person 2", "")).strip()),
                gender=(None if "Gender" not in df.columns else str(r.get("Gender", "")).strip()),
                details=(None if "Details" not in df.columns else str(r.get("Details", "")).strip()),
            )
        )
    return rows
