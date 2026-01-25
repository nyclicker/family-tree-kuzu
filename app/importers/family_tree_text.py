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
    person1: str  # Original display name
    person1_first: str  # First name only
    person1_last: str  # Last name (could be empty)
    person1_key: str  # Unique key (first + last)
    relation: str
    person2: str  # Original display name
    person2_key: str  # Unique key for person2
    gender1: str
    details: str


def _clean(s: str) -> str:
    return (s or "").strip()


def _parse_name_parts(display_name: str) -> Tuple[str, str, str]:
    """
    Parse a display name into (first_name, last_name, full_key).
    
    Examples:
    - "John Smith" -> ("John", "Smith", "John Smith")
    - "Weldeamlak\n(Geza)" -> ("Weldeamlak", "Geza", "Weldeamlak Geza")
    - "SingleName" -> ("SingleName", "", "SingleName")
    - "First Middle Last" -> ("First", "Last", "First Last")
    
    Returns: (first_name, last_name, unique_key)
    """
    name = display_name.strip()
    
    # Handle names with parentheses like "Weldeamlak\n(Geza)"
    if "(" in name and ")" in name:
        # Extract the part before parentheses and inside parentheses
        before_paren = name.split("(")[0].strip()
        inside_paren = name.split("(")[1].split(")")[0].strip()
        
        # Remove \n if present
        before_paren = before_paren.replace("\\n", "").strip()
        
        first_name = before_paren
        last_name = inside_paren
        unique_key = f"{first_name} {last_name}" if last_name else first_name
        return (first_name, last_name, unique_key)
    
    # Handle names with spaces (First Last or First Middle Last)
    parts = name.split()
    if len(parts) == 1:
        # Single name
        return (parts[0], "", parts[0])
    elif len(parts) == 2:
        # First Last
        return (parts[0], parts[1], name)
    else:
        # First Middle... Last - use first and last only
        return (parts[0], parts[-1], f"{parts[0]} {parts[-1]}")


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

        # Parse name components for deduplication
        # Person1 is treated as the first name (display name)
        # Extract first word for display, but use full person1 for matching
        p1_parts = person1.split()
        p1_first = p1_parts[0] if p1_parts else person1
        
        # For "Child" relationships, always combine person1 with parent name (person2)
        # to create a unique key: "FirstName (ParentName)"
        # This distinguishes people with same first name but different parents
        if relation.lower() == "child" and person2:
            p1_key = f"{person1} ({person2})"
            p2_key = person2  # Parent's key is just their name
        else:
            # For non-child relationships (Spouse, etc), use person1 as-is
            p1_key = person1
            p2_key = person2 if person2 else ""

        rows.append(
            ParsedRow(
                line_no=i,
                person1=person1,
                person1_first=p1_first,
                person1_last="",  # Not used anymore
                person1_key=p1_key,
                relation=relation,
                person2=person2,
                person2_key=p2_key,
                gender1=gender1.upper() if gender1 else "",
                details=details,
            )
        )

    return rows


def detect_duplicates(rows: List[ParsedRow], filename: str = "") -> List[str]:
    """
    Detect potential duplicate entries that need to be cleaned up.
    Returns list of warning messages about duplicates found.
    
    This function detects when the same person (same unique key) appears
    multiple times in the file, either with the same display name or different
    display name variants. These duplicates will be automatically resolved by
    the deduplication logic (same unique key = same person in database).
    
    Args:
        rows: List of parsed rows
        filename: Optional filename to include in warning messages
    """
    warnings: List[str] = []
    key_to_display_names: Dict[str, Dict[str, List[int]]] = {}  # key -> {display_name -> line_nos}
    
    # Track all person unique keys and their display name variants
    for r in rows:
        if r.person1_key:
            if r.person1_key not in key_to_display_names:
                key_to_display_names[r.person1_key] = {}
            if r.person1 not in key_to_display_names[r.person1_key]:
                key_to_display_names[r.person1_key][r.person1] = []
            key_to_display_names[r.person1_key][r.person1].append(r.line_no)
    
    # Report if same unique key appears multiple times (duplicate person entries)
    file_prefix = f"[{filename}] " if filename else ""
    for unique_key, display_names in sorted(key_to_display_names.items()):
        # Calculate total appearances
        total_lines = []
        for line_nos in display_names.values():
            total_lines.extend(line_nos)
        
        # Warn if person appears on multiple lines
        if len(total_lines) > 1:
            if len(display_names) > 1:
                # Same person with different display names
                variants = []
                for display_name, line_nos in display_names.items():
                    lines_str = ", ".join(map(str, line_nos))
                    variants.append(f"'{display_name}' (lines {lines_str})")
                warnings.append(
                    f"{file_prefix}Duplicate person '{unique_key}' with different display names: {'; '.join(variants)}"
                )
            else:
                # Same person with same display name appearing multiple times
                display_name = list(display_names.keys())[0]
                lines_str = ", ".join(map(str, sorted(total_lines)))
                warnings.append(
                    f"{file_prefix}Duplicate person '{display_name}' appears on lines: {lines_str}"
                )
    
    return warnings


def build_people_set(rows: List[ParsedRow]) -> Dict[str, Dict[str, str]]:
    """
    Returns dict keyed by unique key (first+last name) with payload fields for /people creation.
    Uses first name only as display_name for presentation.
    Only Person 1's are created per your requirement.
    
    This resolves duplicates: people with same first name but different last names
    will be stored separately using their unique keys.
    """
    people: Dict[str, Dict[str, str]] = {}
    for r in rows:
        if r.person1_key not in people:
            # Use first name only for display, but full key for uniqueness
            people[r.person1_key] = {
                "display_name": r.person1_first,  # Show only first name
                "sex": "M" if r.gender1 == "M" else "F" if r.gender1 == "F" else "M",
                "notes": r.details or "",
            }
        else:
            # if later lines add details, keep first non-empty
            if r.details and not people[r.person1_key].get("notes"):
                people[r.person1_key]["notes"] = r.details
    return people


def build_relationship_requests(
    rows: List[ParsedRow],
    name_to_id: Dict[str, str],
) -> Tuple[List[Tuple[int, Dict[str, str]]], List[str]]:
    """
    Returns tuple of (relationships, warnings).
    relationships: list of (line_no, rel_payload)
    warnings: list of warning messages for skipped items
    
    Enforces: Person2 must exist in name_to_id if referenced.
    Only processes CHILD_OF relationships. Other types are ignored for now.
    
    Disambiguation strategy for duplicate names:
    - Uses file ordering to resolve ambiguity
    - When Person 2 (parent) matches multiple people, uses the MOST RECENT
      occurrence that appeared BEFORE the current line
    - This assumes file is ordered: parents listed before their children
    """
    rels: List[Tuple[int, Dict[str, str]]] = []
    warnings: List[str] = []
    
    # Build a reverse lookup: original person1 name -> list of (line_no, unique_key)
    # Ordered by line number for disambiguation
    name_to_entries: Dict[str, List[Tuple[int, str]]] = {}
    for r in rows:
        original_name = r.person1
        if original_name not in name_to_entries:
            name_to_entries[original_name] = []
        name_to_entries[original_name].append((r.line_no, r.person1_key))

    for r in rows:
        if r.relation in SKIP_RELATIONS:
            continue

        if r.relation not in REL_MAP:
            # Skip unknown relations instead of raising error
            warnings.append(f"Line {r.line_no}: Skipped unknown relation '{r.relation}' (will support in future)")
            continue
        
        # Only process CHILD_OF relationships for now
        rel_type = REL_MAP[r.relation]
        if rel_type != "CHILD_OF":
            warnings.append(f"Line {r.line_no}: Skipped relation type '{rel_type}' (not yet supported)")
            continue

        # must reference an existing person2 (as per your rule)
        # Person2 is referenced by their original name, but we need to find their unique key
        if r.person2:
            # Look up Person 2 by their original person1 name
            if r.person2 not in name_to_entries:
                warnings.append(
                    f"Line {r.line_no}: Person 2 '{r.person2}' not found (must exist as Person 1 somewhere)"
                )
                continue
            
            # Find the most recent occurrence of this person BEFORE the current line
            matching_entries = name_to_entries[r.person2]
            # Filter to entries that appear before current line
            valid_entries = [(line_no, key) for line_no, key in matching_entries if line_no < r.line_no]
            
            if not valid_entries:
                warnings.append(
                    f"Line {r.line_no}: Person 2 '{r.person2}' not found before this line (parent must be defined first)"
                )
                continue
            
            # Use the most recent one (last in the filtered list)
            parent_key = valid_entries[-1][1]
            to_id = name_to_id[parent_key]
        else:
            # if no person2 provided, that's not a valid relationship in your schema
            warnings.append(f"Line {r.line_no}: Person 2 is required for relation '{r.relation}'")
            continue

        # child = Person1 (person1's ID) - use unique key
        from_id = name_to_id[r.person1_key]

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

    return rels, warnings
