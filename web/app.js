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
// multi-tree state
let activeTreeId = null;
let activeTreeVersionId = null; // published active version id
let workingDrafts = []; // cached drafts for current base version
let unsavedCount = 0;
let treesCache = [];

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
  const people = await fetchJSON(`/people${activeTreeId ? `?tree_id=${activeTreeId}` : ''}`);
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

function dismissAllMenus() {
  hideMenu();
  lastRightClickedPerson = null;
  lastRightClickedEdge = null;
}

function showNodeMenu(x, y) {
  // show only node actions
  document.getElementById("ctxEditPerson").style.display = "block";
  document.getElementById("ctxAddPerson").style.display = "none";
  document.getElementById("ctxAddChildOf").style.display = "block";
  document.getElementById("ctxDeletePerson").style.display = "block";
  // hide relationship delete when node menu shown
  const delRelBtn = document.getElementById("ctxDeleteRelationship");
  if (delRelBtn) delRelBtn.style.display = "none";
  showMenuAt(x, y);
}

function showBackgroundMenu(x, y) {
  // show only background actions
  document.getElementById("ctxEditPerson").style.display = "none";
  document.getElementById("ctxAddPerson").style.display = "block";
  document.getElementById("ctxAddChildOf").style.display = "none";
  document.getElementById("ctxDeletePerson").style.display = "none";
  const delRelBtn = document.getElementById("ctxDeleteRelationship");
  if (delRelBtn) delRelBtn.style.display = "none";
  showMenuAt(x, y);
}

function showEdgeMenu(x, y) {
  // show only relationship-specific actions
  const editBtn = document.getElementById("ctxEditPerson"); if (editBtn) editBtn.style.display = "none";
  const addBtn = document.getElementById("ctxAddPerson"); if (addBtn) addBtn.style.display = "none";
  const addChildBtn = document.getElementById("ctxAddChildOf"); if (addChildBtn) addChildBtn.style.display = "none";
  const delPersonBtn = document.getElementById("ctxDeletePerson"); if (delPersonBtn) delPersonBtn.style.display = "none";
  const delRelBtn = document.getElementById("ctxDeleteRelationship"); if (delRelBtn) delRelBtn.style.display = "block";
  showMenuAt(x, y);
}

// NEW NEW DRAW GRPAH without hover

async function drawGraph() {
  const gd = document.getElementById("graph");
  //await Plotly.newPlot(gd, fig.data, fig.layout, fig.config || {});
  //  await Plotly.react(gd, fig.data, fig.layout, config={"scrollZoom": "True", "responsive": "True", "displayModeBar": "True"} || {});

  if (!gd) {
    console.error("Missing #graph element");
    return;
  }

  try {
    let url = '/api/plotly';
    const params = [];
    if (activeTreeId) params.push(`tree_id=${encodeURIComponent(activeTreeId)}`);
    if (activeTreeVersionId) params.push(`tree_version_id=${encodeURIComponent(activeTreeVersionId)}`);
    if (params.length) url += '?' + params.join('&');
    console.log('Fetching', url);
    const res = await fetch(url);

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

    // clear any UI subtree highlight state before re-render
    try { clearSubtreeHighlight(gd); } catch (e) {}
    await Plotly.react(gd, fig.data || [], fig.layout || {}, fig.config);
    try { setupEdgeHitLayer(gd); } catch (e) { /* ignore */ }
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
    const gdData = gd.data || [];
    // determine which trace was clicked: edges are usually the "lines" trace
    const trace = gdData[p.curveNumber] || {};

    // If an edge (line) was clicked, handle edge actions (highlight or delete)
    if ((trace.mode || "").includes("lines")) {
      handleEdgeClick(p, gd);
      return;
    }

    // Otherwise treat as node click
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
      return;
    }

    // Normal node click -> highlight subtree rooted at this node
    try {
        // auto-clear any existing highlight then highlight new subtree
        clearSelectionHighlights(gd);
        highlightSubtree(person.id, gd);
    } catch (err) {
      console.error('highlightSubtree error', err);
    }
  });

  // Right-click: decide node vs background by attempting to "hit test" using event target
  // Use addEventListener for more reliable binding (Plotly may replace internal elements)
  // Use a capture-phase document contextmenu listener tied to this graph instance.
  // This is more reliable than binding on Plotly's internal elements.
  const graphContextHandler = (ev) => {
    // make handler async-capable by wrapping an inner async fn
    (async function (ev) {
    const inGraph = ev.target && ev.target.closest && ev.target.closest('#graph');
    if (!inGraph) return; // let other handlers run for other graph instances
    try {
      ev.preventDefault();
      hideMenu();

      // If we're in parent-pick mode, let right-click on background cancel
      if (parentPickMode) {
        const hit = tryResolveNodeFromEvent(ev, gd);
        if (!hit) {
          clearParentPick();
          dismissAllMenus();
          clearSelectionHighlights(gd);
          return;
        }
      }

      // Check edges FIRST (more specific), then nodes, then background
      const hitEdge = await tryResolveEdgeFromEvent(ev, gd);
      if (hitEdge) {
        lastRightClickedEdge = hitEdge; // { relationship_id, parent_id, child_id }
        showEdgeMenu(ev.clientX, ev.clientY);
        return;
      }

      // If we didn't hit an edge, check for nodes
      const person = await tryResolveNodeFromEventAsync(ev, gd);
      if (person) {
        lastRightClickedPerson = person;
        showNodeMenu(ev.clientX, ev.clientY);
      } else {
        // No edge or node hit -> dismiss any open context UI
        dismissAllMenus();
        clearSelectionHighlights(gd);
        if (parentPickMode) clearParentPick();
      }
    } catch (err) {
      console.error('graphContextHandler error', err);
      hideMenu();
    }
    })(ev);
  };
  document.addEventListener('contextmenu', graphContextHandler, true);

  // (graphContextHandler above now handles contextmenu events within the graph)

  if (!_globalMenuListenersBound) {
    document.addEventListener("click", dismissAllMenus);
    window.addEventListener("scroll", () => dismissAllMenus(), true);
    document.addEventListener("keydown", globalEscapeHandler);
    _globalMenuListenersBound = true;
  }
}

window.addEventListener("resize", () => {
  const gd = document.getElementById("graph");
  if (gd) Plotly.Plots.resize(gd);
});

let lastRightClickedPerson = null;
let lastRightClickedEdge = null;
let _globalMenuListenersBound = false;

function clearSelectionHighlights(gd) {
  clearSubtreeHighlight(gd);
}

function globalEscapeHandler(ev) {
  if (ev.key !== "Escape") return;
  if (parentPickMode) clearParentPick();
  dismissAllMenus();
  const gd = document.getElementById("graph");
  clearSelectionHighlights(gd);
}

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
function tryResolveNodeFromEvent(e, gd) {
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

// Async version: try existing hover approaches and return hover.customdata if node found
async function tryResolveNodeFromEventAsync(e, gd) {
  // Try existing synchronous method first
  const hit = tryResolveNodeFromEvent(e, gd);
  if (hit) return hit;

  // As a fallback, attempt to force hover at cursor (Plotly.Fx.hover is synchronous-ish)
  try {
    const bb = gd.getBoundingClientRect();
    const xpx = e.clientX - bb.left;
    const ypx = e.clientY - bb.top;
    Plotly.Fx.hover(gd, [{ xpx, ypx }], ['xy']);
    const hv = gd._hoverdata && gd._hoverdata[0];
    
    // Make sure this is a node (has person_id), not an edge (has parent_id/child_id)
    if (hv && hv.customdata && hv.customdata.person_id && !hv.customdata.parent_id) {
      return { id: hv.customdata.person_id, label: hv.customdata.label || hv.text || '' };
    }
  } catch (e) {
    // ignore
  }
  return null;
}

// Try to resolve an edge (relationship) under the cursor by checking hover data on the hit-layer.
// The hit-layer is a wide transparent line trace that overlays the actual edges.
async function tryResolveEdgeFromEvent(e, gd) {
  const bb = gd.getBoundingClientRect();
  const xpx = e.clientX - bb.left;
  const ypx = e.clientY - bb.top;

  try {
    console.log('[tryResolveEdgeFromEvent] checking at pixel:', { xpx, ypx });
    console.log('[tryResolveEdgeFromEvent] total traces:', gd.data?.length);
    
    // Log trace info for debugging
    if (gd.data) {
      gd.data.forEach((t, idx) => {
        console.log(`  Trace ${idx}: mode=${t.mode}, hasCustomdata=${!!t.customdata}, customdataLen=${t.customdata?.length || 0}`);
      });
    }
    
    // Force hover at cursor position to ensure fresh detection
    Plotly.Fx.hover(gd, [{ xpx, ypx }], ['xy']);
    const hv = gd._hoverdata && gd._hoverdata[0];
    
    console.log('[tryResolveEdgeFromEvent] hover result:', { 
      hasHoverdata: !!gd._hoverdata,
      hasHv: !!hv,
      curveNumber: hv?.curveNumber,
      customdata: hv?.customdata 
    });
    
    // Check for edge customdata (relationship_id or parent_id/child_id)
    if (hv && hv.customdata) {
      if (hv.customdata.relationship_id || (hv.customdata.parent_id && hv.customdata.child_id)) {
        console.log('[tryResolveEdgeFromEvent] ✓ FOUND EDGE');
        return { 
          relationship_id: hv.customdata.relationship_id, 
          parent_id: hv.customdata.parent_id, 
          child_id: hv.customdata.child_id 
        };
      }
    }
    console.log('[tryResolveEdgeFromEvent] ✗ no edge customdata found');
  } catch (err) {
    console.log('[tryResolveEdgeFromEvent] hover error:', err.message);
  } finally {
    try { Plotly.Fx.unhover(gd); } catch (e) {}
  }
  
  return null;
}

// ----------------- Subtree & Edge Highlighting -----------------
let _originalNodeLineColors = null;
let _originalNodeLineWidths = null;
let _highlightEdgeTraceIndex = null;
let _edgeHitTraceIndex = null;
function setupEdgeHitLayer(gd) {
  // remove previous hit layers
  if (_edgeHitTraceIndex != null) {
    try { Plotly.deleteTraces(gd, _edgeHitTraceIndex); } catch (e) {}
    _edgeHitTraceIndex = null;
  }
  const data = gd.data || [];
  // find the existing edge trace (first 'lines' trace with customdata)
  const edgeIdx = data.findIndex((t) => (t.mode || '').includes('lines') && Array.isArray(t.customdata) && t.customdata.length);
  if (edgeIdx < 0) return;
  const edgeTrace = data[edgeIdx];

  // Densify the edge geometry so hover tests succeed along the full segment, not just endpoints.
  const hitX = [];
  const hitY = [];
  const hitCD = [];
  const hitText = [];
  const xs = edgeTrace.x || [];
  const ys = edgeTrace.y || [];
  const cds = edgeTrace.customdata || [];
  for (let i = 0; i < xs.length; i += 3) {
    const x0 = xs[i];
    const x1 = xs[i + 1];
    const y0 = ys[i];
    const y1 = ys[i + 1];
    const cd = cds[i];
    if (x0 == null || x1 == null || y0 == null || y1 == null) continue;

    // two interior points make hover detection reliable across the whole line
    const mx1 = x0 + (x1 - x0) * 0.33;
    const my1 = y0 + (y1 - y0) * 0.33;
    const mx2 = x0 + (x1 - x0) * 0.66;
    const my2 = y0 + (y1 - y0) * 0.66;

    hitX.push(x0, mx1, mx2, x1, null);
    hitY.push(y0, my1, my2, y1, null);
    hitCD.push(cd, cd, cd, cd, null);
    hitText.push(
      'Right-click to delete relationship',
      'Right-click to delete relationship',
      'Right-click to delete relationship',
      'Right-click to delete relationship',
      ''
    );
  }

  const hit = {
    x: hitX,
    y: hitY,
    mode: 'lines',
    line: { width: 24, color: 'rgba(0,0,0,0.01)', simplify: false },
    hoverinfo: 'text',
    hovertext: hitText,
    hoverdistance: 64,
    customdata: hitCD,
    showlegend: false,
    visible: true,
  };

  // add above edges so it captures pointer events
  Plotly.addTraces(gd, hit).then((inds) => {
    if (Array.isArray(inds) && inds.length) _edgeHitTraceIndex = inds[0];
  }).catch(() => {});
}

function addEdgeMidpointMarkers(gd) {
  // No longer needed - hit-layer handles all edge detection
}

function buildEdgeList(gd) {
  const data = gd.data || [];
  // find edge trace: first trace with mode that includes 'lines'
  let edgeIdx = data.findIndex((t) => (t.mode||"").includes("lines"));
  if (edgeIdx < 0) return { edgeIdx: -1, edges: [] };
  const cds = data[edgeIdx].customdata || [];
  const edges = {};
  for (const c of cds) {
    if (!c) continue;
    const rid = c.relationship_id || (`${c.parent_id}::${c.child_id}`);
    if (!edges[rid]) edges[rid] = { relationship_id: c.relationship_id, parent_id: c.parent_id, child_id: c.child_id };
  }
  return { edgeIdx, edges: Object.values(edges) };
}

function highlightSubtree(rootId, gd) {
  if (!gd || !rootId) return;
  const data = gd.data || [];
  // find node trace
  const nodeIdx = data.findIndex((t) => (t.mode||"").includes('markers'));
  if (nodeIdx < 0) return;

  // build adjacency from edge list
  const { edgeIdx, edges } = buildEdgeList(gd);
  const childrenMap = {};
  const relByPair = {};
  for (const e of edges) {
    if (!e.parent_id || !e.child_id) continue;
    childrenMap[e.parent_id] = childrenMap[e.parent_id] || [];
    childrenMap[e.parent_id].push(e.child_id);
    relByPair[`${e.parent_id}::${e.child_id}`] = e.relationship_id;
  }

  // collect subtree nodes and rel pairs via DFS
  const toVisit = [rootId];
  const subtreeNodes = new Set();
  const subtreePairs = [];
  while (toVisit.length) {
    const cur = toVisit.pop();
    if (subtreeNodes.has(cur)) continue;
    subtreeNodes.add(cur);
    const kids = childrenMap[cur] || [];
    for (const c of kids) {
      subtreePairs.push([cur, c]);
      toVisit.push(c);
    }
  }

  // prepare node marker arrays
  const nodeCustom = data[nodeIdx].customdata || [];
  const nodeCount = nodeCustom.length;
  const baseColors = Array.isArray(data[nodeIdx].marker.color) ? data[nodeIdx].marker.color.slice() : new Array(nodeCount).fill(data[nodeIdx].marker.color || '#888');
  const baseLineColors = (data[nodeIdx].marker.line && Array.isArray(data[nodeIdx].marker.line.color)) ? data[nodeIdx].marker.line.color.slice() : new Array(nodeCount).fill((data[nodeIdx].marker.line && data[nodeIdx].marker.line.color) || '#333');
  const baseLineWidths = (data[nodeIdx].marker.line && Array.isArray(data[nodeIdx].marker.line.width)) ? data[nodeIdx].marker.line.width.slice() : new Array(nodeCount).fill((data[nodeIdx].marker.line && data[nodeIdx].marker.line.width) || 1);

  // save originals if not saved
  if (!_originalNodeLineColors) _originalNodeLineColors = baseLineColors.slice();
  if (!_originalNodeLineWidths) _originalNodeLineWidths = baseLineWidths.slice();

  // build new arrays
  const newLineColors = baseLineColors.slice();
  const newLineWidths = baseLineWidths.slice();
  const newMarkerColors = Array.isArray(baseColors) ? baseColors.slice() : new Array(nodeCount).fill(baseColors);

  for (let i = 0; i < nodeCustom.length; i++) {
    const pid = nodeCustom[i].person_id;
    if (subtreeNodes.has(pid)) {
      // use a clear blue highlight and thicker outline for subtree nodes
      newLineColors[i] = '#1f77b4';
      newLineWidths[i] = 4;
      // brighten marker color to a soft blue
      newMarkerColors[i] = '#aec7e8';
    }
  }

  // apply restyle for node trace
  Plotly.restyle(gd, { 'marker.line.color': [newLineColors], 'marker.line.width': [newLineWidths], 'marker.color': [newMarkerColors] }, [nodeIdx]);

  // add overlay trace for highlighted edges
  // remove previous if exists
  if (_highlightEdgeTraceIndex != null) {
    try { Plotly.deleteTraces(gd, _highlightEdgeTraceIndex); } catch (e) { /* ignore */ }
    _highlightEdgeTraceIndex = null;
  }

  const edgeX = [];
  const edgeY = [];
  // find positions of node ids in nodeCustom
  const nodePosMap = {};
  const xs = data[nodeIdx].x || [];
  const ys = data[nodeIdx].y || [];
  for (let i = 0; i < nodeCustom.length; i++) nodePosMap[nodeCustom[i].person_id] = { x: xs[i], y: ys[i] };

  for (const [p, c] of subtreePairs) {
    const pa = nodePosMap[p];
    const ca = nodePosMap[c];
    if (!pa || !ca) continue;
    edgeX.push(pa.x, ca.x, null);
    edgeY.push(pa.y, ca.y, null);
  }

  if (edgeX.length) {
    const overlay = {
      x: edgeX,
      y: edgeY,
      mode: 'lines',
      line: { width: 4, color: '#1f77b4' },
      hoverinfo: 'none',
      showlegend: false,
    };
    Plotly.addTraces(gd, overlay).then((inds) => {
      // store index of newly added trace (Plotly returns [traceIndex])
      if (Array.isArray(inds) && inds.length) _highlightEdgeTraceIndex = inds[0];
    }).catch(() => {});
  }
}

function clearSubtreeHighlight(gd) {
  if (!gd) return;
  const data = gd.data || [];
  const nodeIdx = data.findIndex((t) => (t.mode||"").includes('markers'));
  if (nodeIdx >= 0 && _originalNodeLineColors) {
    Plotly.restyle(gd, { 'marker.line.color': [_originalNodeLineColors], 'marker.line.width': [_originalNodeLineWidths] }, [nodeIdx]);
    _originalNodeLineColors = null;
    _originalNodeLineWidths = null;
  }
  if (_highlightEdgeTraceIndex != null) {
    try { Plotly.deleteTraces(gd, _highlightEdgeTraceIndex); } catch (e) { /* ignore */ }
    _highlightEdgeTraceIndex = null;
  }
}

function highlightEdgeOnly(parentId, childId, gd) {
  if (!gd) return;
  const data = gd.data || [];
  const nodeIdx = data.findIndex((t) => (t.mode||"").includes('markers'));
  if (nodeIdx < 0) return;

  const nodeCustom = data[nodeIdx].customdata || [];
  const nodeCount = nodeCustom.length;
  const baseColors = Array.isArray(data[nodeIdx].marker.color) ? data[nodeIdx].marker.color.slice() : new Array(nodeCount).fill(data[nodeIdx].marker.color || '#888');
  const baseLineColors = (data[nodeIdx].marker.line && Array.isArray(data[nodeIdx].marker.line.color)) ? data[nodeIdx].marker.line.color.slice() : new Array(nodeCount).fill((data[nodeIdx].marker.line && data[nodeIdx].marker.line.color) || '#333');
  const baseLineWidths = (data[nodeIdx].marker.line && Array.isArray(data[nodeIdx].marker.line.width)) ? data[nodeIdx].marker.line.width.slice() : new Array(nodeCount).fill((data[nodeIdx].marker.line && data[nodeIdx].marker.line.width) || 1);

  if (!_originalNodeLineColors) _originalNodeLineColors = baseLineColors.slice();
  if (!_originalNodeLineWidths) _originalNodeLineWidths = baseLineWidths.slice();

  const newLineColors = baseLineColors.slice();
  const newLineWidths = baseLineWidths.slice();
  const newMarkerColors = Array.isArray(baseColors) ? baseColors.slice() : new Array(nodeCount).fill(baseColors);

  for (let i = 0; i < nodeCustom.length; i++) {
    const pid = nodeCustom[i].person_id;
    if (pid === parentId || pid === childId) {
      newLineColors[i] = '#1f77b4';
      newLineWidths[i] = 4;
      newMarkerColors[i] = '#aec7e8';
    }
  }

  Plotly.restyle(gd, { 'marker.line.color': [newLineColors], 'marker.line.width': [newLineWidths], 'marker.color': [newMarkerColors] }, [nodeIdx]);

  // overlay single edge
  if (_highlightEdgeTraceIndex != null) {
    try { Plotly.deleteTraces(gd, _highlightEdgeTraceIndex); } catch (e) {}
    _highlightEdgeTraceIndex = null;
  }
  const nodePosMap = {};
  const xs = data[nodeIdx].x || [];
  const ys = data[nodeIdx].y || [];
  for (let i = 0; i < nodeCustom.length; i++) nodePosMap[nodeCustom[i].person_id] = { x: xs[i], y: ys[i] };
  const pa = nodePosMap[parentId];
  const ca = nodePosMap[childId];
  if (pa && ca) {
    const overlay = { x: [pa.x, ca.x, null], y: [pa.y, ca.y, null], mode: 'lines', line: { width: 4, color: '#1f77b4' }, hoverinfo: 'none', showlegend: false };
    Plotly.addTraces(gd, overlay).then((inds) => { if (Array.isArray(inds) && inds.length) _highlightEdgeTraceIndex = inds[0]; }).catch(() => {});
  }
}

// Handle edge click: show delete prompt or select
async function handleEdgeClick(point, gd) {
  const cd = point.customdata;
  if (!cd) return;
  const relId = cd.relationship_id;
  const parentId = cd.parent_id;
  const childId = cd.child_id;
  // select this edge (do not delete immediately) and highlight it
  lastRightClickedEdge = { relationship_id: relId, parent_id: parentId, child_id: childId };
  try {
    // highlight only this edge and its two nodes
    clearSelectionHighlights(gd);
    highlightEdgeOnly(parentId, childId, gd);
    setStatus(`Selected relationship: ${childId} CHILD_OF ${parentId}. Right-click to open actions.`);
  } catch (e) {
    console.error(e);
  }
}

// clear highlight on Escape
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { const gd = document.getElementById('graph'); clearSubtreeHighlight(gd); } });


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

  if (!activeTreeId || !activeTreeVersionId) {
    setStatus("Select a tree/version first to create drafts.");
    return;
  }

  try {
    await createDraft("person", { display_name, sex, notes: "" });
    setStatus(`Saved draft for ${display_name}`);
    await refreshDraftsCount();
    await drawGraph();
  } catch (err) {
    console.error("Failed to save draft:", err);
    setStatus("Failed to save draft");
  }
};

document.getElementById('ctxDeletePerson').addEventListener('click', async () => {
  hideMenu();
  if (!lastRightClickedPerson) return;
  if (!confirm(`Delete person ${lastRightClickedPerson.label}? This will create a draft.`)) return;
  try {
    // create a person draft with deleted flag
    await createDraft('person', { id: lastRightClickedPerson.id, deleted: true });
    await refreshDraftsCount();
    setStatus('Created delete draft for person');
    await drawGraph();
  } catch (err) {
    console.error('Failed to create delete draft', err);
    setStatus('Failed to create delete draft');
  }
});

document.getElementById('ctxDeleteRelationship').addEventListener('click', async () => {
  hideMenu();
  if (!lastRightClickedEdge) return;
  const parentId = lastRightClickedEdge.parent_id;
  const childId = lastRightClickedEdge.child_id;
  if (!confirm(`Create delete draft for relationship: ${childId} CHILD_OF ${parentId}?`)) return;
  try {
    await createDraft('relationship', { from_person_id: childId, to_person_id: parentId, type: 'CHILD_OF', op: 'delete' });
    await refreshDraftsCount();
    setStatus('Created delete relationship draft');
    await drawGraph();
  } catch (err) {
    console.error('Failed to create delete relationship draft', err);
    setStatus('Failed to create delete relationship draft');
  }
});

// Edit Person handler
document.getElementById("ctxEditPerson").addEventListener("click", () => {
  // hide menu and open edit modal for the last right-clicked person
  hideMenu();
  if (!lastRightClickedPerson) return;
  openEditPersonModal(lastRightClickedPerson);
});

// Ensure context menu buttons are bound (re-bind in case DOM changed)
function initContextMenuBindings() {
  const addChildBtn = document.getElementById('ctxAddChildOf');
  if (addChildBtn) addChildBtn.onclick = async () => { hideMenu(); if (!lastRightClickedPerson) return; enterParentPick(lastRightClickedPerson); };

  const addPersonBtn = document.getElementById('ctxAddPerson');
  if (addPersonBtn) addPersonBtn.onclick = async () => {
    hideMenu(); if (parentPickMode) clearParentPick();
    const display_name = prompt('Person name:'); if (!display_name) return; const sex = prompt('Sex (M/F/U):', 'U') || 'U';
    if (!activeTreeId || !activeTreeVersionId) { setStatus('Select a tree/version first to create drafts.'); return; }
    try { await createDraft('person', { display_name, sex, notes: '' }); setStatus(`Saved draft for ${display_name}`); await refreshDraftsCount(); await drawGraph(); } catch (err) { console.error(err); setStatus('Failed to save draft'); }
  };

  const editBtn = document.getElementById('ctxEditPerson');
  if (editBtn) editBtn.onclick = () => { hideMenu(); if (!lastRightClickedPerson) return; openEditPersonModal(lastRightClickedPerson); };
}

// call once on load
initContextMenuBindings();

function setHint(msg) {
  const hint = document.getElementById("ctxHint");
  if (hint) hint.textContent = msg;
}

function openEditPersonModal(person) {
  document.getElementById("personModalTitle").textContent = `Edit: ${person.label || "Person"}`;
  document.getElementById("personNameInput").value = person.label || "";
  document.getElementById("personNotesInput").value = person.notes || ""; // if you have this

  // populate parent select
  const parentSel = document.getElementById('personParentSelect');
  if (parentSel) {
    parentSel.innerHTML = '';
    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = '(no change)';
    parentSel.appendChild(empty);
    for (const p of peopleCache) {
      if (String(p.id) === String(person.id)) continue;
      const o = document.createElement('option');
      o.value = p.id;
      o.textContent = p.display_name;
      parentSel.appendChild(o);
    }
  }

  document.getElementById("personModalBackdrop").style.display = "block";
  document.getElementById("personModal").style.display = "block";

  // keep reference for save
  document.getElementById("personModal").dataset.personId = person.id;
}

function closePersonModal() {
  document.getElementById("personModalBackdrop").style.display = "none";
  document.getElementById("personModal").style.display = "none";
  document.getElementById("personModal").dataset.personId = "";
}

document.getElementById("personModalCancel").addEventListener("click", closePersonModal);
document.getElementById("personModalBackdrop").addEventListener("click", closePersonModal);

document.getElementById("personModalSave").addEventListener("click", async () => {
  const personId = document.getElementById("personModal").dataset.personId;
  const name = document.getElementById("personNameInput").value.trim();
  const notes = document.getElementById("personNotesInput").value.trim();

  if (!name) {
    setStatus("Name is required.");
    return;
  }
  // Save as a draft (edit) rather than immediately mutating published data
  if (!activeTreeId || !activeTreeVersionId) {
    setStatus('Select a tree/version first to save edits as drafts.');
    return;
  }

  try {
    await createDraft('person', { id: personId, display_name: name, notes });
    await refreshDraftsCount();
    setStatus('Saved person edit as draft.');
  } catch (err) {
    console.error('Failed to save draft', err);
    setStatus('Failed to save draft');
  }

  closePersonModal();
  await drawGraph();
});

// Save parent change handler
document.getElementById('personParentSave').addEventListener('click', async () => {
  const personId = document.getElementById('personModal').dataset.personId;
  const parentSel = document.getElementById('personParentSelect');
  if (!personId || !parentSel) return;
  const parentId = parentSel.value;
  if (!parentId) return setStatus('No parent selected');
  try {
    await createDraft('relationship', { from_person_id: personId, to_person_id: parentId, type: 'CHILD_OF', op: 'replace' });
    await refreshDraftsCount();
    setStatus('Saved parent-change as draft');
    closePersonModal();
    await drawGraph();
  } catch (err) {
    console.error('Failed to save parent change', err);
    setStatus('Failed to save parent change');
  }
});

/*

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
*/

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
  if (!activeTreeId || !activeTreeVersionId) {
    setStatus("Select a tree/version first to create drafts.");
    throw new Error("No active tree/version");
  }

  try {
    await createDraft("relationship", { from_person_id: childId, to_person_id: parentId, type: "CHILD_OF", op: "replace" });
    setStatus("Saved draft relationship");
    return { ok: true };
  } catch (err) {
    throw err;
  }
}

// --- Draft helpers ---
async function createDraft(change_type, payload) {
  const url = `/trees/${activeTreeId}/versions/${activeTreeVersionId}/drafts`;
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ change_type, payload }) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function listDrafts() {
  const url = `/trees/${activeTreeId}/versions/${activeTreeVersionId}/drafts`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function refreshDraftsCount() {
  if (!activeTreeId || !activeTreeVersionId) return;
  const drafts = await listDrafts();
  unsavedCount = drafts.length;
  let badge = document.getElementById("draftCountBadge");
  if (!badge) {
    // create badge next to selector
    const sel = document.getElementById("treeSelect");
    if (sel) {
      badge = document.createElement("span");
      badge.id = "draftCountBadge";
      badge.style.marginLeft = "8px";
      badge.style.padding = "4px 8px";
      badge.style.background = "#ffeb3b";
      badge.style.borderRadius = "8px";
      badge.style.fontSize = "12px";
      sel.parentNode.insertBefore(badge, sel.nextSibling);
    }
  }
  if (badge) badge.textContent = String(unsavedCount || "0");
}

async function publishDrafts() {
  if (!activeTreeId || !activeTreeVersionId) return;
  const url = `/trees/${activeTreeId}/versions/${activeTreeVersionId}/publish`;
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  activeTreeVersionId = data.tree_version_id;
  await loadTrees();
  await refreshDraftsCount();
  await drawGraph();
  setStatus("Published drafts as new version.");
}

async function loadTrees() {
  try {
    const res = await fetch('/trees');
    if (!res.ok) throw new Error(await res.text());
    const trees = await res.json();
    const sel = document.getElementById('treeSelect');
    sel.innerHTML = '';
    // placeholder so selector shows when empty
    const ph = document.createElement('option');
    ph.value = '';
    ph.textContent = 'Select a tree...';
    sel.appendChild(ph);
    for (const t of trees) {
      const o = document.createElement('option');
      o.value = t.id;
      o.textContent = t.name + (t.active_version_id ? ` (v:${t.active_version_id})` : '');
      sel.appendChild(o);
    }

    // pick a sensible default
    if (!activeTreeId && trees.length) {
      activeTreeId = trees[0].id;
    }
    if (activeTreeId) sel.value = activeTreeId;

    // load versions for selected tree
    await loadSelectedTreeVersion();
    // populate versions select for current tree
    try {
      const vres = await fetch(`/trees/${activeTreeId}/versions`);
      if (vres.ok) {
        const vs = await vres.json();
        // populateVersions is defined below
        // but ensure it's available by calling after it's defined (no-op here)
      }
    } catch (err) {
      // ignore
    }

    // cache trees and populate name input
    const nameInput = document.getElementById('treeNameInput');
    treesCache = trees;
    async function refreshTreeName() {
      if (!activeTreeId) {
        if (nameInput) nameInput.value = '';
        return;
      }
      try {
        const t = treesCache.find(x => String(x.id) === String(activeTreeId));
        if (t && nameInput) nameInput.value = t.name || '';
      } catch (err) {
        console.error('refreshTreeName failed', err);
      }
    }
    await refreshTreeName();

    // populate versions select and load button
    const versionsSel = document.getElementById('treeVersionsSelect');
    const loadVerBtn = document.getElementById('treeLoadVersionBtn');
    async function populateVersions(versions) {
      if (!versionsSel) return;
      versionsSel.innerHTML = '';
      for (const v of versions) {
        const o = document.createElement('option');
        o.value = v.id;
        o.textContent = `v:${v.version} ${v.active ? '(active)' : ''}`;
        versionsSel.appendChild(o);
      }
      if (activeTreeVersionId) versionsSel.value = activeTreeVersionId;
    }
    if (loadVerBtn && versionsSel) {
      loadVerBtn.onclick = async () => {
        const selId = versionsSel.value;
        if (!selId) return;
        activeTreeVersionId = selId;
        await refreshPeopleDropdowns();
        await refreshDraftsCount();
        await drawGraph();
        setStatus('Loaded selected version.');
      };
    }

    // initial populate versions for current tree
    try {
      const resv = await fetch(`/trees/${activeTreeId}/versions`);
      if (resv.ok) {
        const vs = await resv.json();
        await populateVersions(vs);
      }
    } catch (err) {
      // ignore
    }

    // attach change handler
    sel.onchange = async (ev) => {
      // tree ids are strings (UUIDs). Keep as string.
      activeTreeId = ev.target.value;
      await loadSelectedTreeVersion();
      await refreshPeopleDropdowns();
      await refreshDraftsCount();
      await refreshTreeName();
      // refresh versions select for new tree
      try {
        const res = await fetch(`/trees/${activeTreeId}/versions`);
        if (res.ok) {
          const vs = await res.json();
          await populateVersions(vs);
        }
      } catch (err) {}
      await drawGraph();
    };

    // Hook existing Save / Discard buttons in the static UI (avoid duplicating buttons)
    const saveBtn = document.getElementById('treeSaveBtn');
    if (saveBtn) {
      saveBtn.onclick = async () => {
        // Integrate rename into save: if the name input differs, ask whether to rename before publishing
        const currentName = (treesCache.find(x => String(x.id) === String(activeTreeId)) || {}).name || '';
        const newName = nameInput ? (nameInput.value && nameInput.value.trim()) : '';
        try {
          if (newName && newName !== currentName) {
            const doRename = confirm('Tree name changed. OK = rename current tree and publish. Cancel = publish without renaming.');
            if (doRename) {
              const pres = await fetch(`/trees/${activeTreeId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: newName }) });
              if (!pres.ok) throw new Error(await pres.text());
              // update UI immediately
              const selEl = document.getElementById('treeSelect');
              if (selEl) {
                for (const opt of selEl.options) {
                  if (String(opt.value) === String(activeTreeId)) {
                    const suffixMatch = opt.textContent.match(/\s*\(v:\s*\d+\)$/);
                    opt.textContent = newName + (suffixMatch ? ` ${suffixMatch[0]}` : '');
                    break;
                  }
                }
              }
            }
          }
          if (!confirm('Publish drafts as a new version?')) return;
          await publishDrafts();
        } catch (err) {
          setStatus('Publish failed: ' + String(err));
        }
      };
    }

    const discardBtn = document.getElementById('treeDiscardBtn');
    if (discardBtn) {
      discardBtn.onclick = async () => {
        if (!confirm('Discard all drafts for this version?')) return;
        try {
          const res = await fetch(`/trees/${activeTreeId}/versions/${activeTreeVersionId}/drafts`, { method: 'DELETE' });
          if (!res.ok) throw new Error(await res.text());
          await refreshDraftsCount();
          await drawGraph();
          setStatus('Discarded drafts.');
        } catch (err) {
          setStatus('Discard failed: ' + String(err));
        }
      };
    }

    // Create new tree button -> prompt for name and call import endpoint (creates tree + initial version)
    const newBtn = document.getElementById('treeNewBtn');
    if (newBtn) {
      newBtn.onclick = async () => {
        const name = prompt('New tree name:');
        if (!name) return;
        try {
          const res = await fetch('/trees/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          // switch to the new tree/version
          activeTreeId = data.tree_id;
          activeTreeVersionId = data.tree_version_id;
          await loadTrees();
          await refreshPeopleDropdowns();
          await refreshDraftsCount();
          await drawGraph();
          setStatus('Created new tree.');
        } catch (err) {
          console.error('Failed to create tree', err);
          setStatus('Failed to create tree: ' + String(err));
        }
      };
    }

  } catch (err) {
    console.error('loadTrees failed', err);
  }
}

async function loadSelectedTreeVersion() {
  if (!activeTreeId) return;
  const res = await fetch(`/trees/${activeTreeId}/versions`);
  if (!res.ok) throw new Error(await res.text());
  const versions = await res.json();
  // find active version
  const active = versions.find(v => v.active) || versions[versions.length-1];
  activeTreeVersionId = active ? active.id : null;
}

(async function init() {
  await refreshPeopleDropdowns();
  await loadTrees();
  await refreshDraftsCount();
  await drawGraph();
})();
