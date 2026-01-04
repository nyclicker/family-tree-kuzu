console.log("[app.js] loaded", new Date().toISOString());
window.__APP_JS_LOADED__ = true;

// global variables
let selectedChildId = null;
let selectedChildName = null;
let peopleCache = [];          // used for parent picker
let ctxMode = "normal"; // "normal" | "pick-parent"
let selectedChild = null; // { id, label }
let selectedChildLabel = null;
let parentPickMode = false; // when true: left-click picks a parent

// If your Plotly trace uses customdata for person_id, set this true.
const NODE_ID_FROM_CUSTOMDATA = true;

function clearParentPick() {
  selectedChildId = null;
  selectedChildLabel = null;
  parentPickMode = false;
  setStatus("");
}

function enterParentPick(child) {
  selectedChildId = child.id;
  selectedChildLabel = child.label;
  parentPickMode = true;
  setStatus(`Pick a parent for "${selectedChildLabel}" (left-click a node). Right-click background to cancel.`);
}

async function fetchJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function refreshPeopleDropdowns() {
  const people = await fetchJSON("/people");
  peopleCache = people;

  const from = document.getElementById("from");
  const to = document.getElementById("to");
  if (from && to) {            // if dropdowns still exist in your UI
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
}

let lastHoverPoint = null;

function attachPlotlyHoverTracking(gd) {
  gd.on("plotly_hover", (ev) => {    
    if (ev && ev.points && ev.points[0]) lastHoverPoint = ev.points[0];
  });
  gd.on("plotly_unhover", (ev) => {    
    lastHoverPoint = null;
  });
}

// Expect your node trace has customdata with { id, label } OR arrays you can map.
function getHoveredPerson() {
  const p = lastHoverPoint;
  if (!p) return null;

  console.log("[getHoveredPerson] lastHoverPoint", { p });
  //customdata is an object per point: { id, label }
  if (p.customdata && typeof p.customdata === "object" && p.customdata.person_id) {
    return { id: p.customdata.person_id, label: p.customdata.label || p.text || "" };
  }

  // Fallback: no id available → can't do node-specific actions reliably
  return null;
}

function showMenuAt(x, y) {
  const menu = document.getElementById("ctxMenu");
  menu.style.left = `${x}px`;
  menu.style.top = `${y}px`;
  menu.style.display = "block";
}

function hideMenu() {
  const menu = document.getElementById("ctxMenu");
  if (menu) menu.style.display = "none";
}

function showNodeMenu(x, y) {
  // show only node actions
  document.getElementById("ctxAddPerson").style.display = "none";
  document.getElementById("ctxAddChildOf").style.display = "block";
  showMenuAt(x, y);
}

function showBackgroundMenu(x, y) {
  // show only background actions
  document.getElementById("ctxAddPerson").style.display = "block";
  document.getElementById("ctxAddChildOf").style.display = "none";
  showMenuAt(x, y);
}

// NEW NEW DRAW GRPAH without hover

async function drawGraph() {
  const res = await fetch("/api/plotly");
  const fig = await res.json();

  const gd = document.getElementById("graph");
  //await Plotly.newPlot(gd, fig.data, fig.layout, fig.config || {});
  //  await Plotly.react(gd, fig.data, fig.layout, config={"scrollZoom": "True", "responsive": "True", "displayModeBar": "True"} || {});

  if (!gd) {
    console.error("Missing #graph element");
    return;
  }

  try {
    console.log("Fetching /api/plotly ...");
    const res = await fetch("/api/plotly");

    console.log("Response status:", res.status);
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`GET /api/plotly failed: ${res.status} ${txt}`);
    }

    const fig = await res.json();
    console.log("Got figure keys:", Object.keys(fig));

    // Defensive defaults
    fig.config = fig.config || {};
    fig.config.scrollZoom = true;
    fig.config.responsive = true;

    await Plotly.react(gd, fig.data || [], fig.layout || {}, fig.config);
    console.log("Plotly rendered.");
  } catch (err) {
    console.error("drawGraph error:", err);
    // make it obvious on-screen too
    gd.innerHTML = `<div style="padding:12px;color:#b00;font-family:system-ui">
      Plot failed: ${String(err)}
    </div>`;
  }

  // Track last point Plotly says we clicked (reliable for nodes)
  let lastPoint = null;

  gd.on("plotly_click", (ev) => {
    if (!ev?.points?.length) return;

    // Only care about node trace points (assumes first trace is edges, second is nodes — adjust if needed)
    const p = ev.points[0];
    lastPoint = p;

    const person = personFromPlotlyPoint(p);
    console.log("[plotly_click] clicked person:", person, 
      "parentPickMode:", parentPickMode, "selectedChildId:", selectedChildId
    );
    if (!person) return;

    if (parentPickMode) {
      // left-click chooses parent
      if (person.id === selectedChildId) {
        setStatus("Pick a different person (cannot relate to self).");
        return;
      }

      createChildOf(selectedChildId, person.id)
        .then(async () => {
          setStatus(`Added: ${selectedChildLabel} CHILD_OF ${person.label}`);
          clearParentPick();
          await drawGraph();
        })
        .catch((err) => {
          console.error(err);
          setStatus(`Error adding relationship: ${err.message || err}`);
        });
    }
  });

  // Right-click: decide node vs background by attempting to "hit test" using event target
  gd.oncontextmenu = (e) => {
    e.preventDefault();
    hideMenu();

    // If we're in parent-pick mode, let right-click on background cancel
    if (parentPickMode) {
      // If right-click isn't on a node, treat as cancel + show background menu
      const hit = tryResolveNodeFromEvent(e, gd, fig);
      console.log("[contextmenu] parentPickMode hit test:", hit);
      if (!hit) {
        clearParentPick();
        showBackgroundMenu(e.clientX, e.clientY);
        return false;
      }
    }

    const person = tryResolveNodeFromEvent(e, gd, fig);
    if (person) {
      // store which node this menu refers to
      lastRightClickedPerson = person;
      console.log("[contextmenu] right-clicked person:", person);
      showNodeMenu(e.clientX, e.clientY);
    } else {
      showBackgroundMenu(e.clientX, e.clientY);
    }
    return false;
  };

  // Click anywhere hides the menu
  document.addEventListener("click", () => hideMenu(), { once: true });
  window.addEventListener("scroll", () => hideMenu(), true);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && parentPickMode) {
      clearParentPick();
    }
  });

  // Esc hides the menu
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") hideMenu();
  }, { once: true });
}

window.addEventListener("resize", () => {
  const gd = document.getElementById("graph");
  if (gd) Plotly.Plots.resize(gd);
});

let lastRightClickedPerson = null;

function personFromPlotlyPoint(p) {
  // We rely on customdata being person_id, and text being label
  console.log("[personFromPlotlyPoint] p:", p);
  const id = p?.customdata.person_id ?? null;
  const label = p?.customdata.label ?? p?.hovertext ?? null;

  if (!id) return null;
  return { id: String(id), label: label ? String(label) : String(id) };
}

/**
 * Best-effort node detection on right-click:
 * - If right-click happened on a Plotly point, Plotly often sets gd._hoverdata
 * - We can also use Plotly.Fx.hover to force-hover at cursor pixel
 */
function tryResolveNodeFromEvent(e, gd, fig) {
  // 1) If Plotly has hoverdata, use it
  const hover = gd._hoverdata;
  if (hover && hover.length) {
    const person = personFromPlotlyPoint(hover[0]);
    if (person) return person;
  }

  // 2) Force hover at mouse position (more reliable than relying on stale hover)
  // Get mouse position relative to plot
  const bb = gd.getBoundingClientRect();
  const xpx = e.clientX - bb.left;
  const ypx = e.clientY - bb.top;

  try {
    // This triggers Plotly to compute hover points at that pixel
    Plotly.Fx.hover(gd, [{ xpx, ypx }], ["xy"]);
    const hover2 = gd._hoverdata;
    if (hover2 && hover2.length) {
      const person = personFromPlotlyPoint(hover2[0]);
      if (person) return person;
    }
  } catch (_) {
    // ignore
  }

  return null;
}

function startPickParent(childPerson) {
  selectedChild = { id: childPerson.id, label: childPerson.label };
  ctxMode = "pick-parent";
  setStatus(`Adding CHILD_OF for ${childPerson.label}. Now right-click the PARENT node.`);
}

function extractNodeFromEvent(ev) {
  // Works for plotly_hover/plotly_click style events
  const pt = ev?.points?.[0];
  if (!pt) return null;

  // Prefer customdata (best practice: set customdata=person_id per node)
  let id = null;
  if (NODE_ID_FROM_CUSTOMDATA && pt.customdata != null) {
    id = String(pt.customdata);
  } else if (pt.text != null) {
    // fallback: if text is unique id (usually it isn't)
    id = String(pt.text);
  }

  const label =
    (pt.text ? String(pt.text) : null) ||
    (pt.hovertext ? String(pt.hovertext).replace(/<br>/g, " ") : null) ||
    id;

  if (!id) return null;
  return { id, label };
}

function clearRelSelection() {
  selectedChildId = null;
  selectedChildName = null;
}

document.getElementById("ctxAddChildOf").onclick = async () => {
  hideMenu();
  if (!lastRightClickedPerson) return;
  enterParentPick(lastRightClickedPerson);
};

document.getElementById("ctxAddPerson").onclick = async () => {
  hideMenu();
  if (parentPickMode) clearParentPick();

  const display_name = prompt("Person name:");
  if (!display_name) return;

  const sex = prompt("Sex (M/F/U):", "U") || "U";

  await fetchJSON("/people", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name, sex })
  });

  await refreshPeopleDropdowns();
  await drawGraph();
};

function setHint(msg) {
  const hint = document.getElementById("ctxHint");
  if (hint) hint.textContent = msg;
}

document.getElementById("ctxAddPerson").onclick = async () => {
  hideMenu();

  const display_name = prompt("Person name:");
  if (!display_name) return;

  const sex = prompt("Sex (M/F/U):", "U") || "U";

  await fetchJSON("/people", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name, sex })
  });

  await refreshPeopleDropdowns();
  await drawGraph();
};

/* New Code  for relationship creation*/
let selectedFrom = null;       // person_id
let selectedFromName = null;   // display label

function setStatus(msg) {
  const el = document.getElementById("relStatusText");
  if (el) el.textContent = msg;
}

function clearSelection() {
  selectedFrom = null;
  selectedFromName = null;
  setStatus("Right-click a person to begin.");
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") clearSelection();
});

// Helper: resolve clicked point -> { id, label } or null
function getPersonFromPlotlyEvent(ev) {
  if (!ev?.points?.length) return null;
  const pt = ev.points[0];

  // If your node trace uses customdata = person_id per point:
  const id = pt.customdata;

  // label can come from pt.text or pt.hovertext depending on your trace setup
  const label = (pt.text || pt.hovertext || "").toString().replaceAll("<br>", "\n");

  if (!id) return null;
  return { id: id.toString(), label: label || id.toString() };
}

async function createChildOf(childId, parentId) {
  return fetchJSON("/relationships", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_person_id: childId, to_person_id: parentId, type: "CHILD_OF" })
  });
}

(async function init() {
  await refreshPeopleDropdowns();
  await drawGraph();
})();
