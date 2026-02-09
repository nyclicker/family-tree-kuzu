let cy = null;
let people = [];
let selectedPersonId = null;
let currentDatasetName = '';

// Generation-based color palette
const GEN_COLORS = [
  '#8e44ad', '#2980b9', '#27ae60', '#e67e22', '#e74c3c',
  '#1abc9c', '#d35400', '#3498db', '#9b59b6', '#2ecc71',
  '#f39c12', '#16a085', '#c0392b', '#2c3e50'
];

// Track context menu target
let ctxTargetNode = null;
let ctxTargetEdge = null;

// Track whether user has dragged nodes
let layoutDirty = false;

// ── Data loading ──

async function loadPeople() {
  const res = await fetch('/people');
  people = await res.json();
  const query = document.getElementById('searchInput') ? document.getElementById('searchInput').value.trim() : '';
  renderPeopleList(query);
  populateDropdowns();
}

// ── Search & People List ──

function renderPeopleList(filter) {
  const ul = document.getElementById('peopleList');
  const countEl = document.getElementById('searchCount');
  if (people.length === 0) {
    ul.innerHTML = '<li style="color:#999">No people added yet</li>';
    countEl.textContent = '';
    return;
  }
  const query = (filter || '').toLowerCase();
  const filtered = query
    ? people.filter(p => p.display_name.toLowerCase().includes(query))
    : people;

  countEl.textContent = query
    ? `${filtered.length} of ${people.length} people`
    : `${people.length} people`;

  if (filtered.length === 0) {
    ul.innerHTML = '<li style="color:#999">No matches found</li>';
    return;
  }

  ul.innerHTML = filtered.map(p => {
    const active = p.id === selectedPersonId ? ' active' : '';
    let name = escapeHtml(p.display_name);
    if (query) {
      const re = new RegExp(`(${escapeRegex(query)})`, 'gi');
      name = name.replace(re, '<span class="match-highlight">$1</span>');
    }
    return `<li class="${active}" data-id="${p.id}" onclick="navigateToPerson('${p.id}')"><span class="sex-badge">${p.sex}</span> ${name}</li>`;
  }).join('');
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function onSearchInput() {
  const query = document.getElementById('searchInput').value.trim();
  renderPeopleList(query);
  highlightMatchingNodes(query);
}

function onSearchKeydown(e) {
  if (e.key === 'Enter') {
    const query = document.getElementById('searchInput').value.trim().toLowerCase();
    if (!query) return;
    const match = people.find(p => p.display_name.toLowerCase().includes(query));
    if (match) navigateToPerson(match.id);
  }
  if (e.key === 'Escape') {
    document.getElementById('searchInput').value = '';
    onSearchInput();
  }
}

function highlightMatchingNodes(query) {
  if (!cy) return;
  cy.elements().removeClass('search-match search-dimmed');
  if (!query) return;
  const q = query.toLowerCase();
  const matched = cy.nodes().filter(n => n.data('label').toLowerCase().includes(q));
  const unmatched = cy.nodes().not(matched);
  matched.addClass('search-match');
  unmatched.addClass('search-dimmed');
  cy.edges().forEach(edge => {
    if (edge.source().hasClass('search-dimmed') && edge.target().hasClass('search-dimmed')) {
      edge.addClass('search-dimmed');
    }
  });
}

function navigateToPerson(personId) {
  selectedPersonId = personId;
  const query = document.getElementById('searchInput').value.trim();
  renderPeopleList(query);
  if (!cy) return;
  const node = cy.getElementById(personId);
  if (!node || node.empty()) return;
  cy.elements().removeClass('search-match search-dimmed');
  cy.elements().unselect();
  node.select();
  cy.animate({ center: { eles: node }, zoom: 1.5 }, { duration: 400 });
}

function populateDropdowns() {
  const opts = people.map(p => `<option value="${p.id}">${p.display_name}</option>`).join('');
  const empty = '<option disabled>Add people first</option>';
  document.getElementById('relFrom').innerHTML = opts || empty;
  document.getElementById('relTo').innerHTML = opts || empty;
}

// ── Status messages ──

function showStatus(id, message, isError) {
  const el = document.getElementById(id);
  el.textContent = message;
  el.className = 'status ' + (isError ? 'error' : 'success');
  setTimeout(() => { el.className = 'status'; }, 4000);
}

// ── Sidebar: Add Person ──

async function addPerson() {
  const name = document.getElementById('personName').value.trim();
  if (!name) { showStatus('personStatus', 'Name is required', true); return; }
  const sex = document.getElementById('personSex').value;
  const notes = document.getElementById('personNotes').value.trim() || null;
  try {
    const res = await fetch('/people', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, sex, notes })
    });
    if (!res.ok) throw new Error(await res.text());
    document.getElementById('personName').value = '';
    document.getElementById('personNotes').value = '';
    showStatus('personStatus', `Added ${name}`, false);
    await refresh();
  } catch (e) {
    showStatus('personStatus', 'Error: ' + e.message, true);
  }
}

// ── Sidebar: Add Relationship ──

async function addRelationship() {
  const from_person_id = document.getElementById('relFrom').value;
  const to_person_id = document.getElementById('relTo').value;
  const type = document.getElementById('relType').value;
  if (!from_person_id || !to_person_id) {
    showStatus('relStatus', 'Select both people', true); return;
  }
  if (from_person_id === to_person_id) {
    showStatus('relStatus', 'Cannot relate a person to themselves', true); return;
  }
  try {
    const res = await fetch('/relationships', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_person_id, to_person_id, type })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    showSpouseMergeReport(data);
    showStatus('relStatus', 'Relationship added', false);
    await refresh();
  } catch (e) {
    showStatus('relStatus', 'Error: ' + e.message, true);
  }
}

// ── Load Data: Dataset picker ──

let availableDatasets = [];

async function loadAvailableDatasets() {
  try {
    const res = await fetch('/api/datasets');
    availableDatasets = await res.json();
    renderDatasetPicker();
  } catch (e) {
    document.getElementById('datasetList').innerHTML = '<div style="padding:8px;color:#999">Could not load datasets</div>';
  }
}

function renderDatasetPicker() {
  const el = document.getElementById('datasetList');
  if (availableDatasets.length === 0) {
    el.innerHTML = '<div style="padding:8px;color:#999">No data files found in /data</div>';
    return;
  }
  el.innerHTML = availableDatasets.map((ds, i) =>
    `<div class="ds-item"><input type="checkbox" id="ds_${i}" value="${escapeHtml(ds.filename)}"><label for="ds_${i}">${escapeHtml(ds.name)}</label></div>`
  ).join('');
}

async function loadSelectedDatasets(combine) {
  const checkboxes = document.querySelectorAll('#datasetList input[type="checkbox"]:checked');
  const files = Array.from(checkboxes).map(cb => cb.value);
  if (files.length === 0) {
    showStatus('loadStatus', 'Select at least one dataset', true);
    return;
  }
  showStatus('loadStatus', 'Loading...', false);
  try {
    const res = await fetch('/api/import/dataset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files, combine })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    setDatasetName(data.dataset_name || 'Family Tree');
    showImportReport(data);
    await refresh();
  } catch (e) {
    showStatus('loadStatus', 'Error: ' + e.message, true);
  }
}

async function clearData() {
  if (!confirm('Clear all data from the graph? This cannot be undone.')) return;
  try {
    await fetch('/api/clear', { method: 'POST' });
    setDatasetName('');
    document.getElementById('importReportSection').style.display = 'none';
    await refresh();
    showStatus('loadStatus', 'All data cleared', false);
  } catch (e) {
    showStatus('loadStatus', 'Error: ' + e.message, true);
  }
}

function setDatasetName(name) {
  currentDatasetName = name;
  const el = document.getElementById('datasetInfo');
  if (el) el.textContent = name || 'No data loaded';
  const headerLabel = document.getElementById('datasetLabel');
  if (headerLabel) headerLabel.textContent = name || '';
  const saveBtn = document.getElementById('saveBtn');
  if (saveBtn) saveBtn.style.display = name ? 'inline-block' : 'none';
  const clearBtn = document.getElementById('clearBtn');
  if (clearBtn) clearBtn.style.display = name ? 'inline-block' : 'none';
  const combineBtn = document.getElementById('combineBtn');
  if (combineBtn) combineBtn.style.display = name ? 'inline-block' : 'none';
}

async function saveChanges() {
  try {
    const res = await fetch('/api/export/csv');
    if (!res.ok) throw new Error('Export failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (currentDatasetName || 'family_tree') + '.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showStatus('loadStatus', 'Saved!', false);
  } catch (e) {
    showStatus('loadStatus', 'Error saving: ' + e.message, true);
  }
}

// ── Load Data: File Upload ──

function setupDropZone() {
  const zone = document.getElementById('dropZone');
  if (!zone) return;
  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });
}

function onFileSelected(input) {
  const file = input.files[0];
  if (file) uploadFile(file);
  input.value = '';  // reset so same file can be re-selected
}

async function uploadFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['csv', 'txt', 'db'].includes(ext)) {
    showStatus('loadStatus', `Unsupported file type: .${ext}. Use .csv, .txt, or .db`, true);
    return;
  }
  document.getElementById('dropLabel').textContent = `Importing ${file.name}...`;
  showStatus('loadStatus', 'Importing...', false);
  try {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch('/api/import/upload', { method: 'POST', body: form });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    document.getElementById('dropLabel').textContent = `Loaded: ${file.name}`;
    setDatasetName(data.dataset_name || file.name.replace(/\.[^.]+$/, ''));
    showImportReport(data);
    await refresh();
  } catch (e) {
    document.getElementById('dropLabel').textContent = 'Click or drag a file here';
    showStatus('loadStatus', 'Error: ' + e.message, true);
  }
}

// ── Import Report ──

function showImportReport(data) {
  const section = document.getElementById('importReportSection');
  const summary = document.getElementById('importSummary');
  const fixesDiv = document.getElementById('importFixes');
  const fixesList = document.getElementById('fixesList');
  const errorsDiv = document.getElementById('importErrors');
  const errorsList = document.getElementById('errorsList');

  summary.innerHTML = `<strong>${data.people}</strong> people, <strong>${data.relationships}</strong> relationships imported.`;

  const fixes = data.auto_fixes || [];
  const errors = data.errors || [];

  if (fixes.length > 0) {
    fixesDiv.style.display = 'block';
    fixesList.innerHTML = fixes.map(f =>
      `<li>${f.line ? `<span class="line-num">Line ${f.line}:</span>` : ''}${escapeHtml(f.message)}</li>`
    ).join('');
  } else {
    fixesDiv.style.display = 'none';
  }

  if (errors.length > 0) {
    errorsDiv.style.display = 'block';
    errorsList.innerHTML = errors.map(e => {
      let actions = '';
      if (e.type === 'ambiguous_parent' && e.candidates) {
        actions = `<br><span style="font-size:11px;color:#888">Candidates: ${e.candidates.map(c => escapeHtml(c)).join(', ')}</span>`;
        // Add a "find in graph" link for each candidate
        actions += '<br>' + e.candidates.map(c => {
          const person = people.find(p => p.display_name === c);
          if (person) {
            return `<a href="#" onclick="navigateToPerson('${person.id}');return false" style="font-size:11px;color:#3498db">Find "${escapeHtml(c)}"</a>`;
          }
          return '';
        }).filter(Boolean).join(' | ');
      }
      return `<li>${e.line ? `<span class="line-num">Line ${e.line}:</span>` : ''}${escapeHtml(e.message)}${actions}</li>`;
    }).join('');
  } else {
    errorsDiv.style.display = 'none';
  }

  if (fixes.length === 0 && errors.length === 0) {
    summary.innerHTML += ' <span style="color:#27ae60">No issues detected.</span>';
  }

  section.style.display = 'block';
  showStatus('loadStatus', errors.length > 0
    ? `Imported with ${errors.length} issue(s) — see report below`
    : `Import complete`, errors.length > 0);
}

// ── Spouse-Children Merge Report ──

function showSpouseMergeReport(data) {
  if (!data.merged_children) return;
  const mc = data.merged_children;
  const parts = [];
  if (mc.merged && mc.merged.length > 0) {
    parts.push(`Merged ${mc.merged.length} duplicate child(ren): ${mc.merged.map(m => m.name).join(', ')}`);
  }
  if (mc.shared_with_a && mc.shared_with_a.length > 0) {
    parts.push(`Linked ${mc.shared_with_a.length} child(ren) to both parents: ${mc.shared_with_a.join(', ')}`);
  }
  if (mc.shared_with_b && mc.shared_with_b.length > 0) {
    parts.push(`Linked ${mc.shared_with_b.length} child(ren) to both parents: ${mc.shared_with_b.join(', ')}`);
  }
  if (parts.length > 0) {
    alert('Spouse children resolved:\n\n' + parts.join('\n'));
  }
}

// ── Helpers ──

function computeGenerations(nodes, edges) {
  // Build adjacency: parent -> children (PARENT_OF edges: source=parent, target=child)
  const children = {};
  const parents = {};
  const nodeIds = new Set(nodes.map(n => n.data.id));
  for (const id of nodeIds) { children[id] = []; parents[id] = []; }
  for (const e of edges) {
    if (e.data.type === 'PARENT_OF') {
      children[e.data.source].push(e.data.target);
      parents[e.data.target].push(e.data.source);
    }
  }
  // Find roots (no parents)
  const roots = [...nodeIds].filter(id => parents[id].length === 0);
  // BFS from roots
  const gen = {};
  const queue = roots.map(id => { gen[id] = 0; return id; });
  while (queue.length > 0) {
    const id = queue.shift();
    for (const child of children[id]) {
      if (!(child in gen) || gen[child] < gen[id] + 1) {
        gen[child] = gen[id] + 1;
        queue.push(child);
      }
    }
  }
  // Assign gen 0 to any remaining unassigned nodes
  for (const id of nodeIds) {
    if (!(id in gen)) gen[id] = 0;
  }
  return gen;
}

function getPersonById(id) {
  return people.find(p => p.id === id);
}

async function refresh() {
  await loadPeople();
  await loadGraph();
}

// ── Layout: Parent-centered family tree ──

function runFamilyLayout(animate) {
  if (!cy || cy.nodes().length === 0) return;

  const NODE_GAP = 70;   // horizontal gap between siblings
  const RANK_GAP = 160;  // vertical gap between generations
  const SPOUSE_GAP = 50;  // offset for spouse nodes

  // Build parent-child adjacency from PARENT_OF edges only
  const childrenOf = {};
  const parentOf = {};
  cy.nodes().forEach(n => { childrenOf[n.id()] = []; });
  cy.edges().forEach(e => {
    if (e.data('type') === 'PARENT_OF') {
      childrenOf[e.data('source')].push(e.data('target'));
      if (!parentOf[e.data('target')]) parentOf[e.data('target')] = e.data('source');
    }
  });

  // Sort children alphabetically for stable layout
  for (const id in childrenOf) {
    childrenOf[id].sort((a, b) => {
      const na = cy.getElementById(a).data('label') || '';
      const nb = cy.getElementById(b).data('label') || '';
      return na.localeCompare(nb);
    });
  }

  // Compute generation depth
  const depth = {};
  function setDepth(id, d) {
    if (depth[id] === undefined || d > depth[id]) {
      depth[id] = d;
      childrenOf[id].forEach(kid => setDepth(kid, d + 1));
    }
  }

  // Find roots (no PARENT_OF edge pointing to them)
  const roots = Object.keys(childrenOf).filter(id => !parentOf[id] && childrenOf[id].length > 0);
  // Leaf-only nodes with no parent-child edges at all
  const isolated = Object.keys(childrenOf).filter(id => !parentOf[id] && childrenOf[id].length === 0);

  roots.forEach(r => setDepth(r, 0));

  // Position subtree recursively: children first, then center parent
  const positions = {};
  function positionSubtree(id, xStart) {
    const kids = childrenOf[id];
    if (kids.length === 0) {
      positions[id] = { x: xStart, y: (depth[id] || 0) * RANK_GAP };
      return xStart + NODE_GAP;
    }
    let x = xStart;
    for (const kid of kids) {
      x = positionSubtree(kid, x);
    }
    // Center parent over its children
    const firstX = positions[kids[0]].x;
    const lastX = positions[kids[kids.length - 1]].x;
    positions[id] = { x: (firstX + lastX) / 2, y: (depth[id] || 0) * RANK_GAP };
    return x;
  }

  // Sort roots: largest subtree first
  function treeSize(id) {
    let s = 1;
    childrenOf[id].forEach(k => { s += treeSize(k); });
    return s;
  }
  roots.sort((a, b) => treeSize(b) - treeSize(a));

  // Position each root's tree
  let xOffset = 0;
  for (const root of roots) {
    xOffset = positionSubtree(root, xOffset) + NODE_GAP;
  }

  // Place spouse-connected nodes next to their partner
  cy.edges().forEach(e => {
    if (e.data('type') === 'SPOUSE_OF') {
      const s = e.data('source'), t = e.data('target');
      if (positions[s] && !positions[t]) {
        depth[t] = depth[s] || 0;
        positions[t] = { x: positions[s].x + SPOUSE_GAP, y: positions[s].y };
      } else if (positions[t] && !positions[s]) {
        depth[s] = depth[t] || 0;
        positions[s] = { x: positions[t].x - SPOUSE_GAP, y: positions[t].y };
      }
    }
  });

  // Any remaining unpositioned nodes (isolated)
  isolated.forEach(id => {
    if (!positions[id]) {
      depth[id] = 0;
      positions[id] = { x: xOffset, y: 0 };
      xOffset += NODE_GAP;
    }
  });

  // Apply positions
  if (animate) {
    cy.nodes().forEach(n => {
      const p = positions[n.id()];
      if (p) n.animate({ position: p }, { duration: 500 });
    });
    setTimeout(() => cy.fit(40), 600);
  } else {
    cy.nodes().forEach(n => {
      const p = positions[n.id()];
      if (p) n.position(p);
    });
    cy.fit(40);
  }
}

function resetLayout() {
  if (!cy) return;
  runFamilyLayout(true);
  layoutDirty = false;
  document.getElementById('resetBtn').style.display = 'none';
}

function onNodeDrag() {
  if (!layoutDirty) {
    layoutDirty = true;
    document.getElementById('resetBtn').style.display = 'block';
  }
}

// ── Modal helpers ──

function openModal(id) {
  document.getElementById(id).classList.add('open');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

function populateModalDropdowns(fromId, toId) {
  const opts = people.map(p => `<option value="${p.id}">${p.display_name}</option>`).join('');
  document.getElementById('modalRelFrom').innerHTML = opts;
  document.getElementById('modalRelTo').innerHTML = opts;
  if (fromId) document.getElementById('modalRelFrom').value = fromId;
  if (toId) document.getElementById('modalRelTo').value = toId;
}

// ── Context Menu: show/hide ──

function hideAllMenus() {
  document.querySelectorAll('.ctx-menu').forEach(m => m.classList.remove('open'));
}

function showMenu(menuId, x, y) {
  hideAllMenus();
  const menu = document.getElementById(menuId);
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';
  menu.classList.add('open');
}

document.addEventListener('click', hideAllMenus);

// ── Context Menu: Node actions ──

function ctxEditPerson() {
  hideAllMenus();
  if (!ctxTargetNode) return;
  const id = ctxTargetNode.data('id');
  const person = getPersonById(id);
  if (!person) return;
  document.getElementById('editPersonId').value = person.id;
  document.getElementById('editPersonName').value = person.display_name;
  document.getElementById('editPersonSex').value = person.sex;
  document.getElementById('editPersonNotes').value = person.notes || '';
  document.getElementById('editModalTitle').textContent = 'Edit Person';
  openModal('editPersonModal');
}

async function saveEditPerson() {
  const id = document.getElementById('editPersonId').value;
  const display_name = document.getElementById('editPersonName').value.trim();
  const sex = document.getElementById('editPersonSex').value;
  const notes = document.getElementById('editPersonNotes').value.trim() || null;
  if (!display_name) return;
  try {
    const res = await fetch(`/people/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name, sex, notes })
    });
    if (!res.ok) throw new Error(await res.text());
    closeModal('editPersonModal');
    await refresh();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function ctxDeletePerson() {
  hideAllMenus();
  if (!ctxTargetNode) return;
  const id = ctxTargetNode.data('id');
  const label = ctxTargetNode.data('label');
  if (!confirm(`Delete "${label}" and all their relationships?`)) return;
  try {
    const res = await fetch(`/people/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    await refresh();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

function ctxAddRelFrom() {
  hideAllMenus();
  if (!ctxTargetNode) return;
  populateModalDropdowns(ctxTargetNode.data('id'), null);
  openModal('addRelModal');
}

function ctxAddRelTo() {
  hideAllMenus();
  if (!ctxTargetNode) return;
  populateModalDropdowns(null, ctxTargetNode.data('id'));
  openModal('addRelModal');
}

async function saveModalRelationship() {
  const from_person_id = document.getElementById('modalRelFrom').value;
  const to_person_id = document.getElementById('modalRelTo').value;
  const type = document.getElementById('modalRelType').value;
  if (!from_person_id || !to_person_id) return;
  if (from_person_id === to_person_id) { alert('Cannot relate a person to themselves'); return; }
  try {
    const res = await fetch('/relationships', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_person_id, to_person_id, type })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    closeModal('addRelModal');
    showSpouseMergeReport(data);
    await refresh();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Context Menu: Edge actions ──

async function ctxDeleteRelationship() {
  hideAllMenus();
  if (!ctxTargetEdge) return;
  const id = ctxTargetEdge.data('id');
  if (!confirm('Delete this relationship?')) return;
  try {
    const res = await fetch(`/relationships/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    await refresh();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Context Menu: Background actions ──

function ctxAddPersonHere() {
  hideAllMenus();
  document.getElementById('modalPersonName').value = '';
  document.getElementById('modalPersonSex').value = 'M';
  document.getElementById('modalPersonNotes').value = '';
  openModal('addPersonModal');
}

async function saveModalPerson() {
  const name = document.getElementById('modalPersonName').value.trim();
  if (!name) return;
  const sex = document.getElementById('modalPersonSex').value;
  const notes = document.getElementById('modalPersonNotes').value.trim() || null;
  try {
    const res = await fetch('/people', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, sex, notes })
    });
    if (!res.ok) throw new Error(await res.text());
    closeModal('addPersonModal');
    await refresh();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Graph rendering ──

async function loadGraph() {
  const res = await fetch('/graph');
  const data = await res.json();
  const emptyState = document.getElementById('emptyState');
  const resetBtn = document.getElementById('resetBtn');

  if (data.nodes.length === 0) {
    if (emptyState) emptyState.style.display = 'flex';
    if (resetBtn) resetBtn.style.display = 'none';
    if (cy) { cy.destroy(); cy = null; }
    return;
  }

  if (emptyState) emptyState.style.display = 'none';
  layoutDirty = false;
  if (resetBtn) resetBtn.style.display = 'none';

  const elements = [];
  const generations = computeGenerations(data.nodes, data.edges);

  data.nodes.forEach(n => {
    const gen = generations[n.data.id] || 0;
    const color = GEN_COLORS[gen % GEN_COLORS.length];
    elements.push({ data: { id: n.data.id, label: n.data.label, gen, color } });
  });

  data.edges.forEach(e => {
    elements.push({
      data: { id: e.data.id, source: e.data.source, target: e.data.target, type: e.data.type }
    });
  });

  if (cy) cy.destroy();

  cy = cytoscape({
    container: document.getElementById('cy'),
    elements,
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(label)',
          'text-valign': 'bottom',
          'text-margin-y': 8,
          'text-wrap': 'wrap',
          'text-max-width': 120,
          'font-size': 13,
          'font-weight': 600,
          'color': '#333',
          'text-outline-color': '#fff',
          'text-outline-width': 2,
          'width': 50,
          'height': 50,
          'border-width': 3,
          'border-color': '#fff',
          'background-color': 'data(color)'
        }
      },
      {
        selector: 'node:selected',
        style: {
          'border-color': '#f39c12',
          'border-width': 4,
          'overlay-opacity': 0.1,
          'overlay-color': '#f39c12'
        }
      },
      {
        selector: 'node.search-match',
        style: {
          'border-color': '#f39c12',
          'border-width': 4,
          'width': 60,
          'height': 60,
          'font-size': 15,
          'z-index': 10
        }
      },
      {
        selector: 'node.search-dimmed',
        style: { 'opacity': 0.15 }
      },
      {
        selector: 'edge.search-dimmed',
        style: { 'opacity': 0.08 }
      },
      {
        selector: 'edge[type="PARENT_OF"]',
        style: {
          'width': 2.5,
          'line-color': '#7f8c8d',
          'target-arrow-color': '#7f8c8d',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'arrow-scale': 1.2
        }
      },
      {
        selector: 'edge[type="SPOUSE_OF"]',
        style: {
          'width': 2,
          'line-color': '#e74c3c',
          'line-style': 'dashed',
          'curve-style': 'bezier'
        }
      },
      {
        selector: 'edge[type="SIBLING_OF"]',
        style: {
          'width': 1.5,
          'line-color': '#27ae60',
          'line-style': 'dotted',
          'curve-style': 'bezier'
        }
      },
      {
        selector: 'edge:selected',
        style: {
          'width': 4,
          'line-color': '#f39c12',
          'target-arrow-color': '#f39c12'
        }
      }
    ],
    layout: { name: 'preset' },  // we run layout manually below
    minZoom: 0.2,
    maxZoom: 3,
    wheelSensitivity: 0.3
  });

  // Run custom parent-centered layout (siblings always grouped under parent)
  runFamilyLayout(false);

  // Show reset button when a node is dragged
  cy.on('dragfree', 'node', onNodeDrag);

  // Context menu events
  cy.on('cxttap', 'node', function(evt) {
    evt.originalEvent.preventDefault();
    ctxTargetNode = evt.target;
    ctxTargetEdge = null;
    showMenu('ctxNode', evt.originalEvent.clientX, evt.originalEvent.clientY);
  });

  cy.on('cxttap', 'edge', function(evt) {
    evt.originalEvent.preventDefault();
    ctxTargetEdge = evt.target;
    ctxTargetNode = null;
    showMenu('ctxEdge', evt.originalEvent.clientX, evt.originalEvent.clientY);
  });

  cy.on('cxttap', function(evt) {
    if (evt.target === cy) {
      evt.originalEvent.preventDefault();
      ctxTargetNode = null;
      ctxTargetEdge = null;
      showMenu('ctxBg', evt.originalEvent.clientX, evt.originalEvent.clientY);
    }
  });

  // Double-click node to edit
  cy.on('dbltap', 'node', function(evt) {
    ctxTargetNode = evt.target;
    ctxEditPerson();
  });
}

// ── Initialize ──

setupDropZone();
loadAvailableDatasets();
loadPeople().then(async () => {
  await loadGraph();
  if (people.length > 0) {
    setDatasetName('Family Tree');
  }
});
