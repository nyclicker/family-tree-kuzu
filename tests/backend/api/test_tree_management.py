"""
Tests for tree management endpoints.
"""

import pytest
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


class TestImportTreeEndpoint:
    """Test POST /trees/import endpoint."""

    def test_import_tree_creates_new_tree_and_version(self, client):
        """Test importing creates a new tree with version 1."""
        response = client.post(
            "/trees/import",
            json={
                "name": "NewTree",
                "source_filename": "source.txt"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "tree_id" in data
        assert "tree_version_id" in data
        assert data["version"] == 1

    def test_import_tree_with_existing_tree_id_increments_version(self, client, sample_tree, sample_tree_version):
        """Test importing with existing tree_id creates version 2."""
        response = client.post(
            "/trees/import",
            json={
                "name": "UpdatedTree",
                "source_filename": "source2.txt",
                "tree_id": sample_tree.id
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["tree_id"] == sample_tree.id
        assert data["version"] == 2

    def test_import_tree_without_name_uses_source_filename(self, client):
        """Test importing without name uses source_filename."""
        response = client.post(
            "/trees/import",
            json={
                "source_filename": "family.txt"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["tree_id"] is not None

    def test_import_tree_invalid_tree_id_raises_value_error(self, client):
        """Test importing with non-existent tree_id raises ValueError (returns 500)."""
        # The endpoint doesn't catch ValueError, so exception propagates
        with pytest.raises(ValueError, match="Tree id 99999 not found"):
            client.post(
                "/trees/import",
                json={
                    "name": "Test",
                    "tree_id": 99999
                }
            )


class TestListTreesEndpoint:
    """Test GET /trees endpoint."""

    def test_list_trees_empty(self, client):
        """Test listing trees when database is empty."""
        response = client.get("/trees")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_trees_returns_all_trees(self, client, sample_tree):
        """Test listing returns all trees."""
        response = client.get("/trees")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_tree.id
        assert data[0]["name"] == sample_tree.name

    def test_list_trees_includes_active_version_id(self, client, sample_tree, sample_tree_version):
        """Test listing includes active_version_id."""
        response = client.get("/trees")
        
        assert response.status_code == 200
        data = response.json()
        assert data[0]["active_version_id"] == sample_tree_version.id

    def test_list_trees_includes_metadata(self, client, sample_tree):
        """Test listing includes description and created_at."""
        response = client.get("/trees")
        
        assert response.status_code == 200
        data = response.json()
        tree = data[0]
        assert "description" in tree
        assert "created_at" in tree

    def test_list_trees_multiple(self, client, db_session):
        """Test listing multiple trees."""
        from app.models import Tree
        
        # Create multiple trees via test database session
        tree1 = Tree(name="Tree1", description="First")
        tree2 = Tree(name="Tree2", description="Second")
        db_session.add_all([tree1, tree2])
        db_session.commit()
        
        response = client.get("/trees")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestListTreeVersionsEndpoint:
    """Test GET /trees/{tree_id}/versions endpoint."""

    def test_list_versions_for_tree(self, client, sample_tree, sample_tree_version):
        """Test listing versions for a tree."""
        response = client.get(f"/trees/{sample_tree.id}/versions")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_tree_version.id
        assert data[0]["version"] == 1
        assert data[0]["active"] is True

    def test_list_versions_multiple(self, client, sample_tree, sample_tree_version, db_session):
        """Test listing multiple versions for a tree."""
        from app.models import TreeVersion
        
        # Create second version
        v2 = TreeVersion(
            tree_id=sample_tree.id,
            version=2,
            source_filename="v2.txt",
            active=False
        )
        db_session.add(v2)
        db_session.commit()
        
        response = client.get(f"/trees/{sample_tree.id}/versions")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["version"] == 1  # Ordered by version asc
        assert data[1]["version"] == 2

    def test_list_versions_includes_metadata(self, client, sample_tree, sample_tree_version):
        """Test listing versions includes all metadata."""
        response = client.get(f"/trees/{sample_tree.id}/versions")
        
        assert response.status_code == 200
        data = response.json()
        version = data[0]
        assert "id" in version
        assert "tree_id" in version
        assert "version" in version
        assert "source_filename" in version
        assert "created_at" in version
        assert "active" in version

    def test_list_versions_empty_tree(self, client, sample_tree):
        """Test listing versions for tree with no versions."""
        response = client.get(f"/trees/{sample_tree.id}/versions")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestUpdateTreeEndpoint:
    """Test PATCH /trees/{tree_id} endpoint."""

    def test_update_tree_name(self, client, sample_tree):
        """Test updating tree name."""
        response = client.patch(
            f"/trees/{sample_tree.id}",
            json={"name": "Updated Name"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_update_tree_description(self, client, sample_tree):
        """Test updating tree description."""
        response = client.patch(
            f"/trees/{sample_tree.id}",
            json={"description": "New description"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "New description"

    def test_update_tree_both_fields(self, client, sample_tree):
        """Test updating both name and description."""
        response = client.patch(
            f"/trees/{sample_tree.id}",
            json={
                "name": "Updated Name",
                "description": "Updated Description"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated Description"

    def test_update_tree_not_found(self, client):
        """Test updating non-existent tree returns 404."""
        response = client.patch(
            "/trees/99999",
            json={"name": "Test"}
        )
        
        assert response.status_code == 404

    def test_update_tree_persists(self, client, sample_tree):
        """Test update persists to database."""
        client.patch(
            f"/trees/{sample_tree.id}",
            json={"name": "Persistent Name"}
        )
        
        # Verify with GET request
        trees = client.get("/trees").json()
        tree = next(t for t in trees if t["id"] == sample_tree.id)
        assert tree["name"] == "Persistent Name"


class TestDraftEndpoints:
    """Test draft management endpoints."""

    def test_create_draft_person(self, client, sample_tree, sample_tree_version):
        """Test creating a draft person change."""
        response = client.post(
            f"/trees/{sample_tree.id}/versions/{sample_tree_version.id}/drafts",
            json={
                "change_type": "person",
                "payload": {"display_name": "Draft Person", "sex": "M"}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["change_type"] == "person"
        assert data["payload"]["display_name"] == "Draft Person"

    def test_create_draft_relationship(self, client, sample_tree, sample_tree_version):
        """Test creating a draft relationship change."""
        response = client.post(
            f"/trees/{sample_tree.id}/versions/{sample_tree_version.id}/drafts",
            json={
                "change_type": "relationship",
                "payload": {"from_person_id": "1", "type": "CHILD_OF"}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["change_type"] == "relationship"

    def test_list_drafts_empty(self, client, sample_tree, sample_tree_version):
        """Test listing drafts when none exist."""
        response = client.get(
            f"/trees/{sample_tree.id}/versions/{sample_tree_version.id}/drafts"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_list_drafts_returns_all(self, client, sample_tree, sample_tree_version, db_session):
        """Test listing returns all drafts for a version."""
        from app.models import WorkingChange
        
        draft1 = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "Draft1"}
        )
        draft2 = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "Draft2"}
        )
        db_session.add_all([draft1, draft2])
        db_session.commit()
        
        response = client.get(
            f"/trees/{sample_tree.id}/versions/{sample_tree_version.id}/drafts"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_delete_single_draft(self, client, sample_tree, sample_tree_version, db_session):
        """Test deleting a single draft."""
        from app.models import WorkingChange
        
        draft = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "ToDelete"}
        )
        db_session.add(draft)
        db_session.commit()
        draft_id = draft.id
        
        response = client.delete(
            f"/trees/{sample_tree.id}/versions/{sample_tree_version.id}/drafts/{draft_id}"
        )
        
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_delete_all_drafts(self, client, sample_tree, sample_tree_version, db_session):
        """Test deleting all drafts for a version."""
        from app.models import WorkingChange
        
        draft1 = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "Draft1"}
        )
        draft2 = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "Draft2"}
        )
        db_session.add_all([draft1, draft2])
        db_session.commit()
        
        response = client.delete(
            f"/trees/{sample_tree.id}/versions/{sample_tree_version.id}/drafts"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 2

    def test_publish_drafts_creates_new_version(self, client, sample_tree, sample_tree_version, db_session):
        """Test publishing drafts creates a new tree version."""
        from app.models import WorkingChange
        
        draft = WorkingChange(
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id,
            change_type="person",
            payload={"display_name": "NewPerson", "sex": "M"}
        )
        db_session.add(draft)
        db_session.commit()
        
        response = client.post(
            f"/trees/{sample_tree.id}/versions/{sample_tree_version.id}/publish"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["tree_id"] == sample_tree.id
        assert data["version"] == 2


class TestGraphEndpoint:
    """Test GET /api/plotly endpoint."""

    def test_get_plotly_by_tree_id(self, client, sample_tree, sample_tree_version, sample_person):
        """Test getting Plotly figure by tree_id."""
        response = client.get(f"/api/plotly?tree_id={sample_tree.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "layout" in data

    def test_get_plotly_by_tree_version_id(self, client, sample_tree, sample_tree_version, sample_person):
        """Test getting Plotly figure by tree_version_id."""
        response = client.get(f"/api/plotly?tree_version_id={sample_tree_version.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_plotly_both_filters(self, client, sample_tree, sample_tree_version):
        """Test getting Plotly figure with both filters provided."""
        # tree_version_id takes precedence over tree_id
        response = client.get(
            f"/api/plotly?tree_id={sample_tree.id}&tree_version_id={sample_tree_version.id}"
        )
        
        assert response.status_code == 200

    def test_get_plotly_empty_tree(self, client, sample_tree, sample_tree_version):
        """Test getting Plotly figure for empty tree."""
        response = client.get(f"/api/plotly?tree_id={sample_tree.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_get_plotly_without_filters(self, client):
        """Test getting Plotly figure without filters returns empty."""
        response = client.get("/api/plotly")
        
        assert response.status_code == 200


class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_returns_ok(self, client):
        """Test health endpoint returns ok status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
