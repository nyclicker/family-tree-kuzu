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
    parser.add_argument("--tree-id", type=int, default=None, help="Optional tree id to import into")
    args = parser.parse_args()

    file_path = Path(args.txt_path)
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    rows = parse_family_tree_txt(file_path)
    people_payloads = build_people_set(rows)

    client = TestClient(app)

    tree_id = args.tree_id

    # If no tree_id provided, create/find tree and create a new version using the filename
    tree_version_id = None
    if tree_id is None:
        import_payload = {
            "name": file_path.stem,
            "source_filename": file_path.name,
        }
        resp = client.post("/trees/import", json=import_payload)
        if resp.status_code >= 400:
            raise SystemExit(f"/trees/import failed: {resp.status_code} {resp.text}")
        data = resp.json()
        tree_id = data["tree_id"]
        tree_version_id = data["tree_version_id"]

    # Create people (Person 1 only)
    name_to_id: dict[str, str] = {}
    for name, payload in people_payloads.items():
        send_payload = dict(payload)
        send_payload["tree_id"] = tree_id
        if tree_version_id is not None:
            send_payload["tree_version_id"] = tree_version_id
        resp = client.post("/people", json=send_payload)
        if resp.status_code >= 400:
            raise SystemExit(f"/people failed for {name!r}: {resp.status_code} {resp.text}")
        name_to_id[name] = resp.json()["id"]

    # Create relationships (validates Person2 exists in Person1 set)
    rel_reqs = build_relationship_requests(rows, name_to_id)
    for line_no, rel_payload in rel_reqs:
        send_rel = dict(rel_payload)
        send_rel["tree_id"] = tree_id
        if tree_version_id is not None:
            send_rel["tree_version_id"] = tree_version_id
        resp = client.post("/relationships", json=send_rel)
        if resp.status_code >= 400:
            raise SystemExit(f"Line {line_no}: /relationships failed: {resp.status_code} {resp.text}")

    print(f"Import complete: {len(name_to_id)} people, {len(rel_reqs)} relationships")

if __name__ == "__main__":
    main()
