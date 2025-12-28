from __future__ import annotations
from typing import Optional, Tuple
import pandas as pd

def normalize_person(raw_value: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Returns:
      person_id     -> internal unique key (full raw string)
      display_label -> short label on the node:
                         - if '\\n(' or '\n(' present: 'Base\\n(Nick)'
                         - else: 'First Last' (first + last token)
      hover_label   -> full label for hover:
                         - if nickname syntax: 'Base (Nick)'
                         - else: full raw value
    """
    if raw_value is None or pd.isna(raw_value):
        return None, None, None

    raw = str(raw_value).strip()
    if raw == "" or raw.lower() in ("none", "nan"):
        return None, None, None

    person_id = raw  # stable internal key = raw string

    # CASE 1: explicit '\n(NickName)' or actual newline
    if "\\n(" in raw or "\n(" in raw:
        if "\\n(" in raw:
            base, rest = raw.split("\\n(", 1)
        else:
            base, rest = raw.split("\n(", 1)
        nick = rest.rstrip(")")

        display_label = f"{base}\n({nick})"
        hover_label = f"{base} ({nick})"
        return person_id, display_label, hover_label

    # CASE 2: no nickname
    parts = raw.split()
    if len(parts) == 1:
        display_label = parts[0]
    else:
        display_label = f"{parts[0]} {parts[-1]}"

    hover_label = raw
    return person_id, display_label, hover_label
