# Family Tree Application - AI Coding Agent Instructions

## Architecture Overview

This is a full-stack family tree genealogy application with:
- **Frontend**: HTML/JavaScript web UI with interactive Plotly graph visualization
- **Backend**: FastAPI (Python) REST API with versioned tree management
- **Database**: PostgreSQL with SQLAlchemy ORM (via Docker Compose)
- **Key Features**: Multi-tree support, version control, import/export, duplicate detection

### Core Data Model

Three main entity types drive the system:
- **Trees**: Collections of families with versions (e.g., "Gezaweldeamlak", "Adi Baro")
- **TreeVersions**: Immutable snapshots (auto-numbered) of a tree's state; imports create new versions
- **People & Relationships**: Linked records filtered by `tree_id` and `tree_version_id`

The design supports two filtering patterns:
1. **By `tree_version_id`**: Get specific versioned snapshot (canonical)
2. **By `tree_id`**: Get active version (see [crud.py](app/crud.py#L15-L20) - queries TreeVersion with `active==True`)

RelTypes: `CHILD_OF`, `SPOUSE_OF`, `EARLIEST_ANCESTOR` (root node, `to_person_id` must be null).

## Critical Developer Workflows

### Run the Stack Locally
```bash
docker compose up   # Starts PostgreSQL + FastAPI (http://localhost:8080)
```

### Database Access (Interactive SQL)
```bash
docker compose exec db psql -U app -d familytree
# SQL commands: \dt (list tables), \d table_name (describe), \q (quit)
# Always end SQL with semicolon
```

### Import Family Tree Data
Two supported formats (CSV-like text or JSON):
```bash
# Option 1: Via CLI (creates new tree + version)
docker compose exec api python3 -m app.importers.import_family_tree /app/data/gezaweldeamlak.txt

# Option 2: Via HTTP upload (handles tree_id logic, creates new version if tree_id provided)
curl -X POST http://localhost:8080/import -F "file=@data/file.txt"
```

### Export Data
```bash
# Export to JSON (defaults to active version if preferred_non_empty=true)
curl "http://localhost:8080/export?tree_id=1&save_to_disk=true"
# Saves to: data/exports/tree_name_v{version}_{timestamp}.json
# Keeps last 5 versions per tree automatically
```

### Run Tests
```bash
# Backend Python tests (NEW - 73 tests covering CRUD, models, schemas)
pytest tests/backend/ -v                    # All backend tests
pytest tests/backend/ --cov=app            # With coverage report
pytest tests/backend/unit/ -v              # Unit tests only

# Frontend JavaScript tests
npm test                    # Jest unit tests with coverage
npm run test:e2e           # Playwright (http://localhost:8888)
npm run test:e2e:ui        # Interactive UI mode
npm run test:all           # All frontend tests
./tests/run-all-tests.sh   # All tests (comprehensive)
```

## Test Structure

Tests are organized by stack:
- **tests/backend/**: Python tests (unit, integration, api)
- **tests/frontend/**: JavaScript tests (unit, e2e)
- **tests/fixtures/**: Shared test data

See [TESTING.md](TESTING.md) for detailed guide.

## Project-Specific Patterns & Conventions

### FastAPI Routes Pattern
- Query params for filtering: `tree_id`, `tree_version_id` (see [main.py](app/main.py#L26-L37))
- Accept both query params AND POST body (`schemas.TreeFilter`) for flexibility
- Prefer explicit `tree_version_id` over `tree_id` if both provided
- All POST operations return matching `*Out` schema (e.g., `PersonOut`)

### Import Processing
- **Text format**: [family_tree_text.py](app/importers/family_tree_text.py) parses CSV-like rows → `ParsedRow` objects
- **Duplicate detection**: Built-in duplicate matcher using name similarity and gender
- **JSON format**: [family_tree_json.py](app/importers/family_tree_json.py) validates schema then inserts
- **Name parsing**: Handles varied formats ("John Smith", "First Middle Last", "Name\n(FamilyName)")
- **Relationship normalization**: Maps text relations (e.g., "Parent") to canonical types (`PARENT_OF`)

### Tree Versioning Strategy
- Imports always create new `TreeVersion` with auto-incremented `version` number
- Only one version can be `active=True` per tree (enforced in [crud.py](app/crud.py#L100+))
- UI queries `active=True` version by default; tests explicitly pass `tree_version_id`
- `EARLIEST_ANCESTOR` constraint: One root per tree/version (see [crud.py](app/crud.py#L45-L52))

### Database Connection Pooling
SQLAlchemy configured for production-scale concurrency:
- Pool size: 20, max overflow: 30 (50 concurrent connections max)
- Pool timeout: 60s, connection recycle: 1 hour
- See [db.py](app/db.py) for config

### Plotly Graph Rendering
- [graph.py](app/graph.py) merges published data with **working drafts** if both `tree_id` and `tree_version_id` provided
- Draft people tagged with `is_draft=True` for UI styling
- Draft relationship ops: `replace` (remove existing from-person rels), `delete` (remove specific rel), `create` (add new)
- Layout generator: [plotly_render.py](app/plotly_graph/plotly_render.py) computes hierarchical layout using tree traversal

### Frontend UI Conventions
- **Context menus**: Global dismissal on Escape, click, scroll (see [TESTING.md](tests/TESTING.md#L22-L33))
- **Selection state**: Only one node/edge selected at a time; selection clears on new selection
- **Event handlers**: Bound once to prevent duplicates on re-render (see [ui-interactions.spec.js](tests/e2e/ui-interactions.spec.js))
- **Graph interaction**: Right-click opens context menu; click inside graph closes menus

## Integration Points & External Dependencies

### PostgreSQL Health Checks
- Docker Compose uses `pg_isready` with 5s intervals, 10 retry max
- API waits for db `service_healthy` before starting
- Connection string: `postgresql+psycopg://app:app@db:5432/familytree` (psycopg driver for async)

### Pydantic Validation
- Custom validators in schemas (e.g., `RelCreate.validate_to_person_id`) enforce domain rules
- `to_person_id` must be null for `EARLIEST_ANCESTOR`, non-null for others

### NetworkX & Plotly Dependencies
- [networkx](https://networkx.org/) for graph algorithms (not visible in imports, used in plotly_render)
- [plotly](https://plotly.com/python/) for interactive visualization (see imports in [main.py](app/main.py#L1))

### File Upload Handling
- FastAPI `UploadFile` with Content-Type detection via Path suffix (.txt, .csv, .json)
- Uploaded files read into memory (suitable for typical ~1MB tree files)
- Errors: Unsupported formats, missing filenames

## Known Quirks & Gotchas

1. **Non-permanent DB by default**: Database data persists in containers but is lost on `docker compose down`. Archive frequently with `docker compose exec db pg_dump`.
2. **Duplicate detection**: Text importer has built-in matching; JSON importer assumes clean data. Merging duplicates is manual.
3. **Root node isolation**: `EARLIEST_ANCESTOR` relationships have no `to_person_id`, which may confuse UI that expects bidirectional edges.
4. **Version immutability**: Imported versions are immutable; edits create drafts in `WorkingChange` table, not persisted versions.
5. **Test ports**: Frontend tests run API on port 8888 (see [TESTING.md](TESTING.md#L8)); local dev uses 8080.

## Key Files to Know

| File | Purpose |
|------|---------|
| [app/main.py](app/main.py) | FastAPI routes, import/export endpoints |
| [app/models.py](app/models.py) | SQLAlchemy ORM: Tree, Person, Relationship, TreeVersion |
| [app/crud.py](app/crud.py) | Database queries, versioning logic |
| [app/importers/family_tree_text.py](app/importers/family_tree_text.py) | Text file parsing, name normalization |
| [app/graph.py](app/graph.py) | Graph data merging, draft integration |
| [app/plotly_graph/plotly_render.py](app/plotly_graph/plotly_render.py) | Hierarchical layout, edge/node rendering |
| [web/app.js](web/app.js) | Frontend interactions, Plotly graph display |
| [tests/e2e/ui-interactions.spec.js](tests/e2e/ui-interactions.spec.js) | Playwright E2E tests |
| [docker-compose.yml](docker-compose.yml) | Service definitions, DB/API setup |

## Common Tasks for AI Agents

### Add a New Import Format
1. Create `app/importers/format_name.py` with parser function
2. Export list of `ParsedRow` or `(people_dict, relationships_list)` tuples
3. Update [import_family_tree.py](app/importers/import_family_tree.py) to detect file type and route
4. Add integration test in [tests/e2e/import-export.spec.js](tests/e2e/import-export.spec.js)

### Fix UI Selection Logic
1. Trace issue in [web/app.js](web/app.js) and ensure only one event handler exists
2. Review [TESTING.md](TESTING.md#L22-L33) for expected behavior
3. Add/update Playwright test in [tests/e2e/ui-interactions.spec.js](tests/e2e/ui-interactions.spec.js)
4. Run `npm run test:e2e:ui` to verify interactively

### Modify Database Schema
1. Edit [app/models.py](app/models.py) SQLAlchemy models
2. Database auto-creates on first run (see [main.py](app/main.py#L17))
3. For migrations, manual SQL scripts in [family_tree.sql](family_tree.sql)
4. Test: `docker compose exec db psql -U app -d familytree < family_tree.sql`

### Debug Tree Versioning
1. Query `TreeVersion` table: `SELECT * FROM tree_versions WHERE tree_id=1;`
2. Check `active` flag in [crud.py](app/crud.py#L15-L20) filtering logic
3. Review [TESTING.md](TESTING.md) test setup for `tree_version_id` patterns
