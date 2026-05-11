// Known duplicate usernames (sync với alias_resolver.py)
const KNOWN_USERNAMES = [
    "mal***@gmail.com", "tra***@gmail.com", "qua***@gmail.com",
    "kha***@gmail.com", "rom***@gmail.com", "ben***@gmail.com",
    "hun***@gmail.com", "thu***@gmail.com"
];

let allAliases = [];

async function loadAliases() {
    try {
        const res = await fetch('/api/aliases');
        allAliases = await res.json();
        updateStats();
        renderAliases();
    } catch(err) {
        console.error('Error loading aliases:', err);
    }
}

function updateStats() {
    const ghost = allAliases.filter(a => a.is_ghost).length;
    const active = allAliases.filter(a => !a.is_ghost).length;
    document.getElementById('alias-stats').textContent =
        `${allAliases.length} tổng | ${active} active | ${ghost} ghost`;
}

function renderAliases() {
    const search = document.getElementById('alias-search').value.toLowerCase();
    const filter = document.getElementById('alias-filter').value;

    let filtered = allAliases.filter(a => {
        const matchSearch = !search ||
            a.alias.toLowerCase().includes(search) ||
            a.username.toLowerCase().includes(search);
        const matchFilter =
            filter === 'all' ? true :
            filter === 'ghost' ? a.is_ghost :
            filter === 'team' ? a.is_team :
            filter === 'active' ? !a.is_ghost :
            filter === 'known' ? KNOWN_USERNAMES.includes(a.username) : true;
        return matchSearch && matchFilter;
    });

    const body = document.getElementById('alias-table-body');

    if (filtered.length === 0) {
        body.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted)">Không tìm thấy</td></tr>';
        return;
    }

    body.innerHTML = filtered.map(a => {
        const statusBadge = a.is_ghost
            ? '<span style="color:#6b7280; font-size:0.75rem;">👻 ghost</span>'
            : a.is_team
                ? `<span style="color:var(--accent); font-size:0.75rem;">⭐ ${a.team_role || 'team'}</span>`
                : '<span style="color:var(--success); font-size:0.75rem;">✅ active</span>';
        const isKnown = KNOWN_USERNAMES.includes(a.username);
        const aliasCell = isKnown
            ? `<span style="color:white; font-weight:500">${a.alias}</span> <span style="color:var(--accent); font-size:0.7rem;">🔑</span>`
            : `<span style="color:white">${a.alias}</span>`;
        const jadeStr = a.max_jade > 0
            ? a.max_jade.toLocaleString()
            : '<span style="color:#6b7280">—</span>';
        const rankStr = a.best_rank < 999
            ? '#' + a.best_rank
            : '<span style="color:#6b7280">—</span>';
        const rowStyle = a.is_ghost ? 'opacity:0.45;' : '';

        return `<tr style="${rowStyle}">
            <td>${aliasCell}</td>
            <td style="color:var(--text-muted); font-size:0.875rem;">${a.username}</td>
            <td>${jadeStr}</td>
            <td>${rankStr}</td>
            <td style="color:var(--text-muted)">${a.days_present}</td>
            <td>${a.is_team ? (a.team_role || '—') : '—'}</td>
            <td>${statusBadge}</td>
        </tr>`;
    }).join('');
}

async function deleteGhosts() {
    const ghost = allAliases.filter(a => a.is_ghost);
    if (ghost.length === 0) { alert('Không có ghost alias nào.'); return; }
    if (!confirm(`Xóa ${ghost.length} ghost aliases?\n\n${ghost.map(a=>a.alias).join(', ')}\n\nHành động này không thể hoàn tác.`)) return;

    const btn = document.getElementById('delete-ghost-btn');
    btn.disabled = true;
    btn.textContent = 'Đang xóa...';

    try {
        const res = await fetch('/api/aliases/ghost', { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            alert(`✅ Đã xóa ${data.deleted_aliases} ghost aliases (${data.deleted_records} records)`);
            await loadAliases();  // Refresh
        } else {
            alert('Lỗi: ' + (data.detail || 'Không thể xóa'));
        }
    } catch(err) {
        alert('Lỗi kết nối');
    } finally {
        btn.disabled = false;
        btn.textContent = '🗑️ Xóa Ghost Aliases';
    }
}

document.addEventListener('DOMContentLoaded', loadAliases);
