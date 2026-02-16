"""Tests for person CRUD API endpoints.

Requirements tested:
- REQ-M1: Merging a person transfers ALL their data to the survivor, including comments
- REQ-P6: Death date implies deceased status (auto-set)
"""
import json


def _make_tree(auth_client, name="Test Tree"):
    return auth_client.post("/api/trees", json={"name": name}).json()


class TestListPeople:
    def test_list(self, auth_client):
        tree = _make_tree(auth_client)
        auth_client.post(f"/api/trees/{tree['id']}/people", json={"display_name": "A"})
        auth_client.post(f"/api/trees/{tree['id']}/people", json={"display_name": "B"})
        resp = auth_client.get(f"/api/trees/{tree['id']}/people")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestCreatePerson:
    def test_basic(self, auth_client):
        tree = _make_tree(auth_client)
        resp = auth_client.post(f"/api/trees/{tree['id']}/people",
                                json={"display_name": "New Person"})
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "New Person"

    def test_with_dates(self, auth_client):
        tree = _make_tree(auth_client)
        resp = auth_client.post(f"/api/trees/{tree['id']}/people", json={
            "display_name": "Dated", "birth_date": "1990-01-01",
            "death_date": "2020-12-31", "is_deceased": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["birth_date"] == "1990-01-01"
        assert data["is_deceased"] is True


class TestUpdatePerson:
    def test_normal(self, auth_client):
        tree = _make_tree(auth_client)
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "Old"}).json()
        resp = auth_client.put(f"/api/trees/{tree['id']}/people/{person['id']}",
                               json={"display_name": "New", "sex": "F"})
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "New"

    def test_not_found(self, auth_client):
        tree = _make_tree(auth_client)
        resp = auth_client.put(f"/api/trees/{tree['id']}/people/nonexistent",
                               json={"display_name": "X", "sex": "U"})
        assert resp.status_code == 404


class TestDeletePerson:
    def test_delete(self, auth_client):
        tree = _make_tree(auth_client)
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "Delete Me"}).json()
        resp = auth_client.delete(f"/api/trees/{tree['id']}/people/{person['id']}")
        assert resp.status_code == 200


class TestGetParents:
    def test_parents(self, auth_client):
        tree = _make_tree(auth_client)
        parent = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "Parent"}).json()
        child = auth_client.post(f"/api/trees/{tree['id']}/people",
                                 json={"display_name": "Child"}).json()
        auth_client.post(f"/api/trees/{tree['id']}/people/{child['id']}/set-parent",
                         json={"existing_person_id": parent["id"]})
        resp = auth_client.get(f"/api/trees/{tree['id']}/people/{child['id']}/parents")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestSetParent:
    def test_new_parent(self, auth_client):
        tree = _make_tree(auth_client)
        child = auth_client.post(f"/api/trees/{tree['id']}/people",
                                 json={"display_name": "Child"}).json()
        resp = auth_client.post(f"/api/trees/{tree['id']}/people/{child['id']}/set-parent",
                                json={"display_name": "New Parent", "sex": "M"})
        assert resp.status_code == 200
        assert resp.json()["parent"]["display_name"] == "New Parent"

    def test_existing_parent(self, auth_client):
        tree = _make_tree(auth_client)
        parent = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "Existing"}).json()
        child = auth_client.post(f"/api/trees/{tree['id']}/people",
                                 json={"display_name": "Child"}).json()
        resp = auth_client.post(f"/api/trees/{tree['id']}/people/{child['id']}/set-parent",
                                json={"existing_person_id": parent["id"]})
        assert resp.status_code == 200

    def test_self_reference(self, auth_client):
        tree = _make_tree(auth_client)
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "P"}).json()
        resp = auth_client.post(f"/api/trees/{tree['id']}/people/{person['id']}/set-parent",
                                json={"existing_person_id": person["id"]})
        assert resp.status_code == 400

    def test_replaces_existing(self, auth_client):
        tree = _make_tree(auth_client)
        old_parent = auth_client.post(f"/api/trees/{tree['id']}/people",
                                      json={"display_name": "OldP"}).json()
        child = auth_client.post(f"/api/trees/{tree['id']}/people",
                                 json={"display_name": "Child"}).json()
        auth_client.post(f"/api/trees/{tree['id']}/people/{child['id']}/set-parent",
                         json={"existing_person_id": old_parent["id"]})
        new_parent = auth_client.post(f"/api/trees/{tree['id']}/people",
                                      json={"display_name": "NewP"}).json()
        resp = auth_client.post(f"/api/trees/{tree['id']}/people/{child['id']}/set-parent",
                                json={"existing_person_id": new_parent["id"]})
        assert resp.status_code == 200
        assert "OldP" in resp.json()["removed_parents"]


class TestRelationshipCounts:
    def test_counts(self, auth_client):
        tree = _make_tree(auth_client)
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "P"}).json()
        resp = auth_client.get(f"/api/trees/{tree['id']}/people/{person['id']}/relationship-counts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parents"] == 0
        assert data["spouses"] == 0


class TestMergePerson:
    def test_normal(self, auth_client):
        tree = _make_tree(auth_client)
        p1 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "Keep"}).json()
        p2 = auth_client.post(f"/api/trees/{tree['id']}/people",
                               json={"display_name": "Remove"}).json()
        resp = auth_client.post(f"/api/trees/{tree['id']}/people/{p2['id']}/merge",
                                json={"merge_into_id": p1["id"]})
        assert resp.status_code == 200
        assert resp.json()["kept"] == "Keep"

    def test_self(self, auth_client):
        tree = _make_tree(auth_client)
        p = auth_client.post(f"/api/trees/{tree['id']}/people",
                              json={"display_name": "P"}).json()
        resp = auth_client.post(f"/api/trees/{tree['id']}/people/{p['id']}/merge",
                                json={"merge_into_id": p["id"]})
        assert resp.status_code == 400

    def test_not_found(self, auth_client):
        tree = _make_tree(auth_client)
        p = auth_client.post(f"/api/trees/{tree['id']}/people",
                              json={"display_name": "P"}).json()
        resp = auth_client.post(f"/api/trees/{tree['id']}/people/{p['id']}/merge",
                                json={"merge_into_id": "nonexistent"})
        assert resp.status_code == 404


class TestMergeTransfersComments:
    """REQ-M1: Merging a person transfers all their data including comments."""

    def test_comments_preserved_after_merge(self, auth_client):
        tree = _make_tree(auth_client)
        keep = auth_client.post(f"/api/trees/{tree['id']}/people",
                                json={"display_name": "Keep"}).json()
        remove = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "Remove"}).json()
        # Add comment on the person to be merged away
        auth_client.post(f"/api/trees/{tree['id']}/people/{remove['id']}/comments",
                         json={"content": "Important genealogy note"})
        # Merge remove into keep
        resp = auth_client.post(
            f"/api/trees/{tree['id']}/people/{remove['id']}/merge",
            json={"merge_into_id": keep["id"]})
        assert resp.status_code == 200
        # Comments should be transferred to the kept person
        comments_resp = auth_client.get(
            f"/api/trees/{tree['id']}/people/{keep['id']}/comments")
        comments = comments_resp.json()
        assert len(comments) == 1
        assert comments[0]["content"] == "Important genealogy note"

    def test_both_persons_comments_combined(self, auth_client):
        tree = _make_tree(auth_client)
        keep = auth_client.post(f"/api/trees/{tree['id']}/people",
                                json={"display_name": "Keep"}).json()
        remove = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "Remove"}).json()
        auth_client.post(f"/api/trees/{tree['id']}/people/{keep['id']}/comments",
                         json={"content": "Keep's note"})
        auth_client.post(f"/api/trees/{tree['id']}/people/{remove['id']}/comments",
                         json={"content": "Remove's note"})
        auth_client.post(
            f"/api/trees/{tree['id']}/people/{remove['id']}/merge",
            json={"merge_into_id": keep["id"]})
        comments_resp = auth_client.get(
            f"/api/trees/{tree['id']}/people/{keep['id']}/comments")
        comments = comments_resp.json()
        assert len(comments) == 2
        contents = {c["content"] for c in comments}
        assert contents == {"Keep's note", "Remove's note"}


class TestAutoDeceasedViaApi:
    """REQ-P6: Setting a death date should automatically mark the person as deceased."""

    def test_create_with_death_date(self, auth_client):
        tree = _make_tree(auth_client)
        resp = auth_client.post(f"/api/trees/{tree['id']}/people", json={
            "display_name": "Deceased", "death_date": "2020-01-01",
        })
        assert resp.status_code == 200
        assert resp.json()["is_deceased"] is True

    def test_update_adds_death_date(self, auth_client):
        tree = _make_tree(auth_client)
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "Alive"}).json()
        assert person["is_deceased"] is False
        resp = auth_client.put(
            f"/api/trees/{tree['id']}/people/{person['id']}",
            json={"display_name": "Alive", "sex": "U", "death_date": "2020-01-01"})
        assert resp.status_code == 200
        assert resp.json()["is_deceased"] is True


class TestComments:
    def test_list(self, auth_client):
        tree = _make_tree(auth_client)
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "P"}).json()
        resp = auth_client.get(f"/api/trees/{tree['id']}/people/{person['id']}/comments")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create(self, auth_client):
        tree = _make_tree(auth_client)
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "P"}).json()
        resp = auth_client.post(f"/api/trees/{tree['id']}/people/{person['id']}/comments",
                                json={"content": "Hello"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "Hello"

    def test_delete(self, auth_client):
        tree = _make_tree(auth_client)
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "P"}).json()
        comment = auth_client.post(f"/api/trees/{tree['id']}/people/{person['id']}/comments",
                                   json={"content": "Delete me"}).json()
        resp = auth_client.delete(
            f"/api/trees/{tree['id']}/people/{person['id']}/comments/{comment['id']}"
        )
        assert resp.status_code == 200

    def test_editor_can_delete_others_comment(self, auth_client, make_authenticated_client):
        """Editors can delete any comment — consistent with their ability to delete the person."""
        tree = _make_tree(auth_client)
        person = auth_client.post(f"/api/trees/{tree['id']}/people",
                                  json={"display_name": "P"}).json()
        comment = auth_client.post(f"/api/trees/{tree['id']}/people/{person['id']}/comments",
                                   json={"content": "Mine"}).json()
        bob = make_authenticated_client("bob2@test.com", "Bob", "password123")
        auth_client.post(f"/api/trees/{tree['id']}/members",
                         json={"email": "bob2@test.com", "role": "editor"})
        resp = bob.delete(
            f"/api/trees/{tree['id']}/people/{person['id']}/comments/{comment['id']}"
        )
        assert resp.status_code == 200


class TestCreateRecordsChangelog:
    def test_records(self, auth_client):
        tree = _make_tree(auth_client)
        auth_client.post(f"/api/trees/{tree['id']}/people",
                         json={"display_name": "Logged"})
        resp = auth_client.get(f"/api/trees/{tree['id']}/changelog")
        assert any(c["action"] == "create" for c in resp.json())
