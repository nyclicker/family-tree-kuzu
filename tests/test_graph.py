"""Tests for app/graph.py — graph building, filtering."""
from app import graph, crud


class TestBuildGraph:
    def test_empty(self, conn, tree_one):
        result = graph.build_graph(conn, tree_id=tree_one["id"])
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_nodes_and_edges(self, conn, family_graph):
        result = graph.build_graph(conn, tree_id=family_graph["tree"]["id"])
        assert len(result["nodes"]) == 4
        assert len(result["edges"]) >= 3

    def test_filter_by_tree_id(self, conn, tree_one, tree_two, family_graph):
        crud.create_person(conn, "Other", tree_id=tree_two["id"])
        result = graph.build_graph(conn, tree_id=tree_one["id"])
        node_labels = {n["data"]["label"] for n in result["nodes"]}
        assert "Other" not in node_labels

    def test_filter_by_dataset(self, conn, tree_one):
        crud.create_person(conn, "DS1Person", dataset="ds1", tree_id=tree_one["id"])
        crud.create_person(conn, "DS2Person", dataset="ds2", tree_id=tree_one["id"])
        result = graph.build_graph(conn, dataset="ds1")
        labels = {n["data"]["label"] for n in result["nodes"]}
        assert "DS1Person" in labels
        assert "DS2Person" not in labels

    def test_excludes_cross_tree_edges(self, conn, tree_one, tree_two):
        p1 = crud.create_person(conn, "P1", tree_id=tree_one["id"])
        p2 = crud.create_person(conn, "P2", tree_id=tree_two["id"])
        crud.create_relationship(conn, p1["id"], p2["id"], "PARENT_OF")
        result = graph.build_graph(conn, tree_id=tree_one["id"])
        # Edge should be excluded since p2 is in a different tree
        assert len(result["edges"]) == 0

    def test_deceased_and_dates(self, conn, tree_one):
        crud.create_person(
            conn, "DeadPerson", tree_id=tree_one["id"],
            birth_date="1900-01-01", death_date="1970-06-15", is_deceased=True,
        )
        result = graph.build_graph(conn, tree_id=tree_one["id"])
        assert len(result["nodes"]) == 1
        node = result["nodes"][0]["data"]
        assert node["is_deceased"] is True
        assert node["birth_date"] == "1900-01-01"
        assert node["death_date"] == "1970-06-15"
