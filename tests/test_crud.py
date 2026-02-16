"""Tests for app/crud.py — person/rel CRUD, merge, comments.

Requirements tested:
- REQ-P1: Every person belongs to exactly one tree
- REQ-P2: Deleting a person removes ALL associated data (edges, comments)
- REQ-P3: Merging two people transfers ALL data to the survivor (edges, properties, comments)
- REQ-P4: A person can have 0, 1, or 2 biological parents
- REQ-P5: Spouse relationships are symmetric (A spouse B == B spouse A)
- REQ-P6: Death date implies deceased status
- REQ-P7: People are listed alphabetically within a tree
- REQ-P8: Tree isolation — operations on one tree never affect another
"""
import pytest
from app import crud


# ── Person CRUD ──

class TestCreatePerson:
    def test_defaults(self, conn, tree_one):
        p = crud.create_person(conn, "Test Person", tree_id=tree_one["id"])
        assert p["display_name"] == "Test Person"
        assert p["sex"] == "U"
        assert p["is_deceased"] is False

    def test_all_fields(self, conn, tree_one):
        p = crud.create_person(
            conn, "Full Person", sex="F", notes="Some notes",
            dataset="ds", tree_id=tree_one["id"],
            birth_date="1990-01-15", death_date="2020-06-01", is_deceased=True,
        )
        assert p["sex"] == "F"
        assert p["notes"] == "Some notes"
        assert p["birth_date"] == "1990-01-15"
        assert p["death_date"] == "2020-06-01"
        assert p["is_deceased"] is True

    def test_auto_deceased_when_death_date(self, conn, tree_one):
        p = crud.create_person(
            conn, "Deceased", tree_id=tree_one["id"], death_date="2020-01-01"
        )
        assert p["is_deceased"] is True


class TestListPeople:
    def test_empty(self, conn, tree_one):
        people = crud.list_people(conn, tree_id=tree_one["id"])
        assert people == []

    def test_ordered(self, conn, tree_one):
        crud.create_person(conn, "Zara", tree_id=tree_one["id"])
        crud.create_person(conn, "Alice", tree_id=tree_one["id"])
        people = crud.list_people(conn, tree_id=tree_one["id"])
        assert len(people) == 2
        assert people[0]["display_name"] == "Alice"
        assert people[1]["display_name"] == "Zara"

    def test_filtered_by_tree(self, conn, tree_one, tree_two):
        crud.create_person(conn, "InTree1", tree_id=tree_one["id"])
        crud.create_person(conn, "InTree2", tree_id=tree_two["id"])
        t1_people = crud.list_people(conn, tree_id=tree_one["id"])
        assert len(t1_people) == 1
        assert t1_people[0]["display_name"] == "InTree1"


class TestGetPerson:
    def test_found(self, conn, person_grandpa, tree_one):
        p = crud.get_person(conn, person_grandpa["id"], tree_id=tree_one["id"])
        assert p is not None
        assert p["display_name"] == "Grandpa"

    def test_not_found(self, conn, tree_one):
        assert crud.get_person(conn, "nonexistent", tree_id=tree_one["id"]) is None

    def test_wrong_tree(self, conn, tree_one, tree_two, person_grandpa):
        assert crud.get_person(conn, person_grandpa["id"], tree_id=tree_two["id"]) is None


class TestUpdatePerson:
    def test_normal(self, conn, person_grandpa, tree_one):
        result = crud.update_person(
            conn, person_grandpa["id"], "Grandpa Updated", "M",
            notes="Updated notes", tree_id=tree_one["id"],
        )
        assert result is not None
        assert result["display_name"] == "Grandpa Updated"
        assert result["notes"] == "Updated notes"

    def test_not_found(self, conn, tree_one):
        result = crud.update_person(conn, "nonexistent", "Name", "U", tree_id=tree_one["id"])
        assert result is None

    def test_auto_deceased(self, conn, person_grandpa, tree_one):
        result = crud.update_person(
            conn, person_grandpa["id"], "Grandpa", "M",
            tree_id=tree_one["id"], death_date="2020-01-01",
        )
        assert result["is_deceased"] is True


class TestDeletePerson:
    def test_normal(self, conn, person_grandpa, tree_one):
        crud.delete_person(conn, person_grandpa["id"], tree_id=tree_one["id"])
        assert crud.get_person(conn, person_grandpa["id"]) is None

    def test_cascades_comments(self, conn, person_grandpa, tree_one, user_alice):
        c = crud.create_comment(
            conn, person_grandpa["id"], tree_one["id"],
            user_alice["id"], "Alice", "Test comment",
        )
        crud.delete_person(conn, person_grandpa["id"], tree_id=tree_one["id"])
        assert crud.get_comment(conn, c["id"]) is None

    def test_wrong_tree(self, conn, person_grandpa, tree_two):
        crud.delete_person(conn, person_grandpa["id"], tree_id=tree_two["id"])
        # Person should still exist — wrong tree
        assert crud.get_person(conn, person_grandpa["id"]) is not None


class TestFindPersonByName:
    def test_found(self, conn, person_grandpa, tree_one):
        p = crud.find_person_by_name(conn, "Grandpa", tree_id=tree_one["id"])
        assert p is not None
        assert p["id"] == person_grandpa["id"]

    def test_not_found(self, conn, tree_one):
        assert crud.find_person_by_name(conn, "Nobody", tree_id=tree_one["id"]) is None


# ── Relationships ──

class TestCreateRelationship:
    def test_parent(self, conn, person_grandpa, person_dad):
        rel = crud.create_relationship(conn, person_grandpa["id"], person_dad["id"], "PARENT_OF")
        assert rel["type"] == "PARENT_OF"
        assert rel["from_person_id"] == person_grandpa["id"]
        assert rel["to_person_id"] == person_dad["id"]

    def test_spouse(self, conn, person_dad, person_mom):
        rel = crud.create_relationship(conn, person_dad["id"], person_mom["id"], "SPOUSE_OF")
        assert rel["type"] == "SPOUSE_OF"

    def test_invalid_type(self, conn, person_grandpa, person_dad):
        with pytest.raises(ValueError, match="Invalid relationship"):
            crud.create_relationship(conn, person_grandpa["id"], person_dad["id"], "FRIEND_OF")


class TestGetRelationshipDetail:
    def test_found(self, conn, person_grandpa, person_dad):
        rel = crud.create_relationship(conn, person_grandpa["id"], person_dad["id"], "PARENT_OF")
        detail = crud.get_relationship_detail(conn, rel["id"])
        assert detail is not None
        assert detail["type"] == "PARENT_OF"
        assert detail["from_name"] == "Grandpa"
        assert detail["to_name"] == "Dad"

    def test_not_found(self, conn):
        assert crud.get_relationship_detail(conn, "nonexistent-rel") is None


class TestDeleteRelationship:
    def test_delete(self, conn, person_grandpa, person_dad):
        rel = crud.create_relationship(conn, person_grandpa["id"], person_dad["id"], "PARENT_OF")
        crud.delete_relationship(conn, rel["id"])
        assert crud.get_relationship_detail(conn, rel["id"]) is None


class TestEdgeExists:
    def test_true(self, conn, person_grandpa, person_dad):
        crud.create_relationship(conn, person_grandpa["id"], person_dad["id"], "PARENT_OF")
        assert crud._edge_exists(conn, person_grandpa["id"], person_dad["id"], "PARENT_OF") is True

    def test_false(self, conn, person_grandpa, person_dad):
        assert crud._edge_exists(conn, person_grandpa["id"], person_dad["id"], "PARENT_OF") is False

    def test_symmetric_spouse(self, conn, person_dad, person_mom):
        crud.create_relationship(conn, person_dad["id"], person_mom["id"], "SPOUSE_OF")
        # Check reverse direction
        assert crud._edge_exists(conn, person_mom["id"], person_dad["id"], "SPOUSE_OF") is True


# ── Family traversal ──

class TestFamilyTraversal:
    def test_get_children(self, conn, family_graph):
        children = crud.get_children(conn, family_graph["dad"]["id"])
        assert len(children) == 1
        assert children[0]["display_name"] == "Child"

    def test_get_parents(self, conn, family_graph):
        parents = crud.get_parents(conn, family_graph["child"]["id"])
        assert len(parents) == 2
        names = {p["display_name"] for p in parents}
        assert names == {"Dad", "Mom"}

    def test_delete_parent_rel(self, conn, family_graph):
        crud.delete_parent_relationship(
            conn, family_graph["dad"]["id"], family_graph["child"]["id"]
        )
        parents = crud.get_parents(conn, family_graph["child"]["id"])
        assert len(parents) == 1
        assert parents[0]["display_name"] == "Mom"

    def test_count_parents(self, conn, family_graph):
        assert crud.count_parents(conn, family_graph["child"]["id"]) == 2

    def test_count_spouses(self, conn, family_graph):
        assert crud.count_spouses(conn, family_graph["dad"]["id"]) == 1


# ── Merge ──

class TestMergePersonTransfersComments:
    """REQ-P3: Merging two people transfers ALL data to the survivor, including comments."""

    def test_comments_transferred_to_survivor(self, conn, tree_one, user_alice):
        keep = crud.create_person(conn, "Keep", tree_id=tree_one["id"])
        remove = crud.create_person(conn, "Remove", tree_id=tree_one["id"])
        crud.create_comment(
            conn, remove["id"], tree_one["id"],
            user_alice["id"], "Alice", "Important genealogy note",
        )
        crud.merge_person_into(conn, keep["id"], remove["id"])
        # REQ: All data from the removed person should transfer to the survivor
        comments = crud.list_comments(conn, keep["id"], tree_one["id"])
        assert len(comments) == 1
        assert comments[0]["content"] == "Important genealogy note"

    def test_multiple_comments_transferred(self, conn, tree_one, user_alice):
        keep = crud.create_person(conn, "Keep", tree_id=tree_one["id"])
        remove = crud.create_person(conn, "Remove", tree_id=tree_one["id"])
        crud.create_comment(conn, remove["id"], tree_one["id"],
                            user_alice["id"], "Alice", "Note 1")
        crud.create_comment(conn, remove["id"], tree_one["id"],
                            user_alice["id"], "Alice", "Note 2")
        crud.create_comment(conn, keep["id"], tree_one["id"],
                            user_alice["id"], "Alice", "Existing note")
        crud.merge_person_into(conn, keep["id"], remove["id"])
        comments = crud.list_comments(conn, keep["id"], tree_one["id"])
        assert len(comments) == 3

    def test_comments_not_lost(self, conn, tree_one, user_alice):
        """REQ: After merge, no comments should be orphaned or deleted."""
        keep = crud.create_person(conn, "Keep", tree_id=tree_one["id"])
        remove = crud.create_person(conn, "Remove", tree_id=tree_one["id"])
        c = crud.create_comment(conn, remove["id"], tree_one["id"],
                                user_alice["id"], "Alice", "Must survive merge")
        crud.merge_person_into(conn, keep["id"], remove["id"])
        # The comment should still exist in the system
        fetched = crud.get_comment(conn, c["id"])
        assert fetched is not None


class TestMergePersonInto:
    def test_transfers_outgoing_edges(self, conn, tree_one):
        a = crud.create_person(conn, "Keep", tree_id=tree_one["id"])
        b = crud.create_person(conn, "Remove", sex="F", notes="B notes", tree_id=tree_one["id"])
        c = crud.create_person(conn, "Child", tree_id=tree_one["id"])
        crud.create_relationship(conn, b["id"], c["id"], "PARENT_OF")
        crud.merge_person_into(conn, a["id"], b["id"])
        # a should now be parent of c
        children = crud.get_children(conn, a["id"])
        assert len(children) == 1
        assert children[0]["id"] == c["id"]
        # b should be gone
        assert crud.get_person(conn, b["id"]) is None

    def test_transfers_incoming_edges(self, conn, tree_one):
        parent = crud.create_person(conn, "Parent", tree_id=tree_one["id"])
        keep = crud.create_person(conn, "Keep", tree_id=tree_one["id"])
        remove = crud.create_person(conn, "Remove", tree_id=tree_one["id"])
        crud.create_relationship(conn, parent["id"], remove["id"], "PARENT_OF")
        crud.merge_person_into(conn, keep["id"], remove["id"])
        parents = crud.get_parents(conn, keep["id"])
        assert len(parents) == 1
        assert parents[0]["id"] == parent["id"]

    def test_inherits_sex_and_notes(self, conn, tree_one):
        keep = crud.create_person(conn, "Keep", sex="U", tree_id=tree_one["id"])
        remove = crud.create_person(conn, "Remove", sex="F", notes="Important", tree_id=tree_one["id"])
        crud.merge_person_into(conn, keep["id"], remove["id"])
        updated = crud.get_person(conn, keep["id"])
        assert updated["sex"] == "F"
        assert updated["notes"] == "Important"


class TestPersonCanHaveTwoParents:
    """REQ-P4: A person can have 0, 1, or 2 biological parents."""

    def test_two_parents(self, conn, tree_one):
        dad = crud.create_person(conn, "Dad", "M", tree_id=tree_one["id"])
        mom = crud.create_person(conn, "Mom", "F", tree_id=tree_one["id"])
        child = crud.create_person(conn, "Child", tree_id=tree_one["id"])
        crud.create_relationship(conn, dad["id"], child["id"], "PARENT_OF")
        crud.create_relationship(conn, mom["id"], child["id"], "PARENT_OF")
        parents = crud.get_parents(conn, child["id"])
        assert len(parents) == 2
        parent_names = {p["display_name"] for p in parents}
        assert parent_names == {"Dad", "Mom"}

    def test_zero_parents(self, conn, tree_one):
        person = crud.create_person(conn, "Orphan", tree_id=tree_one["id"])
        parents = crud.get_parents(conn, person["id"])
        assert len(parents) == 0

    def test_one_parent(self, conn, tree_one):
        parent = crud.create_person(conn, "Parent", tree_id=tree_one["id"])
        child = crud.create_person(conn, "Child", tree_id=tree_one["id"])
        crud.create_relationship(conn, parent["id"], child["id"], "PARENT_OF")
        parents = crud.get_parents(conn, child["id"])
        assert len(parents) == 1


class TestMergeSpouseChildren:
    def test_common_names(self, conn, tree_one):
        dad = crud.create_person(conn, "Dad", "M", tree_id=tree_one["id"])
        mom = crud.create_person(conn, "Mom", "F", tree_id=tree_one["id"])
        child_a = crud.create_person(conn, "SharedChild", tree_id=tree_one["id"])
        child_b = crud.create_person(conn, "SharedChild", tree_id=tree_one["id"])
        crud.create_relationship(conn, dad["id"], child_a["id"], "PARENT_OF")
        crud.create_relationship(conn, mom["id"], child_b["id"], "PARENT_OF")
        result = crud.merge_spouse_children(conn, dad["id"], mom["id"])
        assert len(result["merged"]) == 1
        assert result["merged"][0]["name"] == "SharedChild"

    def test_unique_children(self, conn, tree_one):
        dad = crud.create_person(conn, "Dad", "M", tree_id=tree_one["id"])
        mom = crud.create_person(conn, "Mom", "F", tree_id=tree_one["id"])
        child_a = crud.create_person(conn, "OnlyDadChild", tree_id=tree_one["id"])
        child_b = crud.create_person(conn, "OnlyMomChild", tree_id=tree_one["id"])
        crud.create_relationship(conn, dad["id"], child_a["id"], "PARENT_OF")
        crud.create_relationship(conn, mom["id"], child_b["id"], "PARENT_OF")
        result = crud.merge_spouse_children(conn, dad["id"], mom["id"])
        assert "OnlyMomChild" in result["shared_with_a"]
        assert "OnlyDadChild" in result["shared_with_b"]


# ── Comments ──

class TestComments:
    def test_create_and_list(self, conn, person_grandpa, tree_one, user_alice):
        c = crud.create_comment(
            conn, person_grandpa["id"], tree_one["id"],
            user_alice["id"], "Alice", "A comment",
        )
        assert c["content"] == "A comment"
        comments = crud.list_comments(conn, person_grandpa["id"], tree_one["id"])
        assert len(comments) == 1
        assert comments[0]["id"] == c["id"]

    def test_get(self, conn, person_grandpa, tree_one, user_alice):
        c = crud.create_comment(
            conn, person_grandpa["id"], tree_one["id"],
            user_alice["id"], "Alice", "Get test",
        )
        fetched = crud.get_comment(conn, c["id"])
        assert fetched is not None
        assert fetched["content"] == "Get test"

    def test_delete(self, conn, person_grandpa, tree_one, user_alice):
        c = crud.create_comment(
            conn, person_grandpa["id"], tree_one["id"],
            user_alice["id"], "Alice", "Delete me",
        )
        crud.delete_comment(conn, c["id"])
        assert crud.get_comment(conn, c["id"]) is None


# ── clear_all ──

class TestClearAll:
    def test_global(self, conn, person_grandpa):
        crud.clear_all(conn)
        assert crud.list_people(conn) == []

    def test_by_tree(self, conn, tree_one, tree_two):
        crud.create_person(conn, "T1Person", tree_id=tree_one["id"])
        crud.create_person(conn, "T2Person", tree_id=tree_two["id"])
        crud.clear_all(conn, tree_id=tree_one["id"])
        assert len(crud.list_people(conn, tree_id=tree_one["id"])) == 0
        assert len(crud.list_people(conn, tree_id=tree_two["id"])) == 1
