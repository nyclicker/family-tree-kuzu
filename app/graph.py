"""Build Cytoscape.js graph data from KuzuDB."""
import kuzu


def build_graph(conn: kuzu.Connection):
    result = conn.execute("MATCH (p:Person) RETURN p.id, p.display_name")
    nodes = []
    while result.has_next():
        row = result.get_next()
        nodes.append({"data": {"id": row[0], "label": row[1]}})

    edges = []
    for rel_type in ["PARENT_OF", "SPOUSE_OF", "SIBLING_OF"]:
        result = conn.execute(
            f"MATCH (a:Person)-[r:{rel_type}]->(b:Person) RETURN r.id, a.id, b.id"
        )
        while result.has_next():
            row = result.get_next()
            edges.append({"data": {
                "id": row[0], "source": row[1], "target": row[2], "type": rel_type
            }})

    return {"nodes": nodes, "edges": edges}
