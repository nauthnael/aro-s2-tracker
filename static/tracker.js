let trackerData = null;
let currentMode = 'jade';
let sortState = { col: null, dir: 0 };

async function loadTracker() {
    try {
        const response = await fetch('/api/tracker');
        trackerData = await response.json();
        renderTable();
    } catch (err) {
        console.error("Error loading tracker:", err);
    }
}

function renderTable() {
    if (!trackerData) return;

    const { dates, snapshots, users } = trackerData;
    const headerRow = document.getElementById('tracker-header');
    const body = document.getElementById('tracker-body');
    const searchText = document.getElementById('search-input').value.toLowerCase();
    const filterMode = document.getElementById('filter-select').value;

    // 1. Render Header
    headerRow.innerHTML = `
        <th class="col-rank frozen">Rank</th>
        <th class="col-alias frozen">Alias</th>
        <th class="col-team frozen" style="text-align:center;min-width:90px">Team</th>
        <th class="col-wrate frozen">W.Rate</th>
        <th class="col-proj frozen">Proj 31/05</th>
        <th class="col-prize frozen">Prize</th>
    `;
    
    dates.forEach(dateStr => {
        const snap = snapshots.find(s => s.date === dateStr);
        const dateObj = new Date(dateStr);
        const displayDate = `${dateObj.getDate()}/${dateObj.getMonth() + 1}`;
        const isDelayed = snap && snap.is_delayed;
        
        const th = document.createElement('th');
        if (isDelayed) th.className = 'delayed';

        if (currentMode === 'refs') {
            const isSorted = sortState.col === dateStr;
            const arrow = isSorted ? (sortState.dir === 1 ? ' ▼' : ' ▲') : '';
            th.innerHTML = `<span style="cursor:pointer;user-select:none" onclick="sortByRefDate('${dateStr}')">${displayDate}${isDelayed ? ' ⚠️' : ''}${arrow}</span>`;
        } else {
            th.innerHTML = `${displayDate} ${isDelayed ? '⚠️' : ''}`;
        }

        headerRow.appendChild(th);
    });

    // 2. Filter Users
    let filteredUsers = users.filter(u => {
        const matchSearch = !searchText || u.alias.toLowerCase().includes(searchText);
        const matchFilter = filterMode === 'all' || 
                           (filterMode === 'team' && u.is_team) || 
                           (filterMode === 'top10' && u.current_rank <= 10);
        return matchSearch && matchFilter;
    });

    // Sort: nếu mode refs và đang sort theo ngày cụ thể
    if (currentMode === 'refs' && sortState.col && sortState.dir !== 0) {
        filteredUsers = [...filteredUsers].sort((a, b) => {
            const histA = a.history[sortState.col];
            const histB = b.history[sortState.col];
            // Sort theo delta_t1 (T1 quan trọng hơn T2)
            const valA = histA ? (histA.delta_t1 ?? -9999) : -9999;
            const valB = histB ? (histB.delta_t1 ?? -9999) : -9999;
            return sortState.dir === 1 ? valB - valA : valA - valB;
        });
    }

    // 3. Render Body
    const fragment = document.createDocumentFragment();
    filteredUsers.forEach(user => {
        const tr = document.createElement('tr');
        if (user.username === "nau***@gmail.com") tr.className = 'row-nau';
        else if (user.is_team) tr.className = 'row-team';
        else if (user.current_rank <= 10) tr.className = 'row-top10';

        const isUnresolved = user.alias && user.alias.includes('[?]');
        const aliasDisplay = isUnresolved
            ? `<span style="color:#f59e0b;font-weight:600">${user.alias}</span>`
            : user.alias;

        const isTeam = user.is_team;
        const role = user.team_role;  // "T1", "T2", hoặc null

        let cells = `
            <td class="col-rank">${user.current_rank === 999 ? '—' : user.current_rank}</td>
            <td class="col-alias">
                <span style="display:flex;align-items:center;gap:0.375rem">
                    <span class="alias-text">${aliasDisplay}</span>
                    <button onclick="openAliasEdit('${user.username}', '${user.alias.replace(/'/g, "\\'")}')"
                        title="${isUnresolved ? 'Alias chưa xác định — click để sửa' : 'Sửa alias'}"
                        style="background:none;border:none;cursor:pointer;color:${isUnresolved ? '#f59e0b' : 'var(--text-muted)'};font-size:0.75rem;padding:0;line-height:1;opacity:${isUnresolved ? '1' : '0.6'}" 
                        onmouseover="this.style.opacity='1'" 
                        onmouseout="this.style.opacity='${isUnresolved ? '1' : '0.6'}'">
                        ${isUnresolved ? '⚠️' : '✏️'}
                    </button>
                </span>
            </td>
            <td class="col-team" style="text-align:center;vertical-align:middle">
                <div style="display:flex;align-items:center;justify-content:center;gap:0.4rem">
                    <input type="checkbox"
                        id="chk-team-${user.username.replace(/[^a-z0-9]/gi,'_')}"
                        ${isTeam ? 'checked' : ''}
                        onchange="handleTeamToggle(this, '${user.username}', '${user.alias.replace(/'/g, "\\'")}')"
                        style="width:14px;height:14px;cursor:pointer;accent-color:#3b82f6">
                    ${isTeam ? `<span style="font-size:0.7rem;color:${role === 'T1' ? '#3b82f6' : '#a78bfa'};font-weight:600">${role}</span>` : ''}
                </div>
            </td>
            <td class="col-wrate">${formatNumber(Math.round(user.w_rate))}</td>
            <td class="col-proj">${formatNumber(user.proj_may31)}</td>
            <td class="col-prize" style="color:var(--success)">${user.prize_est}</td>
        `;

        dates.forEach(dateStr => {
            const hist = user.history[dateStr];
            let content = '—';
            let className = 'mode-muted';

            if (hist) {
                if (currentMode === 'jade') {
                    content = formatNumber(hist.jade);
                    className = 'mode-jade';
                } else if (currentMode === 'delta') {
                    if (hist.delta !== null) {
                        content = (hist.delta >= 0 ? '+' : '') + formatNumber(hist.delta);
                        className = hist.delta >= 0 ? 'mode-delta-pos' : 'mode-delta-neg';
                    }
                } else if (currentMode === 'rank') {
                    content = '#' + hist.rank;
                    className = 'mode-jade';
                } else if (currentMode === 'refs') {
                    // Format: "19(+3) / 27(+5)"
                    const dt1 = hist.delta_t1;
                    const dt2 = hist.delta_t2;
                    const t1str = `${hist.t1_refs}${dt1 !== null && dt1 !== undefined ? '(<span style="color:' + (dt1 >= 0 ? 'var(--success)' : 'var(--danger)') + '">' + (dt1 >= 0 ? '+' : '') + dt1 + '</span>)' : ''}`;
                    const t2str = `${hist.t2_refs}${dt2 !== null && dt2 !== undefined ? '(<span style="color:' + (dt2 >= 0 ? 'var(--success)' : 'var(--danger)') + '">' + (dt2 >= 0 ? '+' : '') + dt2 + '</span>)' : ''}`;
                    content = `${t1str} / ${t2str}`;
                    className = 'mode-jade';
                }
            }

            cells += `<td class="${className}${currentMode === 'refs' ? ' mode-refs-cell' : ''}">${content}</td>`;
        });

        tr.innerHTML = cells;
        fragment.appendChild(tr);
    });

    body.innerHTML = '';
    body.appendChild(fragment);
}

function formatNumber(num) {
    if (num === null || num === undefined || num === 0) return "—";
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function switchMode(mode) {
    currentMode = mode;
    // Reset sort khi đổi mode
    if (mode !== 'refs') {
        sortState = { col: null, dir: 0 };
    }
    document.querySelectorAll('.toggle-group button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    renderTable();
}

function sortByRefDate(dateStr) {
    if (sortState.col === dateStr) {
        // Toggle: desc → asc → default
        sortState.dir = sortState.dir === 1 ? -1 : (sortState.dir === -1 ? 0 : 1);
        if (sortState.dir === 0) sortState.col = null;
    } else {
        sortState.col = dateStr;
        sortState.dir = 1; // Bắt đầu bằng desc (nhiều nhất lên trên)
    }
    renderTable();
}

function openAliasEdit(username, currentAlias) {
    const isUnresolved = currentAlias.includes('[?]');
    const msg = isUnresolved
        ? `⚠️ Username "${username}" chưa xác định được alias tự động.\nNhập alias đúng cho người này:`
        : `Sửa alias cho "${username}":\n(Hiện tại: ${currentAlias})`;
    const defaultVal = isUnresolved ? '' : currentAlias;
    const newAlias = prompt(msg, defaultVal);
    if (newAlias === null || newAlias.trim() === '') return;
    if (newAlias.trim() === currentAlias) return;
    saveAlias(username, newAlias.trim());
}

// ─── TEAM MANAGEMENT ──────────────────────────────────────────────────────────

let pendingTeamAction = null; // { username, alias, checkbox }

function handleTeamToggle(checkbox, username, alias) {
    if (checkbox.checked) {
        // Tick → mở modal chọn role
        pendingTeamAction = { username, alias, checkbox };
        document.getElementById('team-modal-alias').textContent = `Alias: ${alias}`;
        // Reset radio về T1
        document.querySelector('input[name="team-role"][value="T1"]').checked = true;
        const modal = document.getElementById('team-role-modal');
        modal.style.display = 'flex';
    } else {
        // Bỏ tick → loại khỏi team ngay, không cần modal
        setTeamMember(username, alias, false, null, checkbox);
    }
}

function confirmSetTeam() {
    if (!pendingTeamAction) return;
    const role = document.querySelector('input[name="team-role"]:checked').value;
    const { username, alias, checkbox } = pendingTeamAction;
    document.getElementById('team-role-modal').style.display = 'none';
    setTeamMember(username, alias, true, role, checkbox);
    pendingTeamAction = null;
}

function cancelSetTeam() {
    if (pendingTeamAction) {
        // Revert checkbox về trạng thái cũ
        pendingTeamAction.checkbox.checked = false;
        pendingTeamAction = null;
    }
    document.getElementById('team-role-modal').style.display = 'none';
}

async function setTeamMember(username, alias, isTeam, role, checkbox) {
    try {
        const res = await fetch('/api/team-members/set-team', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, alias, is_team: isTeam, role })
        });

        if (res.ok) {
            // Cập nhật local data để re-render không cần reload
            if (trackerData) {
                // trackerData.users có thể là object hoặc array tùy server version
                const users = Array.isArray(trackerData.users) ? trackerData.users : Object.values(trackerData.users);
                const user = users.find(u => u.username === username);
                if (user) {
                    user.is_team = isTeam;
                    user.team_role = isTeam ? role : null;
                }
            }
            renderTable();
        } else {
            // Revert checkbox nếu lỗi
            checkbox.checked = !isTeam;
            const err = await res.json();
            alert('Lỗi: ' + (err.detail || 'Không thể cập nhật team'));
        }
    } catch (err) {
        checkbox.checked = !isTeam;
        console.error(err);
        alert('Lỗi kết nối');
    }
}

async function saveAlias(username, alias) {
    try {
        const res = await fetch('/api/team-members/alias', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, alias })
        });
        if (res.ok) {
            if (trackerData) {
                const users = Array.isArray(trackerData.users) ? trackerData.users : Object.values(trackerData.users);
                const user = users.find(u => u.username === username);
                if (user) user.alias = alias;
                renderTable();
            }
        } else {
            alert("Lỗi khi lưu alias");
        }
    } catch (err) {
        console.error(err);
        alert("Lỗi kết nối");
    }
}

// Event Listeners
document.getElementById('search-input').addEventListener('input', renderTable);
document.getElementById('filter-select').addEventListener('change', renderTable);

document.addEventListener('DOMContentLoaded', loadTracker);
