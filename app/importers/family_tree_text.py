# app/importers/family_tree_text.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REL_MAP = {
    "Child": "CHILD_OF",
    # Add more mappings here if you support them
    # "Spouse": "SPOUSE_OF",
}

SKIP_RELATIONS = {"Earliest Ancestor"}  # no relationship row


@dataclass(frozen=True)
class ParsedRow:
    line_no: int
    person1: str
    relation: str
    person2: str
    gender1: str
    details: str


def _clean(s: str) -> str:
    return (s or "").strip()


def parse_family_tree_txt(path: str | Path) -> List[ParsedRow]:
    """
    Expected CSV-ish schema:
    Person 1,Relation,Person 2,Gender,Details
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    rows: List[ParsedRow] = []
    for i, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # skip header
        if line.lower().startswith("person 1,relation,person 2"):
            continue

        parts = [x.strip() for x in line.split(",")]

        # allow missing trailing columns
        while len(parts) < 5:
            parts.append("")

        person1, relation, person2, gender1, details = parts[:5]

        person1 = _clean(person1)
        relation = _clean(relation)
        person2 = _clean(person2)
        gender1 = _clean(gender1)
        details = _clean(details)

        if not person1:
            raise ValueError(f"Line {i}: Person 1 is required")

        # gender only relates to person1 (as you stated) - validate lightly
        if gender1 and gender1.upper() not in {"M", "F"}:
            raise ValueError(f"Line {i}: Gender must be M/F (got {gender1!r})")

        rows.append(
            ParsedRow(
                line_no=i,
                person1=person1,
                relation=relation,
                person2=person2,
                gender1=gender1.upper() if gender1 else "",
                details=details,
            )
        )

    return rows


def build_people_set(rows: List[ParsedRow]) -> Dict[str, Dict[str, str]]:
    """
    Returns dict keyed by display_name with payload fields for /people creation.
    Only Person 1's are created per your requirement.
    """
    people: Dict[str, Dict[str, str]] = {}
    for r in rows:
        if r.person1 not in people:
            # notes: you said details can be ignored; I map it to notes if present
            people[r.person1] = {
                "display_name": r.person1,
                "sex": "M" if r.gender1 == "M" else "F" if r.gender1 == "F" else "M",
                "notes": r.details or "",
            }
        else:
            # if later lines add details, keep first non-empty
            if r.details and not people[r.person1].get("notes"):
                people[r.person1]["notes"] = r.details
    return people


def build_relationship_requests(
    rows: List[ParsedRow],
    name_to_id: Dict[str, str],
) -> List[Tuple[int, Dict[str, str]]]:
    """
    Returns list of (line_no, rel_payload).
    Enforces: Person2 must exist in name_to_id if referenced.
    Skips Earliest Ancestor relationships.
    """
    rels: List[Tuple[int, Dict[str, str]]] = []

    for r in rows:
        if r.relation in SKIP_RELATIONS:
            continue

        if r.relation not in REL_MAP:
            raise ValueError(f"Line {r.line_no}: Unknown relation {r.relation!r}")

        # must reference an existing person2 (as per your rule)
        if r.person2:
            if r.person2 not in name_to_id:
                raise ValueError(
                    f"Line {r.line_no}: Person 2 {r.person2!r} not found among Person 1 set. "
                    f"Fix the file (Person 2 must exist as a Person 1 somewhere)."
                )
            to_id = name_to_id[r.person2]
        else:
            # if no person2 provided, that’s not a valid relationship in your schema
            raise ValueError(f"Line {r.line_no}: Person 2 is required for relation {r.relation!r}")

        from_id = name_to_id[r.person1]

        rels.append(
            (
                r.line_no,
                {
                    "from_person_id": from_id,
                    "to_person_id": to_id,
                    "type": REL_MAP[r.relation],
                },
            )
        )

    return rels
