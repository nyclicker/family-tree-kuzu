from __future__ import annotations

import argparse
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.importers.family_tree_text import (
    parse_family_tree_txt,
    build_people_set,
    build_relationship_requests,
)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("txt_path", help="Path to family tree .txt file inside container")
    args = parser.parse_args()

    file_path = Path(args.txt_path)
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    rows = parse_family_tree_txt(file_path)
    people_payloads = build_people_set(rows)

    client = TestClient(app)

    # Create people (Person 1 only)
    name_to_id: dict[str, str] = {}
    for name, payload in people_payloads.items():
        resp = client.post("/people", json=payload)
        if resp.status_code >= 400:
            raise SystemExit(f"/people failed for {name!r}: {resp.status_code} {resp.text}")
        name_to_id[name] = resp.json()["id"]

    # Create relationships (validates Person2 exists in Person1 set)
    rel_reqs = build_relationship_requests(rows, name_to_id)
    for line_no, rel_payload in rel_reqs:
        resp = client.post("/relationships", json=rel_payload)
        if resp.status_code >= 400:
            raise SystemExit(f"Line {line_no}: /relationships failed: {resp.status_code} {resp.text}")

    print(f"Import complete: {len(name_to_id)} people, {len(rel_reqs)} relationships")

if __name__ == "__main__":
    main()
