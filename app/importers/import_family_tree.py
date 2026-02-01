from __future__ import annotations

import argparse
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.importers.family_tree_text import (
    parse_family_tree_txt,
    build_people_set,
    build_relationship_requests,
    detect_duplicates,
)
from app.importers.family_tree_json import (
    parse_family_tree_json,
    extract_people_for_import,
    extract_relationships_for_import,
)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file_path", help="Path to family tree file (.txt or .json) inside container")
    parser.add_argument("--tree-id", type=int, default=None, help="Optional tree id to import into")
    args = parser.parse_args()

    file_path = Path(args.file_path)
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    # Detect file type: .json vs .txt/.csv (both treated as text-based CSV format)
    is_json = file_path.suffix.lower() == ".json"
    is_text_format = file_path.suffix.lower() in (".txt", ".csv")
    
    rel_reqs = []
    rel_warnings = []

    if is_json:
        json_data = parse_family_tree_json(file_path)
        people_payloads = extract_people_for_import(json_data)
        rel_reqs, rel_warnings = extract_relationships_for_import(json_data, {})  # name_to_id map built below
    elif is_text_format:
        rows = parse_family_tree_txt(file_path)
        
        # Detect and display duplicate warnings
        duplicate_warnings = detect_duplicates(rows, file_path.name)
        if duplicate_warnings:
            print("\n⚠️  DUPLICATE WARNINGS:")
            for warning in duplicate_warnings:
                print(f"  - {warning}")
            print()
        
        people_payloads = build_people_set(rows)
    else:
        raise SystemExit(f"Unsupported file format: {file_path.suffix}. Use .txt, .csv, or .json")

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

    # Create people
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

    # Create relationships
    if is_json:
        if rel_warnings:
            print("\n⚠️  RELATIONSHIP WARNINGS:")
            for warning in rel_warnings:
                print(f"  - {warning}")
            print()
    elif is_text_format:
        rel_reqs, rel_warnings = build_relationship_requests(rows, name_to_id)
        if rel_warnings:
            print("\n⚠️  RELATIONSHIP WARNINGS:")
            for warning in rel_warnings:
                print(f"  - {warning}")
            print()
    
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
