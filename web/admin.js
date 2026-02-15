// ══════════════════════════════════════════════════════════
// Admin Panel JavaScript
// ══════════════════════════════════════════════════════════

let adminUser = null;
let groups = [], users = [], allTrees = [];
let selectedGroupId = null, selectedUserId = null, selectedTreeId = null;
let activeTab = 'groups';

// ── Helpers ──

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

function showStatus(id, message, isError) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = message;
  el.className = 'status-msg ' + (isError ? 'error' : 'success');
  setTimeout(() => { el.className = 'status-msg'; }, 4000);
}

function openModal(id) {
  document.getElementById(id).classList.add('open');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

async function apiFetch(url, options) {
  const res = await fetch(url, options);
  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('Not authenticated');
  }
  if (res.status === 403) {
    const err = await res.json();
    throw new Error(err.detail || 'Forbidden');
  }
  return res;
}

// ── Auth ──

async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me');
    if (!res.ok) {
      window.location.href = '/login';
      return;
    }
    adminUser = await res.json();
    if (!adminUser.is_admin) {
      window.location.href = '/';
      return;
    }
    document.getElementById('userEmail').textContent = adminUser.email;
    initAdmin();
  } catch (e) {
    window.location.href = '/login';
  }
}

async function doLogout() {
  await fetch('/api/auth/logout', { method: 'POST' });
  window.location.href = '/login';
}

// ── Tab switching ──

function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === tab);
  });
  document.querySelectorAll('.panel').forEach(p => {
    p.classList.toggle('active', p.id === 'panel' + tab.charAt(0).toUpperCase() + tab.slice(1));
  });
  if (tab === 'groups') loadGroups();
  if (tab === 'users') loadUsers();
  if (tab === 'trees') loadAdminTrees();
}

// ── Init ──

function initAdmin() {
  loadGroups();
  loadAllTrees();
}

async function loadAllTrees() {
  try {
    const res = await apiFetch('/api/admin/trees');
    if (res.ok) allTrees = await res.json();
  } catch (e) { /* ignore */ }
}

// ══════════════════════════════════════════════════════════
// GROUPS TAB
// ══════════════════════════════════════════════════════════

async function loadGroups() {
  try {
    const res = await apiFetch('/api/groups');
    if (!res.ok) return;
    groups = await res.json();
    renderGroups();
  } catch (e) { /* ignore */ }
}

function renderGroups() {
  const el = document.getElementById('groupList');
  if (groups.length === 0) {
    el.innerHTML = '<div class="empty-msg">No groups yet. Create one to get started.</div>';
    return;
  }
  el.innerHTML = groups.map(g => {
    const active = g.id === selectedGroupId ? ' active' : '';
    return `<div class="list-item${active}" onclick="selectGroup('${g.id}')">
      <div class="list-item-info">
        <div class="list-item-title">${escapeHtml(g.name)}</div>
        <div class="list-item-sub">${escapeHtml(g.description || '')}</div>
      </div>
    </div>`;
  }).join('');
}

async function selectGroup(gid) {
  selectedGroupId = gid;
  renderGroups();
  document.getElementById('groupDetail').style.display = 'block';
  document.getElementById('groupPlaceholder').style.display = 'none';

  const group = groups.find(g => g.id === gid);
  if (group) {
    document.getElementById('groupDetailName').textContent = group.name;
    document.getElementById('groupEditName').value = group.name;
    document.getElementById('groupEditDesc').value = group.description || '';
  }

  // Clear previous magic link display
  const mlEl = document.getElementById('groupMemberMagicLink');
  if (mlEl) { mlEl.className = 'magic-link-box'; mlEl.innerHTML = ''; }
  await Promise.all([loadGroupMembers(gid), loadGroupTrees(gid)]);
  populateGroupTreeSelect();
}

function openCreateGroupModal() {
  document.getElementById('newGroupName').value = '';
  document.getElementById('newGroupDesc').value = '';
  openModal('createGroupModal');
}

async function createGroup() {
  const name = document.getElementById('newGroupName').value.trim();
  if (!name) return;
  const description = document.getElementById('newGroupDesc').value.trim();
  try {
    const res = await apiFetch('/api/groups', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description })
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed');
    const group = await res.json();
    closeModal('createGroupModal');
    await loadGroups();
    selectGroup(group.id);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function saveGroupDetails() {
  if (!selectedGroupId) return;
  const name = document.getElementById('groupEditName').value.trim();
  const description = document.getElementById('groupEditDesc').value.trim();
  if (!name) return;
  try {
    await apiFetch(`/api/groups/${selectedGroupId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description })
    });
    await loadGroups();
    document.getElementById('groupDetailName').textContent = name;
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function deleteSelectedGroup() {
  if (!selectedGroupId) return;
  if (!confirm('Delete this group? All members and tree access grants will be removed.')) return;
  try {
    await apiFetch(`/api/groups/${selectedGroupId}`, { method: 'DELETE' });
    selectedGroupId = null;
    document.getElementById('groupDetail').style.display = 'none';
    document.getElementById('groupPlaceholder').style.display = 'block';
    await loadGroups();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Group Members ──

async function loadGroupMembers(gid) {
  try {
    const res = await apiFetch(`/api/groups/${gid}/members`);
    if (!res.ok) return;
    const members = await res.json();
    renderGroupMembers(members);
  } catch (e) { /* ignore */ }
}

function renderGroupMembers(members) {
  const el = document.getElementById('groupMembersList');
  if (members.length === 0) {
    el.innerHTML = '<div class="empty-msg">No members in this group.</div>';
    return;
  }
  el.innerHTML = members.map(m =>
    `<div class="list-item" style="cursor:default">
      <div class="list-item-info">
        <div class="list-item-title">${escapeHtml(m.display_name)}</div>
        <div class="list-item-sub">${escapeHtml(m.email)}</div>
      </div>
      <div class="list-item-actions">
        <button class="remove-btn" onclick="removeGroupMember('${m.id}')" title="Remove">&times;</button>
      </div>
    </div>`
  ).join('');
}

async function addGroupMember() {
  if (!selectedGroupId) return;
  const email = document.getElementById('groupMemberEmail').value.trim();
  if (!email) return;
  try {
    const res = await apiFetch(`/api/groups/${selectedGroupId}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    if (!res.ok) {
      const err = await res.json();
      showStatus('groupMemberStatus', err.detail || 'Failed to add member', true);
      return;
    }
    const data = await res.json();
    document.getElementById('groupMemberEmail').value = '';
    // Show magic link for newly created or existing users
    if (data.magic_link) {
      const mlEl = document.getElementById('groupMemberMagicLink');
      const label = data.created ? 'New user created. Share this login link:' : 'Member added. Login link:';
      mlEl.innerHTML = `<strong>${label}</strong><br>
        <input type="text" value="${escapeHtml(data.magic_link)}" readonly
          style="width:100%;font-size:11px;margin-top:4px;padding:6px;border:1px solid #ccc;border-radius:4px;background:#fff"
          onclick="this.select()">
        <button class="btn-primary btn-sm" onclick="navigator.clipboard.writeText('${escapeHtml(data.magic_link)}').then(()=>this.textContent='Copied!')" style="margin-top:4px">Copy Link</button>`;
      mlEl.className = 'magic-link-box visible';
    } else {
      showStatus('groupMemberStatus', 'Member added', false);
    }
    await loadGroupMembers(selectedGroupId);
  } catch (e) {
    showStatus('groupMemberStatus', 'Error: ' + e.message, true);
  }
}

async function removeGroupMember(uid) {
  if (!selectedGroupId) return;
  if (!confirm('Remove this member from the group?')) return;
  try {
    await apiFetch(`/api/groups/${selectedGroupId}/members/${uid}`, { method: 'DELETE' });
    await loadGroupMembers(selectedGroupId);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Group Trees ──

async function loadGroupTrees(gid) {
  try {
    const res = await apiFetch(`/api/groups/${gid}/trees`);
    if (!res.ok) return;
    const treesData = await res.json();
    renderGroupTrees(treesData);
  } catch (e) { /* ignore */ }
}

function renderGroupTrees(treesData) {
  const el = document.getElementById('groupTreesList');
  if (treesData.length === 0) {
    el.innerHTML = '<div class="empty-msg">No trees assigned to this group.</div>';
    return;
  }
  el.innerHTML = treesData.map(t => {
    const badgeClass = t.role === 'editor' ? 'badge-editor' : 'badge-viewer';
    return `<div class="list-item" style="cursor:default">
      <div class="list-item-info">
        <div class="list-item-title">${escapeHtml(t.name)}</div>
      </div>
      <div class="list-item-actions">
        <select class="role-select" onchange="updateGroupTreeRole('${t.id}', this.value)">
          <option value="viewer"${t.role === 'viewer' ? ' selected' : ''}>Viewer</option>
          <option value="editor"${t.role === 'editor' ? ' selected' : ''}>Editor</option>
        </select>
        <button class="remove-btn" onclick="removeGroupTree('${t.id}')" title="Remove">&times;</button>
      </div>
    </div>`;
  }).join('');
}

function populateGroupTreeSelect() {
  const sel = document.getElementById('groupTreeSelect');
  sel.innerHTML = '<option value="">Select a tree...</option>' +
    allTrees.map(t => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join('');
}

async function assignGroupTree() {
  if (!selectedGroupId) return;
  const treeId = document.getElementById('groupTreeSelect').value;
  const role = document.getElementById('groupTreeRole').value;
  if (!treeId) return;
  try {
    const res = await apiFetch(`/api/groups/${selectedGroupId}/trees`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tree_id: treeId, role })
    });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || 'Failed');
      return;
    }
    document.getElementById('groupTreeSelect').value = '';
    await loadGroupTrees(selectedGroupId);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

async function updateGroupTreeRole(treeId, role) {
  if (!selectedGroupId) return;
  try {
    await apiFetch(`/api/groups/${selectedGroupId}/trees/${treeId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role })
    });
  } catch (e) {
    alert('Error: ' + e.message);
    await loadGroupTrees(selectedGroupId);
  }
}

async function removeGroupTree(treeId) {
  if (!selectedGroupId) return;
  if (!confirm('Remove this tree from the group?')) return;
  try {
    await apiFetch(`/api/groups/${selectedGroupId}/trees/${treeId}`, { method: 'DELETE' });
    await loadGroupTrees(selectedGroupId);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}


// ══════════════════════════════════════════════════════════
// USERS TAB
// ══════════════════════════════════════════════════════════

async function loadUsers() {
  try {
    const res = await apiFetch('/api/admin/users');
    if (!res.ok) return;
    users = await res.json();
    renderUsers();
  } catch (e) { /* ignore */ }
}

function renderUsers() {
  const el = document.getElementById('userList');
  if (users.length === 0) {
    el.innerHTML = '<div class="empty-msg">No users found.</div>';
    return;
  }
  el.innerHTML = users.map(u => {
    const active = u.id === selectedUserId ? ' active' : '';
    const adminBadge = u.is_admin ? ' <span class="badge badge-admin">admin</span>' : '';
    return `<div class="list-item${active}" onclick="selectUser('${u.id}')">
      <div class="list-item-info">
        <div class="list-item-title">${escapeHtml(u.display_name)}${adminBadge}</div>
        <div class="list-item-sub">${escapeHtml(u.email)}</div>
      </div>
    </div>`;
  }).join('');
}

async function selectUser(uid) {
  selectedUserId = uid;
  renderUsers();
  document.getElementById('userDetail').style.display = 'block';
  document.getElementById('userPlaceholder').style.display = 'none';

  const user = users.find(u => u.id === uid);
  if (user) {
    document.getElementById('userDetailTitle').textContent = user.display_name;
    document.getElementById('userDetailEmail').value = user.email;
    document.getElementById('userDetailName').value = user.display_name;
  }
  document.getElementById('userMagicLink').className = 'magic-link-box';
  document.getElementById('userMagicLink').textContent = '';

  await loadUserGroups(uid);
}

async function loadUserGroups(uid) {
  const el = document.getElementById('userGroupsList');
  try {
    // Load groups first if needed
    if (groups.length === 0) {
      const gRes = await apiFetch('/api/groups');
      if (gRes.ok) groups = await gRes.json();
    }
    // Check each group's membership in parallel
    const results = await Promise.all(groups.map(async g => {
      try {
        const res = await apiFetch(`/api/groups/${g.id}/members`);
        if (!res.ok) return null;
        const members = await res.json();
        return members.some(m => m.id === uid) ? g : null;
      } catch (e) { return null; }
    }));
    const memberGroups = results.filter(Boolean);
    if (memberGroups.length === 0) {
      el.innerHTML = '<div class="empty-msg">Not a member of any groups.</div>';
      return;
    }
    el.innerHTML = memberGroups.map(g =>
      `<div class="list-item" style="cursor:default">
        <div class="list-item-info">
          <div class="list-item-title">${escapeHtml(g.name)}</div>
          <div class="list-item-sub">${escapeHtml(g.description || '')}</div>
        </div>
      </div>`
    ).join('');
  } catch (e) {
    el.innerHTML = '<div class="empty-msg">Error loading groups.</div>';
  }
}

function openCreateUserModal() {
  document.getElementById('newUserEmail').value = '';
  document.getElementById('newUserDisplayName').value = '';
  document.getElementById('createUserMagicLink').className = 'magic-link-box';
  document.getElementById('createUserMagicLink').textContent = '';
  document.getElementById('createUserStatus').className = 'status-msg';
  document.getElementById('createUserBtn').disabled = false;
  openModal('createUserModal');
}

function closeCreateUserModal() {
  closeModal('createUserModal');
  if (activeTab === 'users') loadUsers();
}

async function createUser() {
  const email = document.getElementById('newUserEmail').value.trim();
  const display_name = document.getElementById('newUserDisplayName').value.trim();
  if (!email || !display_name) {
    showStatus('createUserStatus', 'Email and display name are required', true);
    return;
  }
  try {
    const res = await apiFetch('/api/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, display_name })
    });
    if (!res.ok) {
      const err = await res.json();
      showStatus('createUserStatus', err.detail || 'Failed to create user', true);
      return;
    }
    const data = await res.json();
    showStatus('createUserStatus', 'User created successfully!', false);
    document.getElementById('createUserBtn').disabled = true;
    if (data.magic_link) {
      const mlEl = document.getElementById('createUserMagicLink');
      mlEl.innerHTML = `<strong>Magic Link:</strong><br>
        <input type="text" value="${escapeHtml(data.magic_link)}" readonly
          style="width:100%;font-size:11px;margin-top:4px;padding:6px;border:1px solid #ccc;border-radius:4px;background:#fff"
          onclick="this.select()">
        <button class="btn-primary btn-sm" onclick="navigator.clipboard.writeText('${escapeHtml(data.magic_link)}').then(()=>this.textContent='Copied!')" style="margin-top:4px">Copy Link</button>`;
      mlEl.className = 'magic-link-box visible';
    }
    await loadUsers();
  } catch (e) {
    showStatus('createUserStatus', 'Error: ' + e.message, true);
  }
}

async function saveUserDetails() {
  if (!selectedUserId) return;
  const display_name = document.getElementById('userDetailName').value.trim();
  if (!display_name) return;
  try {
    const res = await apiFetch(`/api/admin/users/${selectedUserId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name })
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed');
    showStatus('userDetailStatus', 'Saved', false);
    document.getElementById('userDetailTitle').textContent = display_name;
    await loadUsers();
  } catch (e) {
    showStatus('userDetailStatus', 'Error: ' + e.message, true);
  }
}

async function getUserMagicLink() {
  if (!selectedUserId) return;
  try {
    const res = await apiFetch(`/api/admin/users/${selectedUserId}/magic-link`);
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();
    const el = document.getElementById('userMagicLink');
    el.innerHTML = `<input type="text" value="${escapeHtml(data.magic_link)}" readonly
      style="width:100%;font-size:11px;padding:6px;border:1px solid #ccc;border-radius:4px;background:#fff"
      onclick="this.select()">
      <button class="btn-primary btn-sm" onclick="navigator.clipboard.writeText('${escapeHtml(data.magic_link)}').then(()=>this.textContent='Copied!')" style="margin-top:4px">Copy Link</button>`;
    el.className = 'magic-link-box visible';
  } catch (e) {
    alert('Error: ' + e.message);
  }
}


// ══════════════════════════════════════════════════════════
// TREE ACCESS TAB
// ══════════════════════════════════════════════════════════

async function loadAdminTrees() {
  await loadAllTrees();
  renderAdminTrees();
}

function renderAdminTrees() {
  const el = document.getElementById('adminTreeList');
  if (allTrees.length === 0) {
    el.innerHTML = '<div class="empty-msg">No trees found.</div>';
    return;
  }
  el.innerHTML = allTrees.map(t => {
    const active = t.id === selectedTreeId ? ' active' : '';
    return `<div class="list-item${active}" onclick="selectAdminTree('${t.id}')">
      <div class="list-item-info">
        <div class="list-item-title">${escapeHtml(t.name)}</div>
      </div>
    </div>`;
  }).join('');
}

async function selectAdminTree(treeId) {
  selectedTreeId = treeId;
  renderAdminTrees();
  document.getElementById('treeDetail').style.display = 'block';
  document.getElementById('treePlaceholder').style.display = 'none';

  const tree = allTrees.find(t => t.id === treeId);
  if (tree) {
    document.getElementById('treeDetailName').textContent = tree.name;
  }

  await loadTreeMembers(treeId);
}

async function loadTreeMembers(treeId) {
  try {
    const res = await apiFetch(`/api/trees/${treeId}/members`);
    if (!res.ok) {
      // Maybe not owner — try to display what we can
      document.getElementById('treeGroupsList').innerHTML = '<div class="empty-msg">Cannot load (not owner).</div>';
      document.getElementById('treeUsersList').innerHTML = '<div class="empty-msg">Cannot load (not owner).</div>';
      return;
    }
    const data = await res.json();
    renderTreeGroups(data.groups || []);
    renderTreeUsers(data.owner, data.users || []);
  } catch (e) {
    document.getElementById('treeGroupsList').innerHTML = '<div class="empty-msg">Error loading.</div>';
    document.getElementById('treeUsersList').innerHTML = '<div class="empty-msg">Error loading.</div>';
  }
}

function renderTreeGroups(groupsData) {
  const el = document.getElementById('treeGroupsList');
  if (groupsData.length === 0) {
    el.innerHTML = '<div class="empty-msg">No groups have access to this tree.</div>';
    return;
  }
  el.innerHTML = groupsData.map(g => {
    const badgeClass = g.role === 'editor' ? 'badge-editor' : 'badge-viewer';
    return `<div class="list-item" style="cursor:default">
      <div class="list-item-info">
        <div class="list-item-title">${escapeHtml(g.name)}</div>
      </div>
      <div class="list-item-actions">
        <span class="badge ${badgeClass}">${g.role}</span>
      </div>
    </div>`;
  }).join('');
}

function renderTreeUsers(owner, usersData) {
  const el = document.getElementById('treeUsersList');
  let html = '';

  if (owner) {
    html += `<div class="list-item" style="cursor:default">
      <div class="list-item-info">
        <div class="list-item-title">${escapeHtml(owner.display_name)}</div>
        <div class="list-item-sub">${escapeHtml(owner.email)}</div>
      </div>
      <div class="list-item-actions">
        <span class="badge badge-owner">owner</span>
      </div>
    </div>`;
  }

  for (const u of usersData) {
    html += `<div class="list-item" style="cursor:default">
      <div class="list-item-info">
        <div class="list-item-title">${escapeHtml(u.display_name)}</div>
        <div class="list-item-sub">${escapeHtml(u.email)}</div>
      </div>
      <div class="list-item-actions">
        <select class="role-select" onchange="updateTreeUserOverride('${u.id}', this.value)">
          <option value="viewer"${u.role === 'viewer' ? ' selected' : ''}>Viewer</option>
          <option value="editor"${u.role === 'editor' ? ' selected' : ''}>Editor</option>
        </select>
        <button class="remove-btn" onclick="removeTreeUserOverride('${u.id}')" title="Remove">&times;</button>
      </div>
    </div>`;
  }

  if (!html) {
    html = '<div class="empty-msg">No users with direct access.</div>';
  }
  el.innerHTML = html;
}

async function addTreeUserOverride() {
  if (!selectedTreeId) return;
  const email = document.getElementById('treeUserEmail').value.trim();
  const role = document.getElementById('treeUserRole').value;
  if (!email) return;
  try {
    const res = await apiFetch(`/api/trees/${selectedTreeId}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, role })
    });
    if (!res.ok) {
      const err = await res.json();
      showStatus('treeUserStatus', err.detail || 'Failed', true);
      return;
    }
    document.getElementById('treeUserEmail').value = '';
    showStatus('treeUserStatus', 'User override added', false);
    await loadTreeMembers(selectedTreeId);
  } catch (e) {
    showStatus('treeUserStatus', 'Error: ' + e.message, true);
  }
}

async function updateTreeUserOverride(uid, role) {
  if (!selectedTreeId) return;
  try {
    await apiFetch(`/api/trees/${selectedTreeId}/members/${uid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role })
    });
  } catch (e) {
    alert('Error: ' + e.message);
    await loadTreeMembers(selectedTreeId);
  }
}

async function removeTreeUserOverride(uid) {
  if (!selectedTreeId) return;
  if (!confirm('Remove this user override?')) return;
  try {
    await apiFetch(`/api/trees/${selectedTreeId}/members/${uid}`, { method: 'DELETE' });
    await loadTreeMembers(selectedTreeId);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}


// ── Initialize ──
checkAuth();
