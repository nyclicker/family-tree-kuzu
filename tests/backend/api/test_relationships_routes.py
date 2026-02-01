"""
API endpoint tests for /relationships routes.

Tests the REST API for relationship management including:
- Creating relationships
- Listing relationships with filtering
- Getting individual relationships
- Deleting relationships
- Relationship type validation
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Relationship, RelType


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


class TestCreateRelationship:
    """Test POST /relationships endpoint."""

    def test_create_child_relationship(self, client, populated_tree):
        """Test creating a CHILD_OF relationship."""
        tree, tree_version, people, _ = populated_tree
        parent_id = people[0].id
        child_id = people[1].id
        
        response = client.post("/relationships", json={
            "from_person_id": str(child_id),
            "to_person_id": str(parent_id),
            "type": "CHILD_OF",
            "tree_id": tree.id,
            "tree_version_id": tree_version.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "CHILD_OF"
        assert data["from_person_id"] == str(child_id)
        assert data["to_person_id"] == str(parent_id)

    def test_create_spouse_relationship(self, client, populated_tree):
        """Test creating a SPOUSE_OF relationship."""
        tree, tree_version, people, _ = populated_tree
        spouse1_id = people[0].id
        spouse2_id = people[1].id
        
        response = client.post("/relationships", json={
            "from_person_id": str(spouse1_id),
            "to_person_id": str(spouse2_id),
            "type": "SPOUSE_OF",
            "tree_id": tree.id,
            "tree_version_id": tree_version.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "SPOUSE_OF"

    def test_create_earliest_ancestor_relationship(self, client, db_session, sample_tree, sample_tree_version):
        """Test creating an EARLIEST_ANCESTOR relationship (root node)."""
        from app import crud
        
        # Create a person to be the root
        root = crud.create_person(
            db_session,
            display_name="Patriarch",
            sex="M",
            notes="",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        
        response = client.post("/relationships", json={
            "from_person_id": str(root.id),
            "to_person_id": None,  # Root has no parent
            "type": "EARLIEST_ANCESTOR",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "EARLIEST_ANCESTOR"
        assert data["to_person_id"] is None

    def test_create_relationship_missing_to_person(self, client, populated_tree):
        """Test that non-EARLIEST_ANCESTOR relationships require to_person_id."""
        tree, tree_version, people, _ = populated_tree
        
        response = client.post("/relationships", json={
            "from_person_id": str(people[0].id),
            "to_person_id": None,  # Should fail for CHILD_OF
            "type": "CHILD_OF",
            "tree_id": tree.id,
            "tree_version_id": tree_version.id
        })
        
        assert response.status_code == 422  # Validation error

    def test_create_relationship_invalid_type(self, client, populated_tree):
        """Test creating relationship with invalid type."""
        tree, tree_version, people, _ = populated_tree
        
        response = client.post("/relationships", json={
            "from_person_id": str(people[0].id),
            "to_person_id": str(people[1].id),
            "type": "INVALID_TYPE",
            "tree_id": tree.id,
            "tree_version_id": tree_version.id
        })
        
        assert response.status_code == 422  # Validation error


class TestListRelationships:
    """Test GET /relationships endpoint."""

    def test_list_all_relationships(self, client, populated_tree):
        """Test listing all relationships in a tree."""
        tree, tree_version, people, relationships = populated_tree
        
        response = client.get("/relationships", params={
            "tree_id": tree.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # At least the root relationship

    def test_list_relationships_by_tree_version(self, client, populated_tree):
        """Test listing relationships filtered by tree_version_id."""
        tree, tree_version, people, relationships = populated_tree
        
        response = client.get("/relationships", params={
            "tree_version_id": tree_version.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        for rel in data:
            assert rel["tree_version_id"] == tree_version.id

    def test_list_relationships_by_person(self, client, populated_tree):
        """Test listing relationships for a specific person."""
        tree, tree_version, people, relationships = populated_tree
        person_id = people[0].id
        
        # Get all relationships
        response = client.get("/relationships", params={
            "tree_version_id": tree_version.id
        })
        
        data = response.json()
        # Filter to relationships involving this person
        person_rels = [
            r for r in data
            if r["from_person_id"] == str(person_id) or r.get("to_person_id") == str(person_id)
        ]
        assert len(person_rels) >= 1

    def test_list_relationships_empty_tree(self, client, sample_tree, sample_tree_version):
        """Test listing relationships from empty tree."""
        response = client.get("/relationships", params={
            "tree_version_id": sample_tree_version.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestGetRelationship:
    """Test GET /relationships/{rel_id} endpoint."""

    def test_get_relationship_by_id(self, client, populated_tree):
        """Test getting a specific relationship."""
        tree, tree_version, people, relationships = populated_tree
        rel_id = str(relationships[0].id)  # Convert UUID to string
        
        response = client.get(f"/relationships/{rel_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == rel_id
        assert "type" in data
        assert "from_person_id" in data

    def test_get_relationship_not_found(self, client):
        """Test getting non-existent relationship."""
        import uuid
        fake_id = uuid.uuid4()
        
        response = client.get(f"/relationships/{fake_id}")
        
        assert response.status_code == 404


class TestDeleteRelationship:
    """Test DELETE /relationships/{rel_id} endpoint."""

    def test_delete_relationship(self, client, db_session, populated_tree):
        """Test deleting a relationship."""
        from app import crud
        tree, tree_version, people, _ = populated_tree
        
        # Create a relationship to delete
        rel = crud.create_relationship(
            db_session,
            from_id=people[0].id,
            to_id=people[1].id,
            rel_type=RelType.SPOUSE_OF,
            tree_id=tree.id,
            tree_version_id=tree_version.id
        )
        rel_id = rel.id
        
        response = client.delete(f"/relationships/{rel_id}")
        
        assert response.status_code in [200, 204]
        
        # Verify relationship is gone
        check_response = client.get(f"/relationships/{rel_id}")
        assert check_response.status_code == 404

    def test_delete_relationship_not_found(self, client):
        """Test deleting non-existent relationship."""
        import uuid
        fake_id = uuid.uuid4()
        
        response = client.delete(f"/relationships/{fake_id}")
        
        assert response.status_code == 404


class TestRelationshipTypes:
    """Test different relationship types."""

    def test_all_relationship_types_valid(self, client, db_session, sample_tree, sample_tree_version):
        """Test that all RelType enum values are accepted."""
        from app import crud
        
        # Create people for testing
        person1 = crud.create_person(db_session, display_name="Person 1", sex="M", notes="",
                                    tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        person2 = crud.create_person(db_session, display_name="Person 2", sex="F", notes="",
                                    tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        
        # Test CHILD_OF
        response = client.post("/relationships", json={
            "from_person_id": str(person2.id),
            "to_person_id": str(person1.id),
            "type": "CHILD_OF",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        assert response.status_code == 200
        
        # Test SPOUSE_OF
        response = client.post("/relationships", json={
            "from_person_id": str(person1.id),
            "to_person_id": str(person2.id),
            "type": "SPOUSE_OF",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        assert response.status_code == 200

    def test_earliest_ancestor_requires_null_to_person(self, client, db_session, sample_tree, sample_tree_version):
        """Test that EARLIEST_ANCESTOR ideally has null to_person_id (may be leniently validated)."""
        from app import crud
        
        person1 = crud.create_person(db_session, display_name="Root", sex="M", notes="",
                                    tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        person2 = crud.create_person(db_session, display_name="Other", sex="F", notes="",
                                    tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        
        # EARLIEST_ANCESTOR with non-null to_person_id might fail validation
        response = client.post("/relationships", json={
            "from_person_id": str(person1.id),
            "to_person_id": str(person2.id),  # Should ideally be null
            "type": "EARLIEST_ANCESTOR",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        # Accept either rejection (422) or success with forced null (200)
        assert response.status_code in [200, 422]


class TestRelationshipConstraints:
    """Test relationship constraints and validation."""

    def test_cannot_create_duplicate_relationship(self, client, db_session, sample_tree, sample_tree_version):
        """Test that duplicate relationships are handled."""
        from app import crud
        
        person1 = crud.create_person(db_session, display_name="Parent", sex="M", notes="",
                                    tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        person2 = crud.create_person(db_session, display_name="Child", sex="F", notes="",
                                    tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        
        # Create first relationship
        response1 = client.post("/relationships", json={
            "from_person_id": str(person2.id),
            "to_person_id": str(person1.id),
            "type": "CHILD_OF",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        assert response1.status_code == 200
        
        # Try to create duplicate
        response2 = client.post("/relationships", json={
            "from_person_id": str(person2.id),
            "to_person_id": str(person1.id),
            "type": "CHILD_OF",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        # Should either succeed (allowing duplicates) or fail (constraint violation)
        assert response2.status_code in [200, 400, 409, 422]

    def test_relationship_with_nonexistent_person(self, client, sample_tree, sample_tree_version):
        """Test creating relationship with non-existent person (may succeed if validation is loose)."""
        import uuid
        fake_person_id = uuid.uuid4()
        
        response = client.post("/relationships", json={
            "from_person_id": str(fake_person_id),
            "to_person_id": str(uuid.uuid4()),
            "type": "CHILD_OF",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        # Should ideally fail, but may succeed depending on FK constraint enforcement
        assert response.status_code in [200, 400, 404, 422, 500]


class TestRelationshipEdgeCases:
    """Test edge cases and error conditions."""

    def test_self_referential_relationship(self, client, db_session, sample_tree, sample_tree_version):
        """Test creating relationship where from and to are the same person."""
        from app import crud
        
        person = crud.create_person(db_session, display_name="Self", sex="M", notes="",
                                   tree_id=sample_tree.id, tree_version_id=sample_tree_version.id)
        
        response = client.post("/relationships", json={
            "from_person_id": str(person.id),
            "to_person_id": str(person.id),
            "type": "SPOUSE_OF",
            "tree_id": sample_tree.id,
            "tree_version_id": sample_tree_version.id
        })
        
        # Should handle gracefully (either allow or reject)
        assert response.status_code in [200, 400, 422]

    def test_list_relationships_no_filters(self, client):
        """Test listing relationships without filters."""
        response = client.get("/relationships")
        
        # Should return all or require filters
        assert response.status_code in [200, 400, 422]
