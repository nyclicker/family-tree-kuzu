# app/importers/family_tree_json.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def parse_family_tree_json(path: str | Path) -> Dict[str, Any]:
    """
    Parse a JSON export file (from /export endpoint).
    
    Expected schema:
    {
      "tree": { "id": int, "name": str, "description": str },
      "tree_version": { "id": int, "tree_id": int, "version": int, ... },
      "people": [ { "id": str, "display_name": str, "sex": str, "notes": str, ... }, ... ],
      "relationships": [ { "id": str, "from_person_id": str, "to_person_id": str, "type": str, ... }, ... ]
    }
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate structure
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")

    if "people" not in data or "relationships" not in data:
        raise ValueError("JSON must contain 'people' and 'relationships' arrays")

    if not isinstance(data["people"], list):
        raise ValueError("'people' must be an array")

    if not isinstance(data["relationships"], list):
        raise ValueError("'relationships' must be an array")

    return data


def extract_people_for_import(data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Convert JSON people array into the format expected by /people endpoint.
    Returns dict keyed by display_name for deduplication.
    """
    people: Dict[str, Dict[str, str]] = {}
    for p in data.get("people", []):
        if not isinstance(p, dict):
            continue

        display_name = p.get("display_name", "").strip()
        if not display_name:
            continue

        sex = p.get("sex", "U")
        notes = p.get("notes", "")

        # Normalize sex to M/F/U
        if sex not in ("M", "F", "U"):
            sex = "U"

        people[display_name] = {
            "display_name": display_name,
            "sex": sex,
            "notes": notes or "",
        }

    return people


def extract_relationships_for_import(
    data: Dict[str, Any], name_to_id_map: Dict[str, str]
) -> Tuple[List[Tuple[int, Dict[str, str]]], List[str]]:
    """
    Convert JSON relationships array into the format expected by /relationships endpoint.
    Maps old person IDs to new IDs using name_to_id_map (person.display_name -> new person.id).
    Only processes CHILD_OF relationships. Other types are ignored for now.
    
    Returns tuple of (relationships, warnings).
    """
    relationships: List[Tuple[int, Dict[str, str]]] = []
    warnings: List[str] = []

    for i, rel in enumerate(data.get("relationships", []), start=1):
        if not isinstance(rel, dict):
            continue

        from_person_id = rel.get("from_person_id")
        to_person_id = rel.get("to_person_id")
        rel_type = rel.get("type", "")

        if not from_person_id or not rel_type:
            continue
        
        # Only process CHILD_OF relationships for now
        if rel_type != "CHILD_OF":
            warnings.append(f"Relationship {i}: Skipped type '{rel_type}' (not yet supported)")
            continue

        # Try to resolve IDs: check if they're in the name map (import by display_name)
        # Otherwise use the ID as-is (assuming it will be corrected or already valid)
        resolved_from = from_person_id
        resolved_to = to_person_id

        # For now, just pass through the IDs as provided in the JSON
        # (The import_family_tree.py script will remap as needed)
        relationships.append(
            (
                i,
                {
                    "from_person_id": resolved_from,
                    "to_person_id": resolved_to,
                    "type": rel_type,
                },
            )
        )

    return relationships, warnings
