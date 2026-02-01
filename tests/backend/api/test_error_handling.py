"""
Error handling tests for main API endpoints.
"""

import pytest
import io
import json
from fastapi.testclient import TestClient


@pytest.fixture
def client(db_session):
    """Create FastAPI test client with database session override."""
    from app.main import app, get_db
    
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestImportErrorHandling:
    """Test error handling in POST /import endpoint."""

    def test_import_invalid_csv_gender(self, client):
        """Test import with invalid gender value fails gracefully."""
        csv_content = "Person 1,Relation,Person 2,Gender,Details\nJohn Doe,Earliest Ancestor,,X,Invalid gender\n"
        file = io.BytesIO(csv_content.encode())
        
        response = client.post(
            "/import",
            files={"file": ("bad.csv", file, "text/csv")},
            data={"tree_name": "BadGender"}
        )
        
        # Should return 400 with error message
        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data

    def test_import_missing_person1(self, client):
        """Test import with empty Person 1 column fails."""
        csv_content = "Person 1,Relation,Person 2,Gender,Details\n,Earliest Ancestor,,M,Missing name\n"
        file = io.BytesIO(csv_content.encode())
        
        response = client.post(
            "/import",
            files={"file": ("bad.csv", file, "text/csv")},
            data={"tree_name": "MissingPerson"}
        )
        
        assert response.status_code == 400

    def test_import_json_missing_people_key(self, client):
        """Test import with invalid JSON structure fails."""
        invalid_json = {"invalid_key": []}
        file = io.BytesIO(json.dumps(invalid_json).encode())
        
        response = client.post(
            "/import",
            files={"file": ("bad.json", file, "application/json")},
            data={"tree_name": "BadJSON"}
        )
        
        assert response.status_code == 400

    def test_import_json_not_dict(self, client):
        """Test import with JSON array at root fails."""
        invalid_json = [{"id": "1", "display_name": "John"}]
        file = io.BytesIO(json.dumps(invalid_json).encode())
        
        response = client.post(
            "/import",
            files={"file": ("bad.json", file, "application/json")},
            data={"tree_name": "BadJSON"}
        )
        
        assert response.status_code == 400

    def test_import_empty_file_accepts(self, client):
        """Test import with empty file (after header) succeeds but creates no people."""
        csv_content = "Person 1,Relation,Person 2,Gender,Details\n"
        file = io.BytesIO(csv_content.encode())
        
        response = client.post(
            "/import",
            files={"file": ("empty.csv", file, "text/csv")},
            data={"tree_name": "Empty"}
        )
        
        # Should succeed but with 0 people
        assert response.status_code == 200
        data = response.json()
        assert data["people_count"] == 0


class TestExportErrorHandling:
    """Test error handling in GET /export endpoint."""

    def test_export_nonexistent_tree_returns_empty(self, client):
        """Test export with invalid tree_id returns empty data."""
        response = client.get("/export?tree_id=99999")
        
        # Should return 200 with empty data rather than 404
        assert response.status_code == 200
        data = response.json()
        assert data["people"] == []

    def test_export_nonexistent_version_returns_empty(self, client):
        """Test export with invalid tree_version_id returns empty data."""
        response = client.get("/export?tree_version_id=99999")
        
        assert response.status_code == 200
        data = response.json()
        assert data["people"] == []

    def test_export_no_filters_returns_empty(self, client):
        """Test export without filters returns empty data."""
        response = client.get("/export")
        
        # Should not error, just return empty
        assert response.status_code == 200


class TestPersonErrorHandling:
    """Test error handling in /people endpoints."""

    def test_create_person_missing_display_name_fails(self, client, sample_tree, sample_tree_version):
        """Test creating person without display_name fails."""
        response = client.post(
            "/people",
            json={
                "tree_id": sample_tree.id,
                "tree_version_id": sample_tree_version.id,
                "sex": "M"
            }
        )
        
        # Should return 422 validation error
        assert response.status_code == 422

    def test_create_person_invalid_sex_fails(self, client, sample_tree, sample_tree_version):
        """Test creating person with invalid sex value fails."""
        response = client.post(
            "/people",
            json={
                "display_name": "Test",
                "tree_id": sample_tree.id,
                "tree_version_id": sample_tree_version.id,
                "sex": "InvalidSex"
            }
        )
        
        assert response.status_code == 422

    def test_get_person_not_found_returns_404(self, client):
        """Test getting non-existent person returns 404."""
        response = client.get("/people/99999")
        
        assert response.status_code == 404


class TestRelationshipErrorHandling:
    """Test error handling in /relationships endpoints."""

    def test_create_relationship_missing_from_person_fails(self, client, sample_tree, sample_tree_version):
        """Test creating relationship without from_person_id fails."""
        response = client.post(
            "/relationships",
            json={
                "type": "CHILD_OF",
                "to_person_id": "123",
                "tree_id": sample_tree.id,
                "tree_version_id": sample_tree_version.id
            }
        )
        
        assert response.status_code == 422

    def test_create_relationship_invalid_type_fails(self, client, sample_tree, sample_tree_version, sample_person):
        """Test creating relationship with invalid type fails."""
        response = client.post(
            "/relationships",
            json={
                "from_person_id": str(sample_person.id),
                "type": "INVALID_TYPE",
                "tree_id": sample_tree.id,
                "tree_version_id": sample_tree_version.id
            }
        )
        
        assert response.status_code == 422

    def test_create_earliest_ancestor_with_to_person_ignores(self, client, sample_tree, sample_tree_version, sample_person):
        """Test creating EARLIEST_ANCESTOR with to_person_id silently ignores it."""
        response = client.post(
            "/relationships",
            json={
                "from_person_id": str(sample_person.id),
                "to_person_id": str(sample_person.id),
                "type": "EARLIEST_ANCESTOR",
                "tree_id": sample_tree.id,
                "tree_version_id": sample_tree_version.id
            }
        )
        
        # Should succeed and silently set to_person_id to None
        assert response.status_code == 200
        data = response.json()
        assert data["to_person_id"] is None

    def test_create_child_of_without_to_person_fails(self, client, sample_tree, sample_tree_version, sample_person):
        """Test creating CHILD_OF without to_person_id fails validation."""
        response = client.post(
            "/relationships",
            json={
                "from_person_id": str(sample_person.id),
                "type": "CHILD_OF",
                "tree_id": sample_tree.id,
                "tree_version_id": sample_tree_version.id
            }
        )
        
        assert response.status_code == 422
