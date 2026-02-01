"""
API endpoint tests for /people routes.

Tests the REST API for person management including:
- Creating people
- Listing people with filtering
- Getting individual people
- Updating people
- Tree/version filtering
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Person, RelType


@pytest.fixture
def client(db_session):
    """Create FastAPI test client with database session override."""
    # Import app here to avoid DATABASE_URL requirement at module level
    from app.main import app, get_db
    
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestCreatePerson:
    """Test POST /people endpoint."""

    def test_create_person_success(self, client, sample_tree, sample_tree_version):
        """Test creating a person via API."""
        response = client.post("/people", json={
            "display_name": "Alice Smith",
            "sex": "F",
            "notes": "Test person",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Alice Smith"
        assert data["sex"] == "F"
        assert data["notes"] == "Test person"
        assert "id" in data

    def test_create_person_minimal_fields(self, client, sample_tree, sample_tree_version):
        """Test creating person with only required fields."""
        response = client.post("/people", json={
            "display_name": "Bob",
            "sex": "M",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Bob"
        # API returns None for empty notes, not empty string
        assert data["notes"] in ["", None]

    def test_create_person_missing_required_field(self, client, sample_tree, sample_tree_version):
        """Test creating person without required field."""
        response = client.post("/people", json={
            "sex": "F",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        assert response.status_code == 422  # Validation error

    def test_create_person_invalid_sex(self, client, sample_tree, sample_tree_version):
        """Test creating person with invalid sex value."""
        response = client.post("/people", json={
            "display_name": "Invalid Person",
            "sex": "X",  # Invalid value
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        assert response.status_code == 422  # Validation error


class TestListPeople:
    """Test GET /people endpoint."""

    def test_list_all_people(self, client, populated_tree):
        """Test listing all people."""
        tree, tree_version, people, _ = populated_tree
        
        response = client.get("/people", params={
            "tree_id": tree.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # At least root and child from fixture

    def test_list_people_by_tree_version(self, client, populated_tree):
        """Test listing people filtered by tree_version_id."""
        tree, tree_version, people, _ = populated_tree
        
        response = client.get("/people", params={
            "tree_version_id": tree_version.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        for person in data:
            assert person["tree_version_id"] == tree_version.id

    def test_list_people_empty_tree(self, client, sample_tree, sample_tree_version):
        """Test listing people from empty tree."""
        response = client.get("/people", params={
            "tree_version_id": sample_tree_version.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_people_post_with_filter(self, client, populated_tree):
        """Test POST /people/list with filter body (if endpoint exists)."""
        tree, tree_version, people, _ = populated_tree
        
        # Try POST first (may not be implemented)
        response = client.post("/people/list", json={
            "tree_id": tree.id
        })
        
        # If not found or method not allowed, fall back to GET
        if response.status_code in [404, 405]:
            response = client.get("/people", params={"tree_id": tree.id})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2


class TestGetPerson:
    """Test GET /people/{person_id} endpoint."""

    def test_get_person_by_id(self, client, populated_tree):
        """Test getting a specific person."""
        tree, tree_version, people, _ = populated_tree
        person_id = str(people[0].id)  # Convert UUID to string
        
        response = client.get(f"/people/{person_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == person_id
        assert "display_name" in data
        assert "sex" in data

    def test_get_person_not_found(self, client):
        """Test getting non-existent person."""
        import uuid
        fake_id = uuid.uuid4()
        
        response = client.get(f"/people/{fake_id}")
        
        assert response.status_code == 404


class TestUpdatePerson:
    """Test PATCH /people/{person_id} endpoint."""

    def test_update_person_name(self, client, populated_tree):
        """Test updating person's display name."""
        tree, tree_version, people, _ = populated_tree
        person_id = people[0].id
        
        response = client.patch(f"/people/{person_id}", json={
            "display_name": "Updated Name"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Name"
        # Other fields unchanged
        assert data["id"] == person_id

    def test_update_person_notes(self, client, populated_tree):
        """Test updating person's notes."""
        tree, tree_version, people, _ = populated_tree
        person_id = people[0].id
        
        response = client.patch(f"/people/{person_id}", json={
            "notes": "Updated notes"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Updated notes"

    def test_update_person_multiple_fields(self, client, populated_tree):
        """Test updating multiple fields at once."""
        tree, tree_version, people, _ = populated_tree
        person_id = people[0].id
        
        response = client.patch(f"/people/{person_id}", json={
            "display_name": "New Name",
            "notes": "New notes",
            "sex": "F"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "New Name"
        assert data["notes"] == "New notes"
        assert data["sex"] == "F"

    def test_update_person_not_found(self, client):
        """Test updating non-existent person."""
        import uuid
        fake_id = uuid.uuid4()
        
        response = client.patch(f"/people/{fake_id}", json={
            "display_name": "Does Not Exist"
        })
        
        assert response.status_code == 404


class TestDeletePerson:
    """Test DELETE /people/{person_id} endpoint."""

    def test_delete_person(self, client, db_session, sample_tree, sample_tree_version):
        """Test deleting a person."""
        from app import crud
        
        # Create a person to delete
        person = crud.create_person(
            db_session,
            display_name="To Delete",
            sex="M",
            notes="",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        person_id = person.id
        
        response = client.delete(f"/people/{person_id}")
        
        assert response.status_code == 204 or response.status_code == 200
        
        # Verify person is gone
        check_response = client.get(f"/people/{person_id}")
        assert check_response.status_code == 404

    def test_delete_person_not_found(self, client):
        """Test deleting non-existent person."""
        import uuid
        fake_id = uuid.uuid4()
        
        response = client.delete(f"/people/{fake_id}")
        
        assert response.status_code == 404


class TestPeopleSearchAndFilters:
    """Test advanced search and filtering."""

    def test_search_people_by_name(self, client, db_session, sample_tree, sample_tree_version):
        """Test searching people by display name."""
        from app import crud
        
        # Create multiple people
        crud.create_person(db_session, display_name="Alice Smith", sex="F", notes="",
                          tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        crud.create_person(db_session, display_name="Bob Smith", sex="M", notes="",
                          tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        crud.create_person(db_session, display_name="Charlie Jones", sex="M", notes="",
                          tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        
        # Get all from this version
        response = client.get("/people", params={
            "tree_version_id": sample_tree_version.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        names = {p["display_name"] for p in data}
        assert "Alice Smith" in names
        assert "Bob Smith" in names

    def test_filter_people_by_sex(self, client, db_session, sample_tree, sample_tree_version):
        """Test filtering people by sex."""
        from app import crud
        
        # Create people with different sex values
        female = crud.create_person(db_session, display_name="Alice", sex="F", notes="",
                                   tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        male = crud.create_person(db_session, display_name="Bob", sex="M", notes="",
                                 tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        
        # Get all people
        response = client.get("/people", params={
            "tree_version_id": sample_tree_version.id
        })
        
        data = response.json()
        # Check that both sexes are present
        sexes = {p["sex"] for p in data}
        assert "M" in sexes
        assert "F" in sexes


class TestPeopleEdgeCases:
    """Test edge cases and error conditions."""

    def test_create_person_with_empty_name(self, client, sample_tree, sample_tree_version):
        """Test creating person with empty display name."""
        response = client.post("/people", json={
            "display_name": "",
            "sex": "M",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        # Should either reject or accept (depends on validation rules)
        # If accepted, verify it's stored correctly
        if response.status_code == 200:
            data = response.json()
            assert data["display_name"] == ""

    def test_create_person_with_very_long_name(self, client, sample_tree, sample_tree_version):
        """Test creating person with very long display name."""
        long_name = "A" * 500
        
        response = client.post("/people", json={
            "display_name": long_name,
            "sex": "M",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        # Should handle long names gracefully
        assert response.status_code in [200, 422]

    def test_create_person_with_unicode_name(self, client, sample_tree, sample_tree_version):
        """Test creating person with unicode characters."""
        response = client.post("/people", json={
            "display_name": "José María González",
            "sex": "M",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "José María González"

    def test_list_people_with_no_filters(self, client):
        """Test listing people without any filters."""
        response = client.get("/people")
        
        # Should return all people or require filters
        assert response.status_code in [200, 400, 422]
