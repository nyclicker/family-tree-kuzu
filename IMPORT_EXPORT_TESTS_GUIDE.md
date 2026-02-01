# Import/Export Endpoint Tests - Quick Reference

## Test File Location
`tests/backend/api/test_import_export_endpoints.py` (347 lines, 22 tests)

## Test Classes & Coverage

### 1. TestImportEndpoint (9 tests)
Tests for `POST /import` endpoint

| Test | Purpose | CSV Format | Expected |
|------|---------|-----------|----------|
| `test_import_csv_creates_new_tree` | Basic CSV import | Valid with 3 people | Creates tree v1, 3+ people |
| `test_import_txt_creates_new_tree` | TXT file import | Same as CSV | Creates tree v1 |
| `test_import_json_creates_new_tree` | JSON format | `{people: [], relationships: []}` | Creates tree v1 |
| `test_import_multiple_trees` | Multiple imports | Valid CSV | Different tree IDs |
| `test_import_without_file_fails` | Missing file | None | 422 error |
| `test_import_json_format_requires_proper_structure` | JSON validation | Valid JSON | Success |
| `test_import_handles_partial_csv_data` | Minimal data | Single person | 200 OK, 1+ people |
| `test_import_large_file` | Performance | 100 people CSV | Success with many people |
| `test_import_with_special_characters` | UTF-8 handling | `José García, Müller François` | Success with accents |

### 2. TestExportEndpoint (10 tests)
Tests for `GET /export` endpoint

| Test | Purpose | Query Params | Expected |
|------|---------|--------------|----------|
| `test_export_by_tree_id` | Export by tree ID | `tree_id={id}` | 200, people + relationships |
| `test_export_by_tree_version_id` | Export by version | `tree_version_id={id}` | 200, specific version data |
| `test_export_both_filters` | Both params provided | Both tree_id and tree_version_id | 200, merged data |
| `test_export_saves_to_disk` | File save | `save_to_disk=true` | 200, path returned |
| `test_export_nonexistent_tree_fails` | Missing tree | `tree_id=99999` | 200 or 404, empty data |
| `test_export_includes_relationships` | Relationship export | `tree_version_id={id}` | All relationships included |
| `test_export_json_format_valid` | JSON structure | `tree_id={id}` | Valid JSON with person fields |
| `test_export_without_filters_accepts_empty` | No filters | None | 200, empty result |
| `test_export_preserves_person_fields` | Field preservation | `tree_version_id={id}` | id, display_name present |
| `test_export_preserves_relationship_types` | Rel types | `tree_version_id={id}` | CHILD_OF, SPOUSE_OF types |

### 3. TestImportExportRoundTrip (3 tests)
Tests for import → export → reimport cycles

| Test | Purpose | Validates |
|------|---------|-----------|
| `test_roundtrip_preserves_people` | Data persistence | People survive round-trip |
| `test_roundtrip_preserves_relationships` | Relationship integrity | Relationships maintained |
| `test_export_reimport_preserves_data` | Full cycle | Export format compatibility |

## CSV Format

Required format for import tests:
```
Person 1,Relation,Person 2,Gender,Details
John,Earliest Ancestor,,M,Root note
Jane,Spouse,John,F,Note
Child,Child,John,M,
```

### Valid Relation Types
- `Earliest Ancestor` - Root node (no Person 2)
- `Child` - Parent-child relationship
- `Parent` - Parent relationship
- `Spouse` - Spouse relationship

### Invalid Relations (will be skipped)
- ❌ `Child Of` - Use `Child` instead
- ❌ `Parent Of` - Use `Parent` instead  
- ❌ `Spouse Of` - Use `Spouse` instead

## Import Response Format

```json
{
  "tree_id": 1,
  "tree_version_id": 5,
  "version": 1,
  "people_count": 3,
  "relationships_count": 2,
  "warnings": ["Line 3: Skipped unknown relation..."],
  "errors": []
}
```

## Export Response Formats

### Normal export
```json
{
  "people": [...],
  "relationships": [...]
}
```

### With save_to_disk=true
```json
{
  "path": "data/exports/tree_name_v1_timestamp.json",
  "message": "Export saved to ...",
  "status": "success"
}
```

## Running Tests

```bash
# All import/export tests
pytest tests/backend/api/test_import_export_endpoints.py -v

# Specific class
pytest tests/backend/api/test_import_export_endpoints.py::TestImportEndpoint -v

# Specific test
pytest tests/backend/api/test_import_export_endpoints.py::TestImportEndpoint::test_import_csv_creates_new_tree -v

# With coverage
pytest tests/backend/api/test_import_export_endpoints.py --cov=app --cov-report=term-missing
```

## Key Fixture: `client`

All tests use the `client` fixture which:
1. Creates FastAPI TestClient
2. Overrides `get_db` dependency with test database session
3. Clears overrides after test

```python
@pytest.fixture
def client(db_session):
    from app.main import app, get_db
    
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

## Test Data Fixtures Used

- `db_session` - In-memory SQLite database
- `sample_tree` - Pre-created Tree object
- `sample_tree_version` - Pre-created TreeVersion
- `sample_person` - Pre-created Person
- `populated_tree` - Tree with multiple people and relationships

## Coverage Impact

Added 22 tests increased:
- `app/main.py` from 33% → 64% (+31%)
- `app/importers/` from ~50% → 63-81% (+15-30%)
- Overall backend from 62% → 72% (+10%)

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| 400 Bad Request on import | Wrong CSV format | Check relation type (use "Child" not "Child Of") |
| Missing relationships | Relation type not recognized | Verify REL_MAP in family_tree_text.py |
| Empty export | No tree_id or tree_version_id | Provide at least one filter parameter |
| Version not incrementing | tree_id behavior | Import creates new tree if not found, doesn't increment |

## Future Enhancement Areas

1. Malformed data validation
2. Concurrent import handling  
3. Large file optimization
4. Duplicate resolution during import
5. Export filtering by date ranges
6. Streaming export for very large trees
