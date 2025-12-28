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
  const fig = await fetchJSON("/api/plotly");
  Plotly.newPlot("graph", fig.data, fig.layout, fig.config || { responsive: true });
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
  const type = document.getElementById("type").value;

  // If EARLIEST_ANCESTOR, do not send to_person_id
  const payload =
    type === "EARLIEST_ANCESTOR"
      ? { from_person_id: from, type }
      : { from_person_id: from, to_person_id: document.getElementById("to").value, type };

  await fetchJSON("/relationships", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  await drawGraph();
};

(async function init() {
  await refreshPeopleDropdowns();
  await drawGraph();
})();
