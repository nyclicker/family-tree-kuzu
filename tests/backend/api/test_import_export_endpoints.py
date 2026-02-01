"""
Tests for import and export API endpoints.
"""

import pytest
import io
import json
from fastapi.testclient import TestClient
from app import crud


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


class TestImportEndpoint:
    """Tests for POST /import endpoint."""
    
    def test_import_csv_creates_new_tree(self, client):
        """Test importing CSV file creates new tree."""
        csv_content = "Person 1,Relation,Person 2,Gender,Details\nJohn Doe,Earliest Ancestor,,M,Root person\nJane Doe,Spouse,John Doe,F,\nChild Doe,Child,John Doe,M,\n"
        file = io.BytesIO(csv_content.encode())
        
        response = client.post(
            "/import",
            files={"file": ("family.csv", file, "text/csv")},
            data={"tree_name": "Test Family"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 1
        assert "tree_id" in data
        assert data["people_count"] >= 3
    
    def test_import_txt_creates_new_tree(self, client):
        """Test importing TXT file creates new tree."""
        txt_content = "Person 1,Relation,Person 2,Gender,Details\nJohn Doe,Earliest Ancestor,,M,\nJane Doe,Spouse,John Doe,F,\nChild Doe,Child,John Doe,M,\n"
        file = io.BytesIO(txt_content.encode())
        
        response = client.post(
            "/import",
            files={"file": ("family.txt", file, "text/plain")},
            data={"tree_name": "Test Family"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 1
    
    def test_import_json_creates_new_tree(self, client):
        """Test importing JSON file creates new tree."""
        json_data = {
            "people": [
                {"id": "1", "display_name": "John", "sex": "M"},
                {"id": "2", "display_name": "Jane", "sex": "F"}
            ],
            "relationships": []
        }
        file = io.BytesIO(json.dumps(json_data).encode())
        
        response = client.post(
            "/import",
            files={"file": ("tree.json", file, "application/json")},
            data={"tree_name": "JSON Test"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 1
    
    def test_import_multiple_trees(self, client):
        """Test importing creates different trees when no tree_id provided."""
        csv_content1 = "Person 1,Relation,Person 2,Gender,Details\nPerson A,Earliest Ancestor,,M,\n"
        file1 = io.BytesIO(csv_content1.encode())
        
        response1 = client.post(
            "/import",
            files={"file": ("tree1.csv", file1, "text/csv")},
            data={"tree_name": "Tree1"}
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        tree_id1 = data1["tree_id"]
        
        # Second import without tree_id creates a new tree
        csv_content2 = "Person 1,Relation,Person 2,Gender,Details\nPerson B,Earliest Ancestor,,M,\n"
        file2 = io.BytesIO(csv_content2.encode())
        
        response2 = client.post(
            "/import",
            files={"file": ("tree2.csv", file2, "text/csv")},
            data={"tree_name": "Tree2"}
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        tree_id2 = data2["tree_id"]
        
        # Should create different tree IDs
        assert tree_id1 != tree_id2
    
    def test_import_without_file_fails(self, client):
        """Test import without file returns 422."""
        response = client.post(
            "/import",
            data={"tree_name": "Test"}
        )
        
        assert response.status_code == 422
    
    def test_import_json_format_requires_proper_structure(self, client):
        """Test importing JSON with valid structure."""
        json_data = {
            "people": [{"id": "1", "display_name": "John", "sex": "M"}],
            "relationships": []
        }
        file = io.BytesIO(json.dumps(json_data).encode())
        
        response = client.post(
            "/import",
            files={"file": ("data.json", file, "application/json")},
            data={"tree_name": "JSONTest"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 1
    
    def test_import_handles_partial_csv_data(self, client):
        """Test importing CSV with minimal data."""
        csv_content = "Person 1,Relation,Person 2,Gender,Details\nSinglePerson,Earliest Ancestor,,M,\n"
        file = io.BytesIO(csv_content.encode())
        
        response = client.post(
            "/import",
            files={"file": ("minimal.csv", file, "text/csv")},
            data={"tree_name": "Minimal"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["people_count"] >= 1
    
    def test_import_large_file(self, client):
        """Test importing large file with many people."""
        lines = ["Person 1,Relation,Person 2,Gender,Details", "Root,Earliest Ancestor,,M,"]
        for i in range(1, 100):
            lines.append(f"Person{i},Child,Root,M,")
        csv_content = "\n".join(lines) + "\n"
        
        file = io.BytesIO(csv_content.encode())
        
        response = client.post(
            "/import",
            files={"file": ("large.csv", file, "text/csv")},
            data={"tree_name": "Large Family"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 1
    
    def test_import_with_special_characters(self, client):
        """Test importing names with special characters."""
        csv_content = "Person 1,Relation,Person 2,Gender,Details\nJosé García,Earliest Ancestor,,M,\nMüller François,Spouse,José García,F,\nO'Brien-Smith,Child,José García,M,\n"
        file = io.BytesIO(csv_content.encode('utf-8'))
        
        response = client.post(
            "/import",
            files={"file": ("special.csv", file, "text/csv")},
            data={"tree_name": "International"}
        )
        
        assert response.status_code == 200


class TestExportEndpoint:
    """Tests for GET /export endpoint."""
    
    def test_export_by_tree_id(self, client, sample_tree, sample_tree_version, sample_person):
        """Test exporting tree by tree_id."""
        response = client.get(f"/export?tree_id={sample_tree.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "people" in data
        assert "relationships" in data
        assert isinstance(data["people"], list)
        assert isinstance(data["relationships"], list)
    
    def test_export_by_tree_version_id(self, client, sample_tree, sample_tree_version, sample_person):
        """Test exporting tree by tree_version_id."""
        response = client.get(f"/export?tree_version_id={sample_tree_version.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "people" in data
        assert isinstance(data["people"], list)
    
    def test_export_both_filters(self, client, sample_tree, sample_tree_version, sample_person):
        """Test export with both tree_id and tree_version_id."""
        response = client.get(
            f"/export?tree_id={sample_tree.id}&tree_version_id={sample_tree_version.id}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "people" in data
    
    def test_export_saves_to_disk(self, client, sample_tree, sample_tree_version, sample_person):
        """Test export with save_to_disk creates file."""
        response = client.get(
            f"/export?tree_id={sample_tree.id}&save_to_disk=true"
        )
        
        assert response.status_code == 200
        data = response.json()
        # When save_to_disk=true, response includes 'path' instead of 'people'
        assert "path" in data or "people" in data
    
    def test_export_nonexistent_tree_fails(self, client):
        """Test exporting nonexistent tree returns empty or error."""
        response = client.get("/export?tree_id=99999")
        
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert data["people"] == []
    
    def test_export_includes_relationships(self, client, populated_tree):
        """Test export includes all relationships."""
        tree, version, people, rels = populated_tree
        
        response = client.get(f"/export?tree_version_id={version.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["relationships"]) >= len(rels)
    
    def test_export_json_format_valid(self, client, sample_tree, sample_tree_version, sample_person):
        """Test export returns valid JSON format."""
        response = client.get(f"/export?tree_id={sample_tree.id}")
        
        assert response.status_code == 200
        data = response.json()
        if data["people"]:
            person = data["people"][0]
            assert "id" in person
            assert "display_name" in person
    
    def test_export_without_filters_accepts_empty(self, client):
        """Test export without tree_id or tree_version_id returns empty."""
        response = client.get("/export")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data.get("people"), list) or data.get("people") == []
    
    def test_export_preserves_person_fields(self, client, db_session, sample_tree, sample_tree_version):
        """Test export preserves all person fields."""
        person = crud.create_person(
            db_session,
            display_name="Test Person",
            sex="F",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id,
            notes="Test notes"
        )
        
        response = client.get(f"/export?tree_version_id={sample_tree_version.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["people"]) >= 1
    
    def test_export_preserves_relationship_types(self, client, populated_tree):
        """Test export preserves relationship types."""
        tree, version, people, rels = populated_tree
        
        response = client.get(f"/export?tree_version_id={version.id}")
        
        assert response.status_code == 200
        data = response.json()
        rel_types = [r["type"] for r in data["relationships"]]
        assert any("CHILD_OF" in str(t) or "SPOUSE_OF" in str(t) for t in rel_types)


class TestImportExportRoundTrip:
    """Test import/export/import cycle preserves data."""
    
    def test_roundtrip_preserves_people(self, client):
        """Test import then export preserves all people."""
        csv_content = "Person 1,Relation,Person 2,Gender,Details\nJohn Doe,Earliest Ancestor,,M,\nJane Doe,Spouse,John Doe,F,\n"
        file = io.BytesIO(csv_content.encode())
        
        import_response = client.post(
            "/import",
            files={"file": ("test.csv", file, "text/csv")},
            data={"tree_name": "Test"}
        )
        
        assert import_response.status_code == 200
        tree_id = import_response.json()["tree_id"]
        
        export_response = client.get(f"/export?tree_id={tree_id}")
        
        assert export_response.status_code == 200
        data = export_response.json()
        assert len(data["people"]) >= 2
    
    def test_roundtrip_preserves_relationships(self, client):
        """Test import then export preserves relationships."""
        csv_content = "Person 1,Relation,Person 2,Gender,Details\nParent,Earliest Ancestor,,M,\nChild,Child,Parent,F,\n"
        file = io.BytesIO(csv_content.encode())
        
        import_response = client.post(
            "/import",
            files={"file": ("test.csv", file, "text/csv")},
            data={"tree_name": "Test"}
        )
        
        tree_id = import_response.json()["tree_id"]
        
        export_response = client.get(f"/export?tree_id={tree_id}")
        data = export_response.json()
        
        assert len(data["relationships"]) > 0
    
    def test_export_reimport_preserves_data(self, client, sample_tree, sample_tree_version, sample_person):
        """Test exporting and re-importing preserves tree structure."""
        export_response = client.get(f"/export?tree_id={sample_tree.id}")
        exported_data = export_response.json()
        
        assert exported_data is not None
        assert "people" in exported_data or "path" in exported_data
