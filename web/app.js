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

// Track cursor position on the graph canvas for placing new nodes
let lastCtxPosition = null;

// ── Data loading ──

async function loadPeople() {
  const res = await fetch('/people');
  people = await res.json();
  const query = document.getElementById('searchInput') ? document.getElementById('searchInput').value.trim() : '';
  renderPeopleList(query);
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
    const newPerson = await res.json();
    document.getElementById('personName').value = '';
    document.getElementById('personNotes').value = '';
    showStatus('personStatus', `Added ${name}`, false);
    await refresh();
    highlightNewNode(newPerson.id);
  } catch (e) {
    showStatus('personStatus', 'Error: ' + e.message, true);
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
    `<div class="ds-item" onclick="this.querySelector('input').click()"><input type="checkbox" id="ds_${i}" value="${escapeHtml(ds.filename)}" onclick="event.stopPropagation()"><span style="cursor:pointer;color:#333;font-size:13px">${escapeHtml(ds.name)}</span></div>`
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
  updateSharingSection();
  if (name) loadShares();
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

// Flash-highlight a newly added node
function highlightNewNode(nodeId) {
  if (!cy) return;
  const node = cy.getElementById(nodeId);
  if (!node || node.empty()) return;
  node.addClass('new-node');
  setTimeout(() => node.removeClass('new-node'), 2500);
  cy.animate({ center: { eles: node }, zoom: cy.zoom() }, { duration: 300 });
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

function ctxAddChild() {
  hideAllMenus();
  if (!ctxTargetNode) return;
  const parentId = ctxTargetNode.data('id');
  const parentLabel = ctxTargetNode.data('label');
  document.getElementById('addChildParentId').value = parentId;
  document.getElementById('addChildModalTitle').textContent = `Add Child of ${parentLabel}`;
  document.getElementById('addChildName').value = '';
  document.getElementById('addChildSex').value = 'U';
  document.getElementById('addChildNotes').value = '';
  openModal('addChildModal');
}

async function saveAddChild() {
  const parentId = document.getElementById('addChildParentId').value;
  const name = document.getElementById('addChildName').value.trim();
  if (!name) return;
  const sex = document.getElementById('addChildSex').value;
  const notes = document.getElementById('addChildNotes').value.trim() || null;
  try {
    // Create the child person
    const res = await fetch('/people', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, sex, notes })
    });
    if (!res.ok) throw new Error(await res.text());
    const child = await res.json();
    // Create PARENT_OF relationship
    const relRes = await fetch('/relationships', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_person_id: parentId, to_person_id: child.id, type: 'PARENT_OF' })
    });
    if (!relRes.ok) throw new Error(await relRes.text());
    closeModal('addChildModal');
    await refresh();
    highlightNewNode(child.id);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Context Menu: Add Parent ──

let parentMode = 'new';  // 'new' or 'existing'

function setParentMode(mode) {
  parentMode = mode;
  document.getElementById('parentNewFields').style.display = mode === 'new' ? 'block' : 'none';
  document.getElementById('parentExistingFields').style.display = mode === 'existing' ? 'block' : 'none';
  document.getElementById('parentModeNew').className = mode === 'new' ? 'btn-primary' : 'btn-secondary';
  document.getElementById('parentModeExisting').className = mode === 'existing' ? 'btn-primary' : 'btn-secondary';
  if (mode === 'existing') {
    populateParentSelect('');
    document.getElementById('parentSearchInput').value = '';
  }
}

function populateParentSelect(query) {
  const childId = document.getElementById('addParentChildId').value;
  const q = (query || '').toLowerCase();
  const filtered = people.filter(p => p.id !== childId && (!q || p.display_name.toLowerCase().includes(q)));
  const sel = document.getElementById('parentExistingSelect');
  sel.innerHTML = filtered.map(p =>
    `<option value="${p.id}">${escapeHtml(p.display_name)} (${p.sex})</option>`
  ).join('');
}

function onParentSearchInput() {
  const query = document.getElementById('parentSearchInput').value.trim();
  populateParentSelect(query);
}

async function ctxAddParent() {
  hideAllMenus();
  if (!ctxTargetNode) return;
  const childId = ctxTargetNode.data('id');
  const childLabel = ctxTargetNode.data('label');
  // Check if already has a parent
  let existingParents = [];
  try {
    const res = await fetch(`/people/${childId}/parents`);
    existingParents = await res.json();
  } catch (e) { /* proceed */ }

  document.getElementById('addParentChildId').value = childId;
  document.getElementById('addParentName').value = '';
  document.getElementById('addParentNotes').value = '';
  document.getElementById('addParentSex').value = 'M';
  setParentMode('new');

  if (existingParents.length > 0) {
    const parentNames = existingParents.map(p => p.display_name).join(', ');
    if (!confirm(`"${childLabel}" already has a parent: ${parentNames}.\n\nDo you want to REPLACE the existing parent?`)) {
      return;
    }
    document.getElementById('addParentModalTitle').textContent = `Replace Parent of ${childLabel}`;
    document.getElementById('addParentSubmitBtn').textContent = 'Replace Parent';
    document.getElementById('addParentChildId').dataset.replace = 'true';
  } else {
    document.getElementById('addParentModalTitle').textContent = `Add Parent of ${childLabel}`;
    document.getElementById('addParentSubmitBtn').textContent = 'Add Parent';
    document.getElementById('addParentChildId').dataset.replace = 'false';
  }
  openModal('addParentModal');
}

async function saveAddParent() {
  const childId = document.getElementById('addParentChildId').value;
  // Build request body based on mode
  let body;
  if (parentMode === 'existing') {
    const selectedId = document.getElementById('parentExistingSelect').value;
    if (!selectedId) { alert('Select a person from the list'); return; }
    body = { existing_person_id: selectedId };
  } else {
    const name = document.getElementById('addParentName').value.trim();
    if (!name) { alert('Enter a name'); return; }
    body = {
      display_name: name,
      sex: document.getElementById('addParentSex').value,
      notes: document.getElementById('addParentNotes').value.trim() || null,
    };
  }
  try {
    const res = await fetch(`/people/${childId}/set-parent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to set parent');
    }
    const data = await res.json();
    closeModal('addParentModal');
    await refresh();
    highlightNewNode(data.parent.id);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Context Menu: Add Spouse ──

async function ctxAddSpouse() {
  hideAllMenus();
  if (!ctxTargetNode) return;
  const personId = ctxTargetNode.data('id');
  const personLabel = ctxTargetNode.data('label');
  // Check spouse count
  try {
    const res = await fetch(`/people/${personId}/relationship-counts`);
    const counts = await res.json();
    if (counts.spouses >= 1) {
      alert(`"${personLabel}" already has a spouse. Remove the existing spouse relationship first.`);
      return;
    }
  } catch (e) { /* proceed, server will validate */ }
  document.getElementById('addSpousePersonId').value = personId;
  document.getElementById('addSpouseModalTitle').textContent = `Add Spouse of ${personLabel}`;
  document.getElementById('addSpouseName').value = '';
  // Default to opposite sex of the person
  const person = getPersonById(personId);
  document.getElementById('addSpouseSex').value = person && person.sex === 'M' ? 'F' : 'M';
  document.getElementById('addSpouseNotes').value = '';
  openModal('addSpouseModal');
}

async function saveAddSpouse() {
  const personId = document.getElementById('addSpousePersonId').value;
  const name = document.getElementById('addSpouseName').value.trim();
  if (!name) return;
  const sex = document.getElementById('addSpouseSex').value;
  const notes = document.getElementById('addSpouseNotes').value.trim() || null;
  try {
    const res = await fetch('/people', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, sex, notes })
    });
    if (!res.ok) throw new Error(await res.text());
    const spouse = await res.json();
    const relRes = await fetch('/relationships', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_person_id: personId, to_person_id: spouse.id, type: 'SPOUSE_OF' })
    });
    if (!relRes.ok) {
      await fetch(`/people/${spouse.id}`, { method: 'DELETE' });
      throw new Error(await relRes.text());
    }
    const data = await relRes.json();
    closeModal('addSpouseModal');
    showSpouseMergeReport(data);
    await refresh();
    highlightNewNode(spouse.id);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Context Menu: Add Sibling (= child of same parents) ──

async function ctxAddSibling() {
  hideAllMenus();
  if (!ctxTargetNode) return;
  const personId = ctxTargetNode.data('id');
  const personLabel = ctxTargetNode.data('label');
  // Check if the person has parents — siblings must share parents
  try {
    const res = await fetch(`/people/${personId}/parents`);
    const parents = await res.json();
    if (parents.length === 0) {
      alert(`"${personLabel}" has no parents. Add a parent first, then add siblings.`);
      return;
    }
  } catch (e) { /* proceed */ }
  document.getElementById('addSiblingPersonId').value = personId;
  document.getElementById('addSiblingModalTitle').textContent = `Add Sibling of ${personLabel}`;
  document.getElementById('addSiblingName').value = '';
  document.getElementById('addSiblingSex').value = 'U';
  document.getElementById('addSiblingNotes').value = '';
  openModal('addSiblingModal');
}

async function saveAddSibling() {
  const personId = document.getElementById('addSiblingPersonId').value;
  const name = document.getElementById('addSiblingName').value.trim();
  if (!name) return;
  const sex = document.getElementById('addSiblingSex').value;
  const notes = document.getElementById('addSiblingNotes').value.trim() || null;
  try {
    // Get the target person's parents
    const parentsRes = await fetch(`/people/${personId}/parents`);
    const parents = await parentsRes.json();
    if (parents.length === 0) {
      alert('This person has no parents. Add a parent first.');
      return;
    }
    // Create the sibling person
    const res = await fetch('/people', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, sex, notes })
    });
    if (!res.ok) throw new Error(await res.text());
    const sibling = await res.json();
    // Add PARENT_OF from each parent to the new sibling
    for (const parent of parents) {
      const relRes = await fetch('/relationships', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from_person_id: parent.id, to_person_id: sibling.id, type: 'PARENT_OF' })
      });
      if (!relRes.ok) {
        await fetch(`/people/${sibling.id}`, { method: 'DELETE' });
        throw new Error(await relRes.text());
      }
    }
    closeModal('addSiblingModal');
    await refresh();
    highlightNewNode(sibling.id);
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
  const placementPos = lastCtxPosition;
  try {
    const res = await fetch('/people', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, sex, notes })
    });
    if (!res.ok) throw new Error(await res.text());
    const newPerson = await res.json();
    closeModal('addPersonModal');
    await refresh();
    // Place at cursor position and highlight
    if (cy && placementPos) {
      const node = cy.getElementById(newPerson.id);
      if (node && node.nonempty()) {
        node.position(placementPos);
      }
    }
    highlightNewNode(newPerson.id);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Sharing ──

let activeShareToken = null;

async function loadShares() {
  try {
    const res = await fetch('/api/shares');
    const shares = await res.json();
    renderShareLinks(shares);
  } catch (e) { /* ignore */ }
}

function renderShareLinks(shares) {
  const el = document.getElementById('shareLinks');
  if (!shares || shares.length === 0) {
    el.innerHTML = '<div style="font-size:13px;color:#999">No share links yet</div>';
    return;
  }
  el.innerHTML = shares.map(s => {
    const viewerCount = s.viewers ? s.viewers.length : 0;
    const active = s.token === activeShareToken ? ' style="background:#ebf5fb;border-left:3px solid #3498db;padding-left:5px"' : '';
    return `<div${active} style="padding:6px 0;font-size:13px;border-bottom:1px solid #eee;cursor:pointer" onclick="selectShare('${s.token}')">
      <strong>${escapeHtml(s.dataset)}</strong>
      <span style="color:#999;font-size:11px">${viewerCount} viewer(s)</span>
      <span onclick="event.stopPropagation();deleteShare('${s.token}')" style="float:right;color:#e74c3c;cursor:pointer;font-size:11px" title="Delete">&#10005;</span>
    </div>`;
  }).join('');
}

async function createShareLink() {
  if (!currentDatasetName) {
    alert('Load a dataset first');
    return;
  }
  try {
    const res = await fetch('/api/shares', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset: currentDatasetName })
    });
    const link = await res.json();
    activeShareToken = link.token;
    await loadShares();
    selectShare(link.token);
  } catch (e) {
    alert('Error creating share link: ' + e.message);
  }
}

async function deleteShare(token) {
  if (!confirm('Delete this share link? All viewers will lose access.')) return;
  try {
    await fetch(`/api/shares/${token}`, { method: 'DELETE' });
    if (activeShareToken === token) {
      activeShareToken = null;
      document.getElementById('shareDetail').style.display = 'none';
    }
    await loadShares();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function selectShare(token) {
  activeShareToken = token;
  const detail = document.getElementById('shareDetail');
  detail.style.display = 'block';
  const url = `${window.location.origin}/view/${token}`;
  document.getElementById('shareLinkUrl').value = url;
  await loadShares();
  await loadViewers(token);
  await loadAccessLog(token);
}

function copyShareLink() {
  const input = document.getElementById('shareLinkUrl');
  navigator.clipboard.writeText(input.value).then(() => {
    const btn = input.nextElementSibling;
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
  });
}

async function loadViewers(token) {
  try {
    const res = await fetch(`/api/shares/${token}/viewers`);
    const viewers = await res.json();
    const ul = document.getElementById('viewerList');
    if (viewers.length === 0) {
      ul.innerHTML = '<li style="color:#999;font-size:12px">No viewers added yet</li>';
      return;
    }
    ul.innerHTML = viewers.map(v =>
      `<li style="font-size:12px;display:flex;justify-content:space-between;align-items:center">
        <span>${escapeHtml(v.email)}${v.name ? ' (' + escapeHtml(v.name) + ')' : ''}</span>
        <span onclick="removeViewer('${activeShareToken}','${v.id}')" style="color:#e74c3c;cursor:pointer;font-size:11px" title="Remove">&#10005;</span>
      </li>`
    ).join('');
  } catch (e) { /* ignore */ }
}

async function addViewer() {
  if (!activeShareToken) return;
  const email = document.getElementById('viewerEmail').value.trim();
  if (!email) return;
  try {
    const res = await fetch(`/api/shares/${activeShareToken}/viewers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    if (!res.ok) throw new Error(await res.text());
    document.getElementById('viewerEmail').value = '';
    await loadViewers(activeShareToken);
    await loadShares();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function removeViewer(token, viewerId) {
  try {
    await fetch(`/api/shares/${token}/viewers/${viewerId}`, { method: 'DELETE' });
    await loadViewers(token);
    await loadShares();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function loadAccessLog(token) {
  try {
    const res = await fetch(`/api/shares/${token}/access-log`);
    const logs = await res.json();
    const ul = document.getElementById('accessLog');
    if (logs.length === 0) {
      ul.innerHTML = '<li style="color:#999;font-size:11px">No views yet</li>';
      return;
    }
    ul.innerHTML = logs.map(l => {
      const date = new Date(l.viewed_at).toLocaleString();
      return `<li style="font-size:11px"><strong>${escapeHtml(l.email)}</strong> — ${date}${l.ip ? ' from ' + l.ip : ''}</li>`;
    }).join('');
  } catch (e) { /* ignore */ }
}

function updateSharingSection() {
  const section = document.getElementById('sharingSection');
  if (section) section.style.display = currentDatasetName ? 'block' : 'none';
}

// ── Export graph as image ──

function exportGraphPng() {
  if (!cy || cy.nodes().length === 0) return;
  const png = cy.png({ full: true, scale: 2, bg: '#fafafa' });
  const a = document.createElement('a');
  a.href = png;
  a.download = (currentDatasetName || 'family_tree') + '.png';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function exportGraphSvg() {
  if (!cy || cy.nodes().length === 0) return;
  const svgContent = cy.svg({ full: true, scale: 1, bg: '#fafafa' });
  const blob = new Blob([svgContent], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = (currentDatasetName || 'family_tree') + '.svg';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function updateExportButtons(hasNodes) {
  const pngBtn = document.getElementById('exportPngBtn');
  const svgBtn = document.getElementById('exportSvgBtn');
  if (pngBtn) pngBtn.style.display = hasNodes ? 'inline-block' : 'none';
  if (svgBtn) svgBtn.style.display = hasNodes ? 'inline-block' : 'none';
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
    updateExportButtons(false);
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
        selector: 'node.new-node',
        style: {
          'border-color': '#f1c40f',
          'border-width': 6,
          'width': 70,
          'height': 70,
          'font-size': 16,
          'z-index': 999,
          'overlay-opacity': 0.2,
          'overlay-color': '#f1c40f'
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
  updateExportButtons(true);

  // Show reset button when a node is dragged
  cy.on('dragfree', 'node', onNodeDrag);

  // Context menu events
  cy.on('cxttap', 'node', async function(evt) {
    evt.originalEvent.preventDefault();
    ctxTargetNode = evt.target;
    ctxTargetEdge = null;
    // Fetch relationship counts to enable/disable menu items
    const parentItem = document.getElementById('ctxAddParentItem');
    const spouseItem = document.getElementById('ctxAddSpouseItem');
    const siblingItem = document.getElementById('ctxAddSiblingItem');
    parentItem.className = 'ctx-item';
    parentItem.innerHTML = '<span class="ctx-icon">&#x1F464;</span> Add Parent';
    spouseItem.className = 'ctx-item';
    siblingItem.className = 'ctx-item';
    try {
      const res = await fetch(`/people/${evt.target.data('id')}/relationship-counts`);
      const counts = await res.json();
      if (counts.parents >= 1) {
        parentItem.innerHTML = '<span class="ctx-icon">&#x1F504;</span> Replace Parent';
      }
      if (counts.parents === 0) {
        siblingItem.className = 'ctx-item disabled';
        siblingItem.title = 'Add a parent first';
      }
      if (counts.spouses >= 1) spouseItem.className = 'ctx-item disabled';
    } catch (e) { /* show enabled by default */ }
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
      lastCtxPosition = evt.position;  // graph-space coords for placing new node
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
