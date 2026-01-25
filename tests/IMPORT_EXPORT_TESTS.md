# Import/Export Test Suite

Comprehensive test coverage for import and export functionality to prevent regressions during future code changes.

## Test Coverage

### Unit Tests (24 tests)
Location: [tests/unit/import-export.test.js](tests/unit/import-export.test.js)

**Export Data Structure (5 tests)**
- ✓ export should include tree metadata
- ✓ export should include tree version metadata  
- ✓ export should include arrays for people and relationships
- ✓ person records should have required fields
- ✓ relationship records should have required fields

**Filename Generation (5 tests)**
- ✓ should sanitize tree names for filenames
- ✓ should include version number in filename
- ✓ should generate consistent filenames for same tree version
- ✓ should generate different filenames for different versions
- ✓ custom filename should not include timestamp

**Version Management (5 tests)**
- ✓ should detect existing file for same version
- ✓ should not match files from different versions
- ✓ should maintain version sequence
- ✓ cleanup should identify old versions
- ✓ cleanup should not delete custom filenames

**Data Validation (5 tests)**
- ✓ exported tree should have valid structure
- ✓ exported tree_version should have valid structure
- ✓ people array should contain valid person objects
- ✓ relationships array should contain valid relationship objects
- ✓ null values should be handled correctly

**Import Payload (4 tests)**
- ✓ import request should have required fields
- ✓ import response should return tree_id and version
- ✓ tree_id should be optional for first import
- ✓ tree_id should be provided for version increment

### E2E Tests (18 tests)
Location: [tests/e2e/import-export.spec.js](tests/e2e/import-export.spec.js)

**Export Endpoint (5 tests)**
- ✓ should export data as JSON
- ✓ should include tree metadata when tree_id is provided
- ✓ should include tree version in response
- ✓ should filter by tree_version_id when provided
- ✓ should download with descriptive filename

**Save to Disk (3 tests)**
- ✓ should save export to data/exports/ directory
- ✓ should include tree name and version in auto-generated filename
- ✓ should overwrite existing file for same tree version
- ✓ should support custom filename
- ✓ should not auto-delete custom filenames during cleanup

**Import Endpoint (5 tests)**
- ✓ should create tree and version on first import
- ✓ should increment version on subsequent imports
- ✓ should return correct tree_version_id
- ✓ should allow filtering exports by specific tree_version

**Export File Content Validation (5 tests)**
- ✓ should contain valid JSON structure
- ✓ should have people as array
- ✓ should have relationships as array
- ✓ each person should have required fields
- ✓ each relationship should have required fields

## Running Tests

### Unit Tests Only (fast, deterministic)
```bash
npm test -- tests/unit/import-export.test.js
# or all unit tests:
npm test -- tests/unit/
```

### E2E Tests (requires running services)
```bash
npx playwright test tests/e2e/import-export.spec.js
```

### All Tests
```bash
npm test -- --silent && npx playwright test tests/e2e/
```

## Test Architecture

### Unit Tests
- **Approach**: Validation-focused, no API calls
- **Purpose**: Verify data structures, filename logic, cleanup logic
- **Speed**: Fast (~0.5s)
- **Reliability**: 100% (deterministic)

### E2E Tests  
- **Approach**: Integration-focused, real API calls
- **Purpose**: Verify end-to-end workflows, file I/O, version management
- **Speed**: Slower (~30-60s per test run)
- **Reliability**: Requires clean database state

## Key Test Scenarios

### Import Scenarios
1. **First import** - creates tree v1
2. **Subsequent imports** - increments version
3. **Version filtering** - export specific tree_version_id

### Export Scenarios
1. **Download mode** - returns file without saving to disk
2. **Save to disk** - saves to `data/exports/` with tree name + version
3. **Version overwrite** - same version overwrites previous export
4. **Version separation** - different versions create different files
5. **Custom filenames** - preserved indefinitely, never auto-deleted
6. **Version cleanup** - keeps last 5 versions, deletes older ones

### Data Validation
1. **Required fields** - all records have necessary attributes
2. **Array structure** - people and relationships are arrays
3. **Tree metadata** - includes name, description, version info
4. **Person records** - include id, display_name, sex, notes
5. **Relationship records** - include id, from_person_id, to_person_id, type

## Maintenance

When making changes to import/export code:
1. Run unit tests first: `npm test -- tests/unit/import-export.test.js`
2. Run e2e tests: `npx playwright test tests/e2e/import-export.spec.js`
3. Both should pass before committing

If tests fail:
- Unit test failures indicate logic issues in validation/cleanup
- E2E test failures indicate API integration issues
- Check database state (version numbers may accumulate across test runs)
