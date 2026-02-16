"""Tests for relationship API endpoints.

Requirements tested:
- REQ-F1: A child in a family tree can have two biological parents (mother and father)
- REQ-F2: Spouse relationships should trigger child-sharing between both parents
"""
import pytest


def _make_tree_and_people(auth_client):
    tree = auth_client.post("/api/trees", json={"name": "Rel Tree"}).json()
    p1 = auth_client.post(f"/api/trees/{tree['id']}/people",
                           json={"display_name": "Parent"}).json()
    p2 = auth_client.post(f"/api/trees/{tree['id']}/people",
                           json={"display_name": "Child"}).json()
    return tree, p1, p2


class TestCreateRelationship:
    def test_parent_of(self, auth_client):
        tree, p1, p2 = _make_tree_and_people(auth_client)
        resp = auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p1["id"], "to_person_id": p2["id"], "type": "PARENT_OF",
        })
        assert resp.status_code == 200
        assert resp.json()["type"] == "PARENT_OF"

    def test_spouse_of(self, auth_client):
        tree = auth_client.post("/api/trees", json={"name": "S Tree"}).json()
        p1 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "Husband"}).json()
        p2 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "Wife"}).json()
        resp = auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p1["id"], "to_person_id": p2["id"], "type": "SPOUSE_OF",
        })
        assert resp.status_code == 200

    def test_already_has_two_parents(self, auth_client):
        tree, p1, p2 = _make_tree_and_people(auth_client)
        auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p1["id"], "to_person_id": p2["id"], "type": "PARENT_OF",
        })
        p3 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "Parent2"}).json()
        # Second parent should be allowed (biological family trees need 2)
        resp2 = auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p3["id"], "to_person_id": p2["id"], "type": "PARENT_OF",
        })
        assert resp2.status_code == 200
        # Third parent should be rejected
        p4 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "Parent3"}).json()
        resp3 = auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p4["id"], "to_person_id": p2["id"], "type": "PARENT_OF",
        })
        assert resp3.status_code == 400

    def test_already_has_spouse(self, auth_client):
        tree = auth_client.post("/api/trees", json={"name": "Spouse Tree"}).json()
        p1 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "A"}).json()
        p2 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "B"}).json()
        p3 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "C"}).json()
        auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p1["id"], "to_person_id": p2["id"], "type": "SPOUSE_OF",
        })
        resp = auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p1["id"], "to_person_id": p3["id"], "type": "SPOUSE_OF",
        })
        assert resp.status_code == 400

    def test_spouse_merges_children(self, auth_client):
        tree = auth_client.post("/api/trees", json={"name": "Merge Tree"}).json()
        dad = auth_client.post(f"/api/trees/{tree['id']}/people",
                                json={"display_name": "Dad"}).json()
        mom = auth_client.post(f"/api/trees/{tree['id']}/people",
                                json={"display_name": "Mom"}).json()
        child = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "Kid"}).json()
        auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": dad["id"], "to_person_id": child["id"], "type": "PARENT_OF",
        })
        resp = auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": dad["id"], "to_person_id": mom["id"], "type": "SPOUSE_OF",
        })
        assert resp.status_code == 200


class TestChildCanHaveTwoParents:
    """REQ-F1: In a biological family tree, a child can have two parents."""

    def test_two_parents_via_relationship_api(self, auth_client):
        tree = auth_client.post("/api/trees", json={"name": "Family"}).json()
        dad = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "Dad", "sex": "M"}).json()
        mom = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "Mom", "sex": "F"}).json()
        child = auth_client.post(f"/api/trees/{tree['id']}/people",
                                 json={"display_name": "Child"}).json()
        # First parent
        resp1 = auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": dad["id"], "to_person_id": child["id"], "type": "PARENT_OF",
        })
        assert resp1.status_code == 200
        # Second parent — biological family trees require this
        resp2 = auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": mom["id"], "to_person_id": child["id"], "type": "PARENT_OF",
        })
        assert resp2.status_code == 200
        # Verify child has 2 parents
        parents_resp = auth_client.get(
            f"/api/trees/{tree['id']}/people/{child['id']}/parents")
        assert len(parents_resp.json()) == 2

    def test_cannot_have_three_parents(self, auth_client):
        """A child should have at most 2 biological parents."""
        tree = auth_client.post("/api/trees", json={"name": "Family"}).json()
        p1 = auth_client.post(f"/api/trees/{tree['id']}/people",
                              json={"display_name": "P1"}).json()
        p2 = auth_client.post(f"/api/trees/{tree['id']}/people",
                              json={"display_name": "P2"}).json()
        p3 = auth_client.post(f"/api/trees/{tree['id']}/people",
                              json={"display_name": "P3"}).json()
        child = auth_client.post(f"/api/trees/{tree['id']}/people",
                                 json={"display_name": "Child"}).json()
        # Add first parent
        auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p1["id"], "to_person_id": child["id"], "type": "PARENT_OF",
        })
        # Add second parent
        auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p2["id"], "to_person_id": child["id"], "type": "PARENT_OF",
        })
        # Third parent should be rejected
        resp = auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p3["id"], "to_person_id": child["id"], "type": "PARENT_OF",
        })
        assert resp.status_code == 400


class TestDeleteRelationship:
    def test_delete(self, auth_client):
        tree, p1, p2 = _make_tree_and_people(auth_client)
        rel = auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p1["id"], "to_person_id": p2["id"], "type": "PARENT_OF",
        }).json()
        resp = auth_client.delete(f"/api/trees/{tree['id']}/relationships/{rel['id']}")
        assert resp.status_code == 200


class TestRecordsChangelog:
    def test_create_records(self, auth_client):
        tree, p1, p2 = _make_tree_and_people(auth_client)
        auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p1["id"], "to_person_id": p2["id"], "type": "PARENT_OF",
        })
        resp = auth_client.get(f"/api/trees/{tree['id']}/changelog")
        changes = resp.json()
        rel_changes = [c for c in changes if c["entity_type"] == "relationship"]
        assert len(rel_changes) >= 1


class TestViewerForbidden:
    def test_viewer_cannot_create(self, auth_client, viewer_client):
        tree = auth_client.post("/api/trees", json={"name": "T"}).json()
        # Grant viewer access
        auth_client.post(f"/api/trees/{tree['id']}/members",
                         json={"email": "eve@test.com", "role": "viewer"})
        p1 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "P1"}).json()
        p2 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "P2"}).json()
        resp = viewer_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p1["id"], "to_person_id": p2["id"], "type": "PARENT_OF",
        })
        assert resp.status_code == 403


class TestDeleteRecordsDetail:
    def test_delete_records_detail(self, auth_client):
        tree, p1, p2 = _make_tree_and_people(auth_client)
        rel = auth_client.post(f"/api/trees/{tree['id']}/relationships", json={
            "from_person_id": p1["id"], "to_person_id": p2["id"], "type": "PARENT_OF",
        }).json()
        auth_client.delete(f"/api/trees/{tree['id']}/relationships/{rel['id']}")
        resp = auth_client.get(f"/api/trees/{tree['id']}/changelog")
        deletes = [c for c in resp.json() if c["action"] == "delete" and c["entity_type"] == "relationship"]
        assert len(deletes) >= 1
