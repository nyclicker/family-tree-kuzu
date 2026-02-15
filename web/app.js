let cy = null;
let people = [];
let selectedPersonId = null;
let currentDatasetName = '';

// Auth & tree state
let currentUser = null;
let currentTreeId = null;
let currentTreeRole = null;
let userTrees = [];

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

// Track comment IDs created in this session (for delete eligibility)
const sessionCommentIds = new Set();

// Track cursor position on the graph canvas for placing new nodes
let lastCtxPosition = null;

// ── Sidebar toggle ──

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  const collapsed = sidebar.classList.toggle('collapsed');
  overlay.classList.toggle('open', !collapsed);
  localStorage.setItem('sidebarCollapsed', collapsed ? '1' : '');
}

function initSidebar() {
  const sidebar = document.getElementById('sidebar');
  const isMobile = window.innerWidth <= 768;
  const saved = localStorage.getItem('sidebarCollapsed');
  // On mobile, default collapsed; on desktop, respect saved preference
  if (isMobile || saved === '1') {
    sidebar.classList.add('collapsed');
  }
}

// ── API URL helper ──

function treeApi(path) {
  return `/api/trees/${currentTreeId}${path}`;
}

function canEdit() {
  return currentTreeRole === 'owner' || currentTreeRole === 'editor';
}

function isOwner() {
  return currentTreeRole === 'owner';
}

// ══════════════════════════════════════════════════════════
// AUTH
// ══════════════════════════════════════════════════════════

function showAuthTab(tab) {
  document.getElementById('loginForm').style.display = tab === 'login' ? 'block' : 'none';
  document.getElementById('registerForm').style.display = tab === 'register' ? 'block' : 'none';
  document.getElementById('tabLogin').className = 'auth-tab' + (tab === 'login' ? ' active' : '');
  document.getElementById('tabRegister').className = 'auth-tab' + (tab === 'register' ? ' active' : '');
  document.getElementById('authError').style.display = 'none';
}

function showAuthError(msg) {
  const el = document.getElementById('authError');
  el.textContent = msg;
  el.style.display = 'block';
}

async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me');
    if (res.ok) {
      currentUser = await res.json();
      showApp();
      return;
    }
  } catch (e) { /* not authenticated */ }
  showLogin();
}

function showLogin() {
  document.getElementById('authScreen').style.display = 'flex';
  document.getElementById('mainApp').style.display = 'none';
  // Clear all auth form fields for safety
  document.getElementById('loginEmail').value = '';
  document.getElementById('loginPassword').value = '';
  document.getElementById('regName').value = '';
  document.getElementById('regEmail').value = '';
  document.getElementById('regPassword').value = '';
  document.getElementById('regSetupToken').value = '';
  document.getElementById('authError').style.display = 'none';
  // Always reset to login tab
  showAuthTab('login');
  // Hide setup token field by default, only show if needed
  checkSetupStatus();
}

async function checkSetupStatus() {
  try {
    const res = await fetch('/api/auth/setup-status');
    if (res.ok) {
      const data = await res.json();
      document.getElementById('setupTokenGroup').style.display = data.needs_setup ? 'block' : 'none';
    }
  } catch (e) {
    // Hide by default if we can't check
    document.getElementById('setupTokenGroup').style.display = 'none';
  }
}

function showApp() {
  document.getElementById('authScreen').style.display = 'none';
  document.getElementById('mainApp').style.display = 'block';
  document.getElementById('userEmail').textContent = currentUser.email;
  const adminBtn = document.getElementById('adminBtn');
  if (adminBtn) adminBtn.style.display = currentUser.is_admin ? 'inline-block' : 'none';
  initSidebar();
  initApp();
}

async function doLogin() {
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  if (!email || !password) { showAuthError('Email and password are required'); return; }
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    if (!res.ok) {
      const err = await res.json();
      showAuthError(err.detail || 'Login failed');
      return;
    }
    currentUser = await res.json();
    showApp();
  } catch (e) {
    showAuthError('Connection error');
  }
}

async function doRegister() {
  const display_name = document.getElementById('regName').value.trim();
  const email = document.getElementById('regEmail').value.trim();
  const password = document.getElementById('regPassword').value;
  const setup_token = document.getElementById('regSetupToken').value.trim();
  if (!display_name || !email || !password) {
    showAuthError('All fields are required');
    return;
  }
  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name, email, password, setup_token: setup_token || null })
    });
    if (!res.ok) {
      const err = await res.json();
      showAuthError(err.detail || 'Registration failed');
      return;
    }
    currentUser = await res.json();
    showApp();
  } catch (e) {
    showAuthError('Connection error');
  }
}

async function doLogout() {
  await fetch('/api/auth/logout', { method: 'POST' });
  currentUser = null;
  currentTreeId = null;
  currentTreeRole = null;
  if (cy) { cy.destroy(); cy = null; }
  showLogin();
}

// ══════════════════════════════════════════════════════════
// APP INITIALIZATION
// ══════════════════════════════════════════════════════════

let appInitialized = false;

function initApp() {
  if (!appInitialized) {
    setupDropZone();
    setupWelcomeDropZone();
    appInitialized = true;
  }
  loadTrees();
}

// ══════════════════════════════════════════════════════════
// TREE MANAGEMENT
// ══════════════════════════════════════════════════════════

async function loadTrees() {
  try {
    const res = await fetch('/api/trees');
    if (!res.ok) return;
    userTrees = await res.json();
    renderTreeList();
    // Auto-select if we had a tree selected or there's only one
    if (currentTreeId) {
      const found = userTrees.find(t => t.id === currentTreeId);
      if (found) {
        selectTree(found.id, found.role);
        return;
      }
    }
    if (userTrees.length === 1) {
      selectTree(userTrees[0].id, userTrees[0].role);
    } else if (userTrees.length === 0) {
      currentTreeId = null;
      currentTreeRole = null;
      updateTreeUI();
    }
  } catch (e) { /* ignore */ }
}

function renderTreeList() {
  const ul = document.getElementById('treeList');
  if (userTrees.length === 0) {
    ul.innerHTML = '<li style="color:#999;padding:8px">No trees yet. Create one to get started.</li>';
    return;
  }
  ul.innerHTML = userTrees.map(t => {
    const active = t.id === currentTreeId ? ' active' : '';
    return `<li class="tree-item${active}" onclick="selectTree('${t.id}','${t.role}')">
      <span class="tree-name">${escapeHtml(t.name)}</span>
      <span class="tree-role">${t.role}</span>
    </li>`;
  }).join('');
}

function selectTree(treeId, role) {
  currentTreeId = treeId;
  currentTreeRole = role;
  const tree = userTrees.find(t => t.id === treeId);
  currentDatasetName = tree ? tree.name : '';
  renderTreeList();
  updateTreeUI();
  refresh();
  if (isOwner()) {
    loadShares();
    loadMembers();
  }
}

function updateTreeUI() {
  const hasTree = !!currentTreeId;
  const hasTrees = userTrees.length > 0;
  // Header label
  const headerLabel = document.getElementById('datasetLabel');
  if (headerLabel) {
    const tree = userTrees.find(t => t.id === currentTreeId);
    headerLabel.textContent = tree ? ` — ${tree.name}` : '';
  }
  // Welcome vs Tree selector
  const welcomeSection = document.getElementById('welcomeSection');
  const treeSection = document.getElementById('treeSection');
  if (welcomeSection) welcomeSection.style.display = !hasTrees ? 'block' : 'none';
  if (treeSection) treeSection.style.display = hasTrees ? 'block' : 'none';

  // Show/hide sections based on tree selection and role
  const dataSection = document.getElementById('dataSection');
  const addPersonSection = document.getElementById('addPersonSection');
  const sharingSection = document.getElementById('sharingSection');
  const membersSection = document.getElementById('membersSection');
  const searchSection = document.getElementById('searchSection');

  if (dataSection) dataSection.style.display = hasTree && canEdit() ? 'block' : 'none';
  if (addPersonSection) addPersonSection.style.display = hasTree && canEdit() ? 'block' : 'none';
  if (sharingSection) sharingSection.style.display = hasTree && isOwner() ? 'block' : 'none';
  if (membersSection) membersSection.style.display = hasTree && isOwner() ? 'block' : 'none';
  if (searchSection) searchSection.style.display = hasTree ? 'block' : 'none';

  // Save/Clear buttons
  const saveBtn = document.getElementById('saveBtn');
  const clearBtn = document.getElementById('clearBtn');
  if (saveBtn) saveBtn.style.display = hasTree ? 'inline-block' : 'none';
  if (clearBtn) clearBtn.style.display = hasTree && isOwner() ? 'inline-block' : 'none';
  // History button
  const historyBtn = document.getElementById('historyBtn');
  if (historyBtn) historyBtn.style.display = hasTree ? 'inline-block' : 'none';
  // Close history panel when switching trees
  const historyPanel = document.getElementById('historyPanel');
  if (historyPanel) historyPanel.classList.remove('open');
}

function openCreateTreeModal() {
  document.getElementById('newTreeName').value = '';
  openModal('createTreeModal');
}

async function createTree() {
  const name = document.getElementById('newTreeName').value.trim();
  if (!name) return;
  try {
    const res = await fetch('/api/trees', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    if (!res.ok) throw new Error(await res.text());
    const tree = await res.json();
    closeModal('createTreeModal');
    await loadTrees();
    selectTree(tree.id, 'owner');
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ══════════════════════════════════════════════════════════
// DATA LOADING
// ══════════════════════════════════════════════════════════

async function loadPeople() {
  if (!currentTreeId) {
    people = [];
    const query = document.getElementById('searchInput') ? document.getElementById('searchInput').value.trim() : '';
    renderPeopleList(query);
    return;
  }
  const res = await fetch(treeApi('/people'));
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

function onSidebarDeathDateChange() {
  if (document.getElementById('personDeathDate').value) {
    document.getElementById('personDeceased').checked = true;
  }
}

async function addPerson() {
  if (!currentTreeId || !canEdit()) return;
  const name = document.getElementById('personName').value.trim();
  if (!name) { showStatus('personStatus', 'Name is required', true); return; }
  const sex = document.getElementById('personSex').value;
  const notes = document.getElementById('personNotes').value.trim() || null;
  const birth_date = document.getElementById('personBirthDate').value || null;
  const death_date = document.getElementById('personDeathDate').value || null;
  const is_deceased = document.getElementById('personDeceased').checked || null;
  try {
    const res = await fetch(treeApi('/people'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, sex, notes, birth_date, death_date, is_deceased })
    });
    if (!res.ok) throw new Error(await res.text());
    const newPerson = await res.json();
    document.getElementById('personName').value = '';
    document.getElementById('personNotes').value = '';
    document.getElementById('personBirthDate').value = '';
    document.getElementById('personDeathDate').value = '';
    document.getElementById('personDeceased').checked = false;
    showStatus('personStatus', `Added ${name}`, false);
    await refresh();
    highlightNewNode(newPerson.id);
  } catch (e) {
    showStatus('personStatus', 'Error: ' + e.message, true);
  }
}


// ── Import helpers ──

async function ensureTreeForImport(nameFallback) {
  if (currentTreeId) return currentTreeId;
  // Auto-create a tree named after the import
  const treeName = nameFallback || 'Imported Tree';
  const res = await fetch('/api/trees', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: treeName })
  });
  if (!res.ok) throw new Error('Failed to create tree');
  const tree = await res.json();
  await loadTrees();
  selectTree(tree.id, 'owner');
  return tree.id;
}

async function clearData() {
  if (!currentTreeId || !isOwner()) return;
  if (!confirm('Clear all data from this tree? This cannot be undone.')) return;
  try {
    await fetch(treeApi('/clear'), { method: 'POST' });
    document.getElementById('importReportSection').style.display = 'none';
    await refresh();
    showStatus('loadStatus', 'All data cleared', false);
  } catch (e) {
    showStatus('loadStatus', 'Error: ' + e.message, true);
  }
}

async function saveChanges() {
  if (!currentTreeId) return;
  try {
    const res = await fetch(treeApi('/export/csv'));
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

function setupWelcomeDropZone() {
  const zone = document.getElementById('welcomeDropZone');
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
  input.value = '';
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
    await ensureTreeForImport(file.name.replace(/\.[^.]+$/, ''));
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(treeApi('/import/upload'), { method: 'POST', body: form });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    document.getElementById('dropLabel').textContent = `Loaded: ${file.name}`;
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
  const roots = [...nodeIds].filter(id => parents[id].length === 0);
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
  for (const id of nodeIds) {
    if (!(id in gen)) gen[id] = 0;
  }
  return gen;
}

function getPersonById(id) {
  return people.find(p => p.id === id);
}

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

  const NODE_GAP = 140;
  const RANK_GAP = 220;
  const SPOUSE_GAP = 70;

  const childrenOf = {};
  const parentOf = {};
  cy.nodes().forEach(n => { childrenOf[n.id()] = []; });
  cy.edges().forEach(e => {
    if (e.data('type') === 'PARENT_OF') {
      childrenOf[e.data('source')].push(e.data('target'));
      if (!parentOf[e.data('target')]) parentOf[e.data('target')] = e.data('source');
    }
  });

  const spousePairs = [];
  cy.edges().forEach(e => {
    if (e.data('type') === 'SPOUSE_OF') {
      spousePairs.push([e.data('source'), e.data('target')]);
    }
  });

  for (const id in childrenOf) {
    childrenOf[id].sort((a, b) => {
      const na = cy.getElementById(a).data('label') || '';
      const nb = cy.getElementById(b).data('label') || '';
      return na.localeCompare(nb);
    });
  }

  const depth = {};
  function setDepth(id, d) {
    if (depth[id] === undefined || d > depth[id]) {
      depth[id] = d;
      childrenOf[id].forEach(kid => setDepth(kid, d + 1));
    }
  }

  const roots = Object.keys(childrenOf).filter(id => !parentOf[id] && childrenOf[id].length > 0);
  const isolated = Object.keys(childrenOf).filter(id => !parentOf[id] && childrenOf[id].length === 0);

  roots.forEach(r => setDepth(r, 0));

  function findRoot(id) {
    let cur = id;
    while (parentOf[cur]) cur = parentOf[cur];
    return cur;
  }

  const rootGroup = {};
  roots.forEach(r => { rootGroup[r] = r; });
  function findGroup(r) {
    while (rootGroup[r] !== r) { rootGroup[r] = rootGroup[rootGroup[r]]; r = rootGroup[r]; }
    return r;
  }
  function unionGroups(a, b) {
    const ga = findGroup(a), gb = findGroup(b);
    if (ga !== gb) rootGroup[ga] = gb;
  }
  for (const [s, t] of spousePairs) {
    const rs = findRoot(s), rt = findRoot(t);
    if (rs !== rt && rootGroup[rs] !== undefined && rootGroup[rt] !== undefined) {
      unionGroups(rs, rt);
    }
  }

  const groups = {};
  roots.forEach(r => {
    const g = findGroup(r);
    if (!groups[g]) groups[g] = [];
    groups[g].push(r);
  });
  function treeSize(id) {
    let s = 1;
    childrenOf[id].forEach(k => { s += treeSize(k); });
    return s;
  }
  const groupList = Object.values(groups);
  groupList.forEach(g => g.sort((a, b) => treeSize(b) - treeSize(a)));
  groupList.sort((a, b) => {
    const sa = a.reduce((sum, r) => sum + treeSize(r), 0);
    const sb = b.reduce((sum, r) => sum + treeSize(r), 0);
    return sb - sa;
  });

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
    const firstX = positions[kids[0]].x;
    const lastX = positions[kids[kids.length - 1]].x;
    positions[id] = { x: (firstX + lastX) / 2, y: (depth[id] || 0) * RANK_GAP };
    return x;
  }

  function getSubtreeIds(rootId) {
    const ids = [rootId];
    const queue = [rootId];
    while (queue.length > 0) {
      const cur = queue.shift();
      for (const kid of childrenOf[cur]) {
        ids.push(kid);
        queue.push(kid);
      }
    }
    return ids;
  }

  let xOffset = 0;
  const positionedSoFar = new Set();

  for (const group of groupList) {
    xOffset = positionSubtree(group[0], xOffset);
    getSubtreeIds(group[0]).forEach(id => positionedSoFar.add(id));

    for (let i = 1; i < group.length; i++) {
      const root = group[i];
      const treeIds = getSubtreeIds(root);

      let spouseAnchor = null;
      for (const [s, t] of spousePairs) {
        if (treeIds.includes(s) && positions[t]) {
          spouseAnchor = { thisNode: s, otherNode: t };
          break;
        }
        if (treeIds.includes(t) && positions[s]) {
          spouseAnchor = { thisNode: t, otherNode: s };
          break;
        }
      }

      positionSubtree(root, xOffset + NODE_GAP);

      if (spouseAnchor && positions[spouseAnchor.thisNode] && positions[spouseAnchor.otherNode]) {
        const targetX = positions[spouseAnchor.otherNode].x + SPOUSE_GAP;
        const currentX = positions[spouseAnchor.thisNode].x;
        const shiftX = targetX - currentX;
        const targetDepth = depth[spouseAnchor.otherNode] || 0;
        const currentDepth = depth[spouseAnchor.thisNode] || 0;
        const depthShift = targetDepth - currentDepth;
        for (const id of treeIds) {
          if (positions[id]) {
            positions[id].x += shiftX;
            positions[id].y += depthShift * RANK_GAP;
          }
          if (depth[id] !== undefined) depth[id] += depthShift;
        }

        function detectOverlap(treeNodeIds) {
          const occupiedByY = {};
          for (const eid of positionedSoFar) {
            if (!positions[eid]) continue;
            const y = Math.round(positions[eid].y);
            if (!occupiedByY[y]) occupiedByY[y] = [];
            occupiedByY[y].push(positions[eid].x);
          }
          let maxOvl = 0;
          for (const id of treeNodeIds) {
            if (!positions[id]) continue;
            const y = Math.round(positions[id].y);
            const tx = positions[id].x;
            const occupied = occupiedByY[y];
            if (!occupied) continue;
            for (const ox of occupied) {
              const gap = Math.abs(tx - ox);
              if (gap < NODE_GAP) maxOvl = Math.max(maxOvl, NODE_GAP - gap);
            }
          }
          return maxOvl;
        }

        const anchorId = spouseAnchor.thisNode;
        let hasOverlap = detectOverlap(treeIds) > 0;
        if (hasOverlap) {
          for (const id of treeIds) {
            if (id === anchorId) continue;
            if (positions[id]) positions[id].y += RANK_GAP;
            if (depth[id] !== undefined) depth[id] += 1;
          }
        }

        const remainingOverlap = detectOverlap(treeIds);
        if (remainingOverlap > 0) {
          for (const id of treeIds) {
            if (positions[id]) positions[id].x += remainingOverlap;
          }
        }
      }

      treeIds.forEach(id => positionedSoFar.add(id));
      let maxX = xOffset;
      for (const id of treeIds) {
        if (positions[id] && positions[id].x > maxX) maxX = positions[id].x;
      }
      xOffset = maxX + NODE_GAP;
    }

    xOffset += NODE_GAP;
  }

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

  isolated.forEach(id => {
    if (!positions[id]) {
      depth[id] = 0;
      positions[id] = { x: xOffset, y: 0 };
      xOffset += NODE_GAP;
    }
  });

  // Split crowded generations
  const CROWD_THRESHOLD = 10;
  const SUB_ROW_OFFSET = RANK_GAP * 0.4;

  const nodesByDepth = {};
  for (const id in positions) {
    const d = depth[id];
    if (d === undefined) continue;
    if (!nodesByDepth[d]) nodesByDepth[d] = [];
    nodesByDepth[d].push(id);
  }

  for (const d in nodesByDepth) {
    const nodesAtDepth = nodesByDepth[d];
    if (nodesAtDepth.length < CROWD_THRESHOLD) continue;

    const parentGroups = {};
    const noParent = [];
    for (const id of nodesAtDepth) {
      const par = parentOf[id];
      if (par) {
        if (!parentGroups[par]) parentGroups[par] = [];
        parentGroups[par].push(id);
      } else {
        noParent.push(id);
      }
    }

    const sortedGroups = Object.entries(parentGroups)
      .sort((a, b) => (positions[a[0]] ? positions[a[0]].x : 0) - (positions[b[0]] ? positions[b[0]].x : 0));

    let toggle = false;
    for (const [par, kids] of sortedGroups) {
      if (toggle) {
        for (const kid of kids) {
          if (positions[kid]) positions[kid].y += SUB_ROW_OFFSET;
          const desc = getSubtreeIds(kid).slice(1);
          for (const did of desc) {
            if (positions[did]) positions[did].y += SUB_ROW_OFFSET;
          }
        }
      }
      toggle = !toggle;
    }
  }

  // Post-layout: stagger overlapping labels
  const LABEL_CLEARANCE = 120;
  const STAGGER_OFFSET = 35;

  const rowBuckets = {};
  for (const id in positions) {
    const yKey = Math.round(positions[id].y);
    if (!rowBuckets[yKey]) rowBuckets[yKey] = [];
    rowBuckets[yKey].push(id);
  }

  for (const yKey in rowBuckets) {
    const row = rowBuckets[yKey];
    if (row.length < 2) continue;
    row.sort((a, b) => positions[a].x - positions[b].x);
    let nudged = false;
    for (let i = 1; i < row.length; i++) {
      const gap = positions[row[i]].x - positions[row[i - 1]].x;
      if (gap < LABEL_CLEARANCE) {
        nudged = !nudged;
        if (nudged) {
          positions[row[i]].y += STAGGER_OFFSET;
        }
      } else {
        nudged = false;
      }
    }
  }

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
  if (!ctxTargetNode || !canEdit()) return;
  const id = ctxTargetNode.data('id');
  const person = getPersonById(id);
  if (!person) return;
  document.getElementById('editPersonId').value = person.id;
  document.getElementById('editPersonName').value = person.display_name;
  document.getElementById('editPersonSex').value = person.sex;
  document.getElementById('editPersonNotes').value = person.notes || '';
  document.getElementById('editBirthDate').value = person.birth_date || '';
  document.getElementById('editDeathDate').value = person.death_date || '';
  document.getElementById('editDeceased').checked = !!person.is_deceased;
  document.getElementById('editModalTitle').textContent = 'Edit Person';
  document.getElementById('editCommentInput').value = '';
  loadComments(id);
  openModal('editPersonModal');
}

function onEditDeathDateChange() {
  if (document.getElementById('editDeathDate').value) {
    document.getElementById('editDeceased').checked = true;
  }
}

async function saveEditPerson() {
  if (!currentTreeId || !canEdit()) return;
  const id = document.getElementById('editPersonId').value;
  const display_name = document.getElementById('editPersonName').value.trim();
  const sex = document.getElementById('editPersonSex').value;
  const notes = document.getElementById('editPersonNotes').value.trim() || null;
  const birth_date = document.getElementById('editBirthDate').value || null;
  const death_date = document.getElementById('editDeathDate').value || null;
  const is_deceased = document.getElementById('editDeceased').checked || null;
  if (!display_name) return;
  try {
    const res = await fetch(treeApi(`/people/${id}`), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name, sex, notes, birth_date, death_date, is_deceased })
    });
    if (!res.ok) throw new Error(await res.text());
    closeModal('editPersonModal');
    await refresh();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Comments ──

async function loadComments(personId) {
  const listEl = document.getElementById('editCommentList');
  if (!currentTreeId) { listEl.innerHTML = ''; return; }
  try {
    const res = await fetch(treeApi(`/people/${personId}/comments`));
    if (!res.ok) throw new Error('Failed to load comments');
    const comments = await res.json();
    renderComments(comments, personId);
  } catch (e) {
    listEl.innerHTML = '<div style="color:#e74c3c;font-size:12px">Error loading comments</div>';
  }
}

function renderComments(comments, personId) {
  const listEl = document.getElementById('editCommentList');
  if (comments.length === 0) {
    listEl.innerHTML = '<div style="color:#999;font-size:12px">No comments yet</div>';
    return;
  }
  listEl.innerHTML = comments.map(c => {
    const date = new Date(c.created_at).toLocaleString();
    const canDel = sessionCommentIds.has(c.id);
    const delBtn = canDel
      ? `<button class="comment-delete" onclick="deleteComment('${personId}','${c.id}')" title="Delete">&#10005;</button>`
      : '';
    return `<div class="comment-item">
      <div class="comment-meta">
        <span><span class="comment-author">${escapeHtml(c.author_name)}</span> &mdash; ${date}</span>
        ${delBtn}
      </div>
      <div class="comment-content">${escapeHtml(c.content)}</div>
    </div>`;
  }).join('');
}

async function addComment() {
  if (!currentTreeId || !canEdit()) return;
  const personId = document.getElementById('editPersonId').value;
  const input = document.getElementById('editCommentInput');
  const content = input.value.trim();
  if (!content) return;
  try {
    const res = await fetch(treeApi(`/people/${personId}/comments`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    });
    if (!res.ok) throw new Error(await res.text());
    const comment = await res.json();
    sessionCommentIds.add(comment.id);
    input.value = '';
    await loadComments(personId);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function deleteComment(personId, commentId) {
  if (!confirm('Delete this comment?')) return;
  try {
    const res = await fetch(treeApi(`/people/${personId}/comments/${commentId}`), { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    sessionCommentIds.delete(commentId);
    await loadComments(personId);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function ctxDeletePerson() {
  hideAllMenus();
  if (!ctxTargetNode || !canEdit()) return;
  const id = ctxTargetNode.data('id');
  const label = ctxTargetNode.data('label');
  if (!confirm(`Delete "${label}" and all their relationships?`)) return;
  try {
    const res = await fetch(treeApi(`/people/${id}`), { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    await refresh();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

function ctxAddChild() {
  hideAllMenus();
  if (!ctxTargetNode || !canEdit()) return;
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
  if (!currentTreeId || !canEdit()) return;
  const parentId = document.getElementById('addChildParentId').value;
  const name = document.getElementById('addChildName').value.trim();
  if (!name) return;
  const sex = document.getElementById('addChildSex').value;
  const notes = document.getElementById('addChildNotes').value.trim() || null;
  try {
    const res = await fetch(treeApi('/people'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, sex, notes })
    });
    if (!res.ok) throw new Error(await res.text());
    const child = await res.json();
    const relRes = await fetch(treeApi('/relationships'), {
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

let parentMode = 'new';

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
  if (!ctxTargetNode || !canEdit()) return;
  const childId = ctxTargetNode.data('id');
  const childLabel = ctxTargetNode.data('label');
  let existingParents = [];
  try {
    const res = await fetch(treeApi(`/people/${childId}/parents`));
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
  if (!currentTreeId || !canEdit()) return;
  const childId = document.getElementById('addParentChildId').value;
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
    const res = await fetch(treeApi(`/people/${childId}/set-parent`), {
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

let spouseMode = 'new';

function setSpouseMode(mode) {
  spouseMode = mode;
  document.getElementById('spouseNewFields').style.display = mode === 'new' ? 'block' : 'none';
  document.getElementById('spouseExistingFields').style.display = mode === 'existing' ? 'block' : 'none';
  document.getElementById('spouseModeNew').className = mode === 'new' ? 'btn-primary' : 'btn-secondary';
  document.getElementById('spouseModeExisting').className = mode === 'existing' ? 'btn-primary' : 'btn-secondary';
  if (mode === 'existing') {
    populateSpouseSelect('');
    document.getElementById('spouseSearchInput').value = '';
  }
}

function populateSpouseSelect(query) {
  const personId = document.getElementById('addSpousePersonId').value;
  const q = (query || '').toLowerCase();
  const filtered = people.filter(p => p.id !== personId && (!q || p.display_name.toLowerCase().includes(q)));
  const sel = document.getElementById('spouseExistingSelect');
  sel.innerHTML = filtered.map(p =>
    `<option value="${p.id}">${escapeHtml(p.display_name)} (${p.sex})</option>`
  ).join('');
}

function onSpouseSearchInput() {
  const query = document.getElementById('spouseSearchInput').value.trim();
  populateSpouseSelect(query);
}

async function ctxAddSpouse() {
  hideAllMenus();
  if (!ctxTargetNode || !canEdit()) return;
  const personId = ctxTargetNode.data('id');
  const personLabel = ctxTargetNode.data('label');
  try {
    const res = await fetch(treeApi(`/people/${personId}/relationship-counts`));
    const counts = await res.json();
    if (counts.spouses >= 1) {
      alert(`"${personLabel}" already has a spouse. Remove the existing spouse relationship first.`);
      return;
    }
  } catch (e) { /* proceed, server will validate */ }
  document.getElementById('addSpousePersonId').value = personId;
  document.getElementById('addSpouseModalTitle').textContent = `Add Spouse of ${personLabel}`;
  document.getElementById('addSpouseName').value = '';
  document.getElementById('addSpouseNotes').value = '';
  const person = getPersonById(personId);
  document.getElementById('addSpouseSex').value = person && person.sex === 'M' ? 'F' : 'M';
  setSpouseMode('new');
  openModal('addSpouseModal');
}

async function saveAddSpouse() {
  if (!currentTreeId || !canEdit()) return;
  const personId = document.getElementById('addSpousePersonId').value;
  let spouseId;
  try {
    if (spouseMode === 'existing') {
      spouseId = document.getElementById('spouseExistingSelect').value;
      if (!spouseId) { alert('Select a person from the list'); return; }
      if (spouseId === personId) { alert('A person cannot be their own spouse'); return; }
    } else {
      const name = document.getElementById('addSpouseName').value.trim();
      if (!name) { alert('Enter a name'); return; }
      const sex = document.getElementById('addSpouseSex').value;
      const notes = document.getElementById('addSpouseNotes').value.trim() || null;
      const res = await fetch(treeApi('/people'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: name, sex, notes })
      });
      if (!res.ok) throw new Error(await res.text());
      const spouse = await res.json();
      spouseId = spouse.id;
    }
    const relRes = await fetch(treeApi('/relationships'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_person_id: personId, to_person_id: spouseId, type: 'SPOUSE_OF' })
    });
    if (!relRes.ok) {
      if (spouseMode === 'new') await fetch(treeApi(`/people/${spouseId}`), { method: 'DELETE' });
      throw new Error(await relRes.text());
    }
    const data = await relRes.json();
    closeModal('addSpouseModal');
    showSpouseMergeReport(data);
    await refresh();
    highlightNewNode(spouseId);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Context Menu: Add Sibling ──

async function ctxAddSibling() {
  hideAllMenus();
  if (!ctxTargetNode || !canEdit()) return;
  const personId = ctxTargetNode.data('id');
  const personLabel = ctxTargetNode.data('label');
  try {
    const res = await fetch(treeApi(`/people/${personId}/parents`));
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
  if (!currentTreeId || !canEdit()) return;
  const personId = document.getElementById('addSiblingPersonId').value;
  const name = document.getElementById('addSiblingName').value.trim();
  if (!name) return;
  const sex = document.getElementById('addSiblingSex').value;
  const notes = document.getElementById('addSiblingNotes').value.trim() || null;
  try {
    const parentsRes = await fetch(treeApi(`/people/${personId}/parents`));
    const parents = await parentsRes.json();
    if (parents.length === 0) {
      alert('This person has no parents. Add a parent first.');
      return;
    }
    const res = await fetch(treeApi('/people'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, sex, notes })
    });
    if (!res.ok) throw new Error(await res.text());
    const sibling = await res.json();
    for (const parent of parents) {
      const relRes = await fetch(treeApi('/relationships'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from_person_id: parent.id, to_person_id: sibling.id, type: 'PARENT_OF' })
      });
      if (!relRes.ok) {
        await fetch(treeApi(`/people/${sibling.id}`), { method: 'DELETE' });
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
  if (!ctxTargetEdge || !canEdit()) return;
  const id = ctxTargetEdge.data('id');
  if (!confirm('Delete this relationship?')) return;
  try {
    const res = await fetch(treeApi(`/relationships/${id}`), { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    await refresh();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Context Menu: Background actions ──

function ctxAddPersonHere() {
  hideAllMenus();
  if (!canEdit()) return;
  document.getElementById('modalPersonName').value = '';
  document.getElementById('modalPersonSex').value = 'M';
  document.getElementById('modalPersonNotes').value = '';
  openModal('addPersonModal');
}

async function saveModalPerson() {
  if (!currentTreeId || !canEdit()) return;
  const name = document.getElementById('modalPersonName').value.trim();
  if (!name) return;
  const sex = document.getElementById('modalPersonSex').value;
  const notes = document.getElementById('modalPersonNotes').value.trim() || null;
  const placementPos = lastCtxPosition;
  try {
    const res = await fetch(treeApi('/people'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, sex, notes })
    });
    if (!res.ok) throw new Error(await res.text());
    const newPerson = await res.json();
    closeModal('addPersonModal');
    await refresh();
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

// ── Context Menu: Find Person ──

function ctxFindPerson() {
  hideAllMenus();
  document.getElementById('findPersonInput').value = '';
  document.getElementById('findPersonResults').innerHTML = '';
  openModal('findPersonModal');
  setTimeout(() => document.getElementById('findPersonInput').focus(), 50);
}

function onFindPersonInput() {
  const query = document.getElementById('findPersonInput').value.trim().toLowerCase();
  const listEl = document.getElementById('findPersonResults');
  if (!query) { listEl.innerHTML = ''; return; }
  const filtered = people.filter(p => p.display_name.toLowerCase().includes(query));
  if (filtered.length === 0) {
    listEl.innerHTML = '<li style="color:#999">No matches</li>';
    return;
  }
  const re = new RegExp(`(${escapeRegex(query)})`, 'gi');
  listEl.innerHTML = filtered.map(p => {
    const name = escapeHtml(p.display_name).replace(re, '<span class="match-highlight">$1</span>');
    return `<li data-id="${p.id}" onclick="findPersonSelect('${p.id}')"><span class="sex-badge">${p.sex}</span> ${name}</li>`;
  }).join('');
}

function onFindPersonKeydown(e) {
  if (e.key === 'Enter') {
    const query = document.getElementById('findPersonInput').value.trim().toLowerCase();
    if (!query) return;
    const match = people.find(p => p.display_name.toLowerCase().includes(query));
    if (match) findPersonSelect(match.id);
  }
  if (e.key === 'Escape') {
    closeModal('findPersonModal');
  }
}

function findPersonSelect(personId) {
  closeModal('findPersonModal');
  navigateToPerson(personId);
}

// ══════════════════════════════════════════════════════════
// SHARING (tree-scoped)
// ══════════════════════════════════════════════════════════

let activeShareToken = null;

async function loadShares() {
  if (!currentTreeId || !isOwner()) return;
  try {
    const res = await fetch(treeApi('/shares'));
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
      <strong>${escapeHtml(s.dataset || s.tree_id || '')}</strong>
      <span style="color:#999;font-size:11px">${viewerCount} viewer(s)</span>
      <span onclick="event.stopPropagation();deleteShare('${s.token}')" style="float:right;color:#e74c3c;cursor:pointer;font-size:11px" title="Delete">&#10005;</span>
    </div>`;
  }).join('');
}

async function createShareLink() {
  if (!currentTreeId || !isOwner()) return;
  try {
    const res = await fetch(treeApi('/shares'), {
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
    await fetch(treeApi(`/shares/${token}`), { method: 'DELETE' });
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
    const res = await fetch(treeApi(`/shares/${token}/viewers`));
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
  if (!activeShareToken || !currentTreeId) return;
  const email = document.getElementById('viewerEmail').value.trim();
  if (!email) return;
  try {
    const res = await fetch(treeApi(`/shares/${activeShareToken}/viewers`), {
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
    await fetch(treeApi(`/shares/${token}/viewers/${viewerId}`), { method: 'DELETE' });
    await loadViewers(token);
    await loadShares();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function loadAccessLog(token) {
  try {
    const res = await fetch(treeApi(`/shares/${token}/access-log`));
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

// ══════════════════════════════════════════════════════════
// TREE MEMBERS (owner only)
// ══════════════════════════════════════════════════════════

async function loadMembers() {
  if (!currentTreeId || !isOwner()) return;
  try {
    const res = await fetch(treeApi('/members'));
    if (!res.ok) return;
    const data = await res.json();
    renderMembers(data);
  } catch (e) { /* ignore */ }
}

function renderMembers(data) {
  const el = document.getElementById('membersList');
  let html = '';

  // Owner
  if (data.owner) {
    html += `<div class="member-item">
      <div class="member-info">
        <div class="member-email">${escapeHtml(data.owner.display_name || data.owner.email)}</div>
        <div class="member-role">Owner</div>
      </div>
    </div>`;
  }

  // Direct users
  for (const u of (data.users || [])) {
    html += `<div class="member-item">
      <div class="member-info">
        <div class="member-email">${escapeHtml(u.display_name || u.email)}</div>
        <div class="member-role">${u.role}</div>
      </div>
    </div>`;
  }

  // Groups
  for (const g of (data.groups || [])) {
    html += `<div class="member-item">
      <div class="member-info">
        <div class="member-email">[Group] ${escapeHtml(g.name)}</div>
        <div class="member-role">${g.role}</div>
      </div>
    </div>`;
  }

  if (!html) {
    html = '<div style="font-size:13px;color:#999">No members yet</div>';
  }
  el.innerHTML = html;
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
  if (!currentTreeId) {
    const emptyState = document.getElementById('emptyState');
    if (emptyState) emptyState.style.display = 'flex';
    updateExportButtons(false);
    if (cy) { cy.destroy(); cy = null; }
    return;
  }

  const res = await fetch(treeApi('/graph'));
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
    const nodeData = { id: n.data.id, label: n.data.label, gen, color };
    if (n.data.is_deceased) nodeData.is_deceased = true;
    if (n.data.birth_date) nodeData.birth_date = n.data.birth_date;
    if (n.data.death_date) nodeData.death_date = n.data.death_date;
    elements.push({ data: nodeData });
  });

  const spouseOf = {};
  data.edges.forEach(e => {
    if (e.data.type === 'SPOUSE_OF') {
      spouseOf[e.data.source] = e.data.target;
      spouseOf[e.data.target] = e.data.source;
    }
  });

  const parentEdges = data.edges.filter(e => e.data.type === 'PARENT_OF');
  const skipEdges = new Set();
  const childParents = {};
  parentEdges.forEach(e => {
    const child = e.data.target;
    if (!childParents[child]) childParents[child] = [];
    childParents[child].push(e);
  });
  for (const child in childParents) {
    const edges = childParents[child];
    if (edges.length === 2) {
      const p1 = edges[0].data.source, p2 = edges[1].data.source;
      if (spouseOf[p1] === p2) {
        skipEdges.add(edges[1].data.id);
      }
    }
  }

  data.edges.forEach(e => {
    if (!skipEdges.has(e.data.id)) {
      elements.push({
        data: { id: e.data.id, source: e.data.source, target: e.data.target, type: e.data.type }
      });
    }
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
          'text-max-width': 90,
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
        selector: 'node[?is_deceased]',
        style: {
          'border-style': 'dashed',
          'border-width': 4,
          'border-color': '#95a5a6',
          'opacity': 0.75
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
    layout: { name: 'preset' },
    minZoom: 0.2,
    maxZoom: 3,
    wheelSensitivity: 0.3
  });

  runFamilyLayout(false);
  updateExportButtons(true);

  cy.on('dragfree', 'node', onNodeDrag);

  // Context menu events — only show edit actions if user can edit
  cy.on('cxttap', 'node', async function(evt) {
    evt.originalEvent.preventDefault();
    ctxTargetNode = evt.target;
    ctxTargetEdge = null;

    if (!canEdit()) return; // Don't show context menu for viewers

    const parentItem = document.getElementById('ctxAddParentItem');
    const spouseItem = document.getElementById('ctxAddSpouseItem');
    const siblingItem = document.getElementById('ctxAddSiblingItem');
    parentItem.className = 'ctx-item';
    parentItem.innerHTML = '<span class="ctx-icon">&#x1F464;</span> Add Parent';
    spouseItem.className = 'ctx-item';
    siblingItem.className = 'ctx-item';
    try {
      const res = await fetch(treeApi(`/people/${evt.target.data('id')}/relationship-counts`));
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
    if (!canEdit()) return;
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
      lastCtxPosition = evt.position;
      // Hide "Add Person" for viewers, but always show "Find Person"
      const addItem = document.querySelector('#ctxBg .ctx-item[onclick="ctxAddPersonHere()"]');
      const addSep = addItem ? addItem.previousElementSibling : null;
      if (addItem) addItem.style.display = canEdit() ? '' : 'none';
      if (addSep) addSep.style.display = canEdit() ? '' : 'none';
      showMenu('ctxBg', evt.originalEvent.clientX, evt.originalEvent.clientY);
    }
  });

  cy.on('dbltap', 'node', function(evt) {
    ctxTargetNode = evt.target;
    ctxEditPerson();
  });
}

// ══════════════════════════════════════════════════════════
// MERGE PERSON
// ══════════════════════════════════════════════════════════

function getParentNames(personId) {
  if (!cy) return [];
  const parents = [];
  cy.edges().forEach(e => {
    if (e.data('type') === 'PARENT_OF' && e.data('target') === personId) {
      const parentNode = cy.getElementById(e.data('source'));
      if (parentNode && parentNode.nonempty()) {
        parents.push(parentNode.data('label'));
      }
    }
  });
  return parents;
}

function getPersonLabel(p) {
  const parents = getParentNames(p.id);
  if (parents.length > 0) {
    return `${p.display_name} (${p.sex}) — child of ${parents.join(' & ')}`;
  }
  return `${p.display_name} (${p.sex})`;
}

function ctxMergePerson() {
  hideAllMenus();
  if (!ctxTargetNode || !canEdit()) return;
  const personId = ctxTargetNode.data('id');
  const personLabel = ctxTargetNode.data('label');
  document.getElementById('mergePersonId').value = personId;
  document.getElementById('mergeRemoveName').textContent = personLabel;
  document.getElementById('mergeModalTitle').textContent = `Merge "${personLabel}"`;
  document.getElementById('mergeSearchInput').value = '';
  populateMergeSelect('');
  openModal('mergePersonModal');
}

function onMergeSearchInput() {
  const query = document.getElementById('mergeSearchInput').value.trim();
  populateMergeSelect(query);
}

function populateMergeSelect(query) {
  const personId = document.getElementById('mergePersonId').value;
  const q = (query || '').toLowerCase();
  const filtered = people.filter(p => p.id !== personId && (!q || p.display_name.toLowerCase().includes(q)));
  const sel = document.getElementById('mergeTargetSelect');
  sel.innerHTML = filtered.map(p => {
    const label = getPersonLabel(p);
    return `<option value="${p.id}">${escapeHtml(label)}</option>`;
  }).join('');
}

async function saveMergePerson() {
  if (!currentTreeId || !canEdit()) return;
  const personId = document.getElementById('mergePersonId').value;
  const targetId = document.getElementById('mergeTargetSelect').value;
  if (!targetId) { alert('Select a person to merge into'); return; }
  const removeName = document.getElementById('mergeRemoveName').textContent;
  const keepPerson = people.find(p => p.id === targetId);
  const keepName = keepPerson ? keepPerson.display_name : '?';
  if (!confirm(`Merge "${removeName}" into "${keepName}"?\n\nAll relationships from "${removeName}" will be transferred to "${keepName}", and "${removeName}" will be deleted.\n\nThis cannot be undone.`)) return;
  try {
    const res = await fetch(treeApi(`/people/${personId}/merge`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ merge_into_id: targetId })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Merge failed');
    }
    closeModal('mergePersonModal');
    await refresh();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ══════════════════════════════════════════════════════════
// CHANGE HISTORY
// ══════════════════════════════════════════════════════════

let historyOffset = 0;
const HISTORY_PAGE_SIZE = 50;

function toggleHistoryPanel() {
  const panel = document.getElementById('historyPanel');
  const isOpen = panel.classList.toggle('open');
  if (isOpen) {
    historyOffset = 0;
    loadChangelog();
  }
}

async function loadChangelog() {
  if (!currentTreeId) return;
  try {
    const res = await fetch(treeApi(`/changelog?limit=${HISTORY_PAGE_SIZE}&offset=${historyOffset}`));
    if (!res.ok) return;
    const changes = await res.json();
    renderChangelog(changes, historyOffset === 0);
    const loadMoreBtn = document.getElementById('historyLoadMore');
    if (loadMoreBtn) loadMoreBtn.style.display = changes.length >= HISTORY_PAGE_SIZE ? 'block' : 'none';
  } catch (e) { /* ignore */ }
}

function loadMoreHistory() {
  historyOffset += HISTORY_PAGE_SIZE;
  loadChangelog();
}

function renderChangelog(changes, replace) {
  const listEl = document.getElementById('historyList');
  if (replace && changes.length === 0) {
    listEl.innerHTML = '<div class="history-empty">No changes recorded yet</div>';
    return;
  }
  const html = changes.map(c => {
    const date = new Date(c.created_at).toLocaleString();
    const badgeClass = 'badge-' + c.action;
    return `<div class="history-item">
      <div class="history-action">
        <span class="history-action-badge ${badgeClass}">${escapeHtml(c.action)}</span>
        ${escapeHtml(c.entity_type)}
      </div>
      <div class="history-details">${escapeHtml(c.details || '')}</div>
      <div class="history-meta">
        <span>${escapeHtml(c.user_name || '')}</span>
        <span>${date}</span>
      </div>
    </div>`;
  }).join('');
  if (replace) {
    listEl.innerHTML = html;
  } else {
    listEl.insertAdjacentHTML('beforeend', html);
  }
}

// ── Initialize ──

checkAuth();
