let cy;

async function fetchJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function refreshPeopleDropdowns() {
  const people = await fetchJSON("/people");
  const from = document.getElementById("from");
  const to = document.getElementById("to");
  from.innerHTML = "";
  to.innerHTML = "";

  for (const p of people) {
    const o1 = document.createElement("option");
    o1.value = p.id;
    o1.textContent = p.display_name;

    const o2 = document.createElement("option");
    o2.value = p.id;
    o2.textContent = p.display_name;

    from.appendChild(o1);
    to.appendChild(o2);
  }
}

async function drawGraph() {
  const g = await fetchJSON("/graph");

  const elements = [...g.nodes, ...g.edges];

  if (!cy) {
    cy = cytoscape({
      container: document.getElementById("cy"),
      elements,
      layout: { name: "breadthfirst", directed: true, padding: 20 },
      style: [
        {
          selector: "node",
          style: {
            "label": "data(label)",
            "text-wrap": "wrap",
            "text-max-width": 140,
            "text-valign": "center",
            "text-halign": "center",
            "padding": "10px",
            "shape": "round-rectangle",
          }
        },
        {
          selector: "edge",
          style: {
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "label": "data(type)",
            "font-size": 10
          }
        }
      ]
    });
  } else {
    cy.elements().remove();
    cy.add(elements);
    cy.layout({ name: "breadthfirst", directed: true, padding: 20 }).run();
  }
}

document.getElementById("addPerson").onclick = async () => {
  const name = document.getElementById("name").value.trim();
  const sex = document.getElementById("sex").value;
  if (!name) return;

  await fetchJSON("/people", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: name, sex })
  });

  document.getElementById("name").value = "";
  await refreshPeopleDropdowns();
  await drawGraph();
};

document.getElementById("addRel").onclick = async () => {
  const from = document.getElementById("from").value;
  const to = document.getElementById("to").value;
  const type = document.getElementById("type").value;

  if (!from || !to || from === to) return;

  await fetchJSON("/relationships", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_person_id: from, to_person_id: to, type })
  });

  await drawGraph();
};

(async function init() {
  await refreshPeopleDropdowns();
  await drawGraph();
})();
