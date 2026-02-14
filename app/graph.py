"""Build Cytoscape.js graph data from KuzuDB."""
import kuzu


def build_graph(conn: kuzu.Connection, dataset: str | None = None, tree_id: str | None = None):
    if tree_id:
        result = conn.execute(
            "MATCH (p:Person) WHERE p.tree_id = $tid RETURN p.id, p.display_name",
            {"tid": tree_id}
        )
    elif dataset:
        result = conn.execute(
            "MATCH (p:Person) WHERE p.dataset = $ds RETURN p.id, p.display_name",
            {"ds": dataset}
        )
    else:
        result = conn.execute("MATCH (p:Person) RETURN p.id, p.display_name")
    nodes = []
    node_ids = set()
    while result.has_next():
        row = result.get_next()
        nodes.append({"data": {"id": row[0], "label": row[1]}})
        node_ids.add(row[0])

    edges = []
    for rel_type in ["PARENT_OF", "SPOUSE_OF"]:
        result = conn.execute(
            f"MATCH (a:Person)-[r:{rel_type}]->(b:Person) RETURN r.id, a.id, b.id"
        )
        while result.has_next():
            row = result.get_next()
            # When filtering by dataset/tree, only include edges between nodes in the set
            if (dataset or tree_id) and (row[1] not in node_ids or row[2] not in node_ids):
                continue
            edges.append({"data": {
                "id": row[0], "source": row[1], "target": row[2], "type": rel_type
            }})

    return {"nodes": nodes, "edges": edges}
