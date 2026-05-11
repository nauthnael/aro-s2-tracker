let cachedMembers = [];
let sortState = { col: null, dir: 'asc' };

// ─── FETCH & RENDER ──────────────────────────────────────────────────────────

async function fetchTeam() {
    try {
        const res = await fetch('/api/team-members/with-stats');
        cachedMembers = await res.json();
        renderTeam(cachedMembers);
    } catch (err) {
        console.error("Error fetching team:", err);
    }
}

function renderTeam(members) {
    const toRender = sortState.col
        ? sortMembers(members, sortState.col, sortState.dir)
        : members;

    const teamBody = document.getElementById('team-body');
    teamBody.innerHTML = '';

    if (toRender.length === 0) {
        teamBody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--text-muted)">Chưa có thành viên. Quản lý team tại màn hình Tracker.</td></tr>';
        updatePrizeBanner([]);
        return;
    }

    toRender.forEach((member, index) => {
        const s = member.stats || {};
        const inTop100 = member.stats !== null;

        const row = document.createElement('tr');
        if (member.role === 'LEADER') row.className = 'row-nau';
        else if (member.role === 'T1') row.className = 'row-team';

        const rankDisplay = inTop100
            ? '#' + s.rank
            : '<span style="color:var(--text-muted);font-size:0.75rem">Ngoài top 100</span>';

        row.innerHTML = `
            <td style="color:var(--text-muted);font-size:0.85rem;text-align:center">${index + 1}</td>
            <td>${member.alias}</td>
            <td><span class="badge ${getRoleBadge(member.role)}">${member.role}</span></td>
            <td>${rankDisplay}</td>
            <td>${inTop100 ? formatNumber(s.jade) : '—'}</td>
            <td class="${(s.delta || 0) >= 0 ? 'positive' : 'negative'}">
                ${inTop100 && s.delta !== null && s.delta !== undefined
                    ? (s.delta >= 0 ? '+' : '') + formatNumber(s.delta)
                    : '—'}
            </td>
            <td>${inTop100 && s.w_rate !== null ? formatNumber(Math.round(s.w_rate)) : '—'}</td>
            <td>${inTop100 ? formatNumber(s.proj_may31) : '—'}</td>
            <td style="color:var(--success)">${inTop100 ? (s.prize_est || '—') : '—'}</td>
        `;
        teamBody.appendChild(row);
    });

    updateSortIcons();
    attachSortListeners();
    updatePrizeBanner(toRender);
}

// ─── SORT ─────────────────────────────────────────────────────────────────────

function sortMembers(members, col, dir) {
    const sorted = [...members];
    sorted.sort((a, b) => {
        const sa = a.stats || {};
        const sb = b.stats || {};
        let va, vb;

        switch (col) {
            case 'alias': va = a.alias || ''; vb = b.alias || ''; break;
            case 'role':  va = a.role  || ''; vb = b.role  || ''; break;
            case 'rank':  va = sa.rank     ?? 999;       vb = sb.rank     ?? 999;       break;
            case 'jade':  va = sa.jade     ?? -1;        vb = sb.jade     ?? -1;        break;
            case 'delta': va = sa.delta    ?? -Infinity; vb = sb.delta    ?? -Infinity; break;
            case 'w_rate':va = sa.w_rate   ?? -1;        vb = sb.w_rate   ?? -1;        break;
            case 'proj':  va = sa.proj_may31 ?? -1;      vb = sb.proj_may31 ?? -1;      break;
            case 'prize': va = parsePrize(sa.prize_est); vb = parsePrize(sb.prize_est); break;
            default: return 0;
        }

        if (typeof va === 'string') {
            return dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
        }
        return dir === 'asc' ? va - vb : vb - va;
    });
    return sorted;
}

function attachSortListeners() {
    document.querySelectorAll('thead th[data-col]').forEach(th => {
        const newTh = th.cloneNode(true);
        th.parentNode.replaceChild(newTh, th);
        newTh.style.cursor = 'pointer';
        newTh.style.userSelect = 'none';
        newTh.addEventListener('click', () => {
            const col = newTh.getAttribute('data-col');
            if (sortState.col === col) {
                sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
            } else {
                sortState.col = col;
                sortState.dir = 'asc';
            }
            renderTeam(cachedMembers);
        });
    });
}

function updateSortIcons() {
    document.querySelectorAll('thead th[data-col]').forEach(th => {
        const icon = th.querySelector('.sort-icon');
        if (!icon) return;
        const col = th.getAttribute('data-col');
        if (sortState.col === col) {
            icon.textContent = sortState.dir === 'asc' ? '↑' : '↓';
            icon.style.color = '#3b82f6';
        } else {
            icon.textContent = '↕';
            icon.style.color = 'var(--text-muted)';
        }
    });
}

// ─── PRIZE BANNER ─────────────────────────────────────────────────────────────

function updatePrizeBanner(members) {
    let total = 0;
    let countInTop100 = 0;

    members.forEach(m => {
        const prize = parsePrize((m.stats || {}).prize_est);
        if (prize > 0) {
            total += prize;
            countInTop100++;
        }
    });

    document.getElementById('prize-total').textContent =
        total > 0 ? '$' + total.toLocaleString() : '—';

    const note = document.getElementById('prize-members-note');
    if (total > 0) {
        const outCount = members.length - countInTop100;
        note.textContent = `(${countInTop100} thành viên trong top 100${outCount > 0 ? `, ${outCount} ngoài top` : ''})`;
    } else {
        note.textContent = '';
    }
}

// ─── HELPERS ──────────────────────────────────────────────────────────────────

function getRoleBadge(role) {
    if (role === 'LEADER') return 'badge-info';
    if (role === 'T1') return 'badge-team';
    return 'badge-muted';
}

function formatNumber(num) {
    if (num === null || num === undefined || num === 0) return "—";
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function parsePrize(str) {
    if (!str || str === '—' || str === 'N/A' || str === 'TBD') return -1;
    return parseInt(str.replace(/[^0-9]/g, '')) || -1;
}

// ─── INIT ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', fetchTeam);
