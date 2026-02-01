# Backend Testing Guide

This guide covers testing the Python FastAPI backend using pytest.

## Setup

### Install Dependencies

```bash
# Install the package in development mode
pip install -e .

# Install test dependencies
pip install pytest pytest-cov pytest-asyncio pytest-xdist
```

### Database Testing

Backend tests use an **in-memory SQLite database** (see [conftest.py](conftest.py)) to avoid touching the production database. Each test gets a fresh session that automatically rolls back changes.

## Running Tests

### Run All Backend Tests
```bash
pytest tests/backend/ -v
```

### Run Specific Test Suite
```bash
pytest tests/backend/unit/test_crud.py -v
pytest tests/backend/unit/test_models.py -v
pytest tests/backend/unit/test_schemas.py -v
```

### Run with Coverage Report
```bash
pytest tests/backend/ --cov=app --cov-report=term-missing
pytest tests/backend/ --cov=app --cov-report=html  # HTML report in htmlcov/
```

### Run Tests in Parallel (faster)
```bash
pytest tests/backend/ -n auto
```

### Run Tests in Watch Mode (re-run on file changes)
```bash
pytest-watch tests/backend/ -c
```

## Test Structure

### Unit Tests (`tests/backend/unit/`)

**test_crud.py** - CRUD operations
- `TestCreatePerson` - Creating people with various configurations
- `TestListPeople` - Querying people with filters
- `TestCreateRelationship` - Creating relationships with constraints
- `TestListRelationships` - Querying relationships
- `TestTreeVersioning` - Version management and constraints

**test_models.py** - Model validation
- `TestPersonModel` - Person ORM model
- `TestRelationshipModel` - Relationship constraints
- `TestTreeModel` - Tree model
- `TestTreeVersionModel` - Version model
- `TestSexEnum` - Sex enumeration
- `TestRelTypeEnum` - Relationship type enumeration
- `TestModelRelationships` - SQLAlchemy relationships

**test_schemas.py** - Pydantic schema validation
- `TestPersonCreateSchema` - PersonCreate validation
- `TestPersonOutSchema` - PersonOut response validation
- `TestRelCreateSchema` - RelCreate with relationship type constraints
- `TestRelationshipOutSchema` - RelationshipOut validation
- `TestTreeCreateSchema` - TreeCreate validation
- `TestTreeFilterSchema` - TreeFilter logic
- `TestTreeImportRequestSchema` - Import request validation

### Fixtures (conftest.py)

Reusable test data:

```python
# Database setup
test_db_engine          # In-memory SQLite for entire test session
db_session              # Fresh session for each test (auto-rollback)

# Sample data
sample_tree             # A test tree
sample_tree_version     # A tree version
sample_person           # A male test person
sample_person_female    # A female test person
sample_person_child     # A child test person
sample_earliest_ancestor_rel  # Root node relationship
sample_child_relationship     # CHILD_OF relationship
sample_spouse_relationship    # SPOUSE_OF relationship
populated_tree          # Fully populated tree with people and relationships
```

**Usage:**
```python
def test_something(db_session, sample_tree, sample_person):
    # Test code using fixtures
    pass
```

## Test Data Fixtures

Sample test data is in `tests/fixtures/sample-trees.json`:

- **simple_tree**: 3 people (patriarch, matriarch, child) with relationships
- **name_variations**: Edge cases for name parsing
- **complex_tree**: Metadata for larger test scenarios

## Writing New Tests

### Example: Test a CRUD operation

```python
def test_create_person_with_tree_version(db_session, sample_tree, sample_tree_version):
    """Test creating a person linked to a specific tree version."""
    person = crud.create_person(
        db_session,
        display_name="Versioned Person",
        sex="F",
        notes=None,
        tree_id=sample_tree.id,
        tree_version_id=sample_tree_version.id
    )
    
    assert person.tree_id == sample_tree.id
    assert person.tree_version_id == sample_tree_version.id
    assert person.sex == Sex.F
```

### Example: Test a constraint

```python
def test_enforce_one_earliest_ancestor_per_version(db_session, sample_tree, sample_tree_version, sample_person, sample_person_female):
    """Test that only one EARLIEST_ANCESTOR can exist per tree version."""
    # Create first earliest ancestor
    rel1 = crud.create_relationship(...)
    
    # Try to create second - should fail
    with pytest.raises(Exception):
        rel2 = crud.create_relationship(...)
```

## Test Markers

Tag tests for selective running:

```python
@pytest.mark.unit
def test_something():
    pass

@pytest.mark.integration
def test_something():
    pass
```

Run by marker:
```bash
pytest -m unit                  # Only unit tests
pytest -m integration           # Only integration tests
pytest -m "not integration"     # Everything except integration
```

## CI/CD Integration

Tests run automatically on push via GitHub Actions:

- **Backend Tests** (`.github/workflows/backend-tests.yml`):
  - Python 3.9, 3.11
  - Coverage reports uploaded to Codecov
  - Runs on each push and pull request

- **Frontend Tests** (`.github/workflows/frontend-tests.yml`):
  - Jest unit tests
  - Playwright E2E tests
  - Coverage reports

## Coverage Thresholds

Current targets:
- **Backend**: 70%+ coverage (in progress)
- **Frontend**: 60%+ coverage (in progress)

## Common Issues

### "ModuleNotFoundError: No module named 'app'"
- Ensure you run tests from workspace root: `cd /workspaces/family-tree`
- Install in dev mode: `pip install -e .`

### "sqlite3.OperationalError: database is locked"
- Tests use in-memory database and auto-rollback
- If running in parallel, use: `pytest -n auto` (uses xdist)

### Test timeout
- Increase timeout in pytest.ini or CLI: `pytest --timeout=30`

## Next Steps

**Phase 2 - Full Backend Coverage**:
- [ ] Write import/parsing tests
- [ ] Write API endpoint tests
- [ ] Write error handling tests
- [ ] Write integration tests

**Phase 3 - Frontend Unit Tests**:
- [ ] Replace placeholder tests with real implementations
- [ ] Extract functions from app.js for testability
- [ ] Add UI logic tests

See [TEST_COVERAGE_ASSESSMENT.md](../TEST_COVERAGE_ASSESSMENT.md) for detailed roadmap.
