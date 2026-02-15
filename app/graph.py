"""Build Cytoscape.js graph data from KuzuDB."""
import kuzu


def build_graph(conn: kuzu.Connection, dataset: str | None = None, tree_id: str | None = None):
    _fields = "p.id, p.display_name, p.is_deceased, p.birth_date, p.death_date"
    if tree_id:
        result = conn.execute(
            f"MATCH (p:Person) WHERE p.tree_id = $tid RETURN {_fields}",
            {"tid": tree_id}
        )
    elif dataset:
        result = conn.execute(
            f"MATCH (p:Person) WHERE p.dataset = $ds RETURN {_fields}",
            {"ds": dataset}
        )
    else:
        result = conn.execute(f"MATCH (p:Person) RETURN {_fields}")
    nodes = []
    node_ids = set()
    while result.has_next():
        row = result.get_next()
        node_data = {"id": row[0], "label": row[1]}
        if row[2]:
            node_data["is_deceased"] = True
        if row[3]:
            node_data["birth_date"] = row[3]
        if row[4]:
            node_data["death_date"] = row[4]
        nodes.append({"data": node_data})
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
