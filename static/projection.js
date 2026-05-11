let allUsers = [];
let currentFilter = 'all';

// ─── UTILS ───────────────────────────────────────────────────────────────────

function fmt(n) {
    if (n === null || n === undefined) return '—';
    return Number(n).toLocaleString('en-US');
}

function getRoleBadge(role) {
    if (!role) return '';
    const map = { LEADER: 'badge-leader', T1: 'badge-t1', T2: 'badge-t2' };
    return `<span class="badge ${map[role] || ''}">${role}</span>`;
}

// ─── FILTER ──────────────────────────────────────────────────────────────────

function setFilter(f) {
    currentFilter = f;
    document.getElementById('btn-all').className = f === 'all'
        ? 'btn btn-primary'
        : 'btn';
    document.getElementById('btn-all').style.cssText = f === 'all'
        ? 'font-size:0.8rem;padding:0.3rem 0.75rem;'
        : 'font-size:0.8rem;padding:0.3rem 0.75rem;background:var(--surface);border:1px solid var(--text-muted);color:var(--text);';
    document.getElementById('btn-team').className = f === 'team'
        ? 'btn btn-primary'
        : 'btn';
    document.getElementById('btn-team').style.cssText = f === 'team'
        ? 'font-size:0.8rem;padding:0.3rem 0.75rem;'
        : 'font-size:0.8rem;padding:0.3rem 0.75rem;background:var(--surface);border:1px solid var(--text-muted);color:var(--text);';

    const toShow = f === 'team' ? allUsers.filter(u => u.is_team) : allUsers;
    renderTable(toShow);
}

// ─── RENDER ──────────────────────────────────────────────────────────────────

function renderTable(users) {
    const body = document.getElementById('proj-body');
    body.innerHTML = '';

    if (!users.length) {
        body.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:2rem;color:var(--text-muted)">Không có dữ liệu</td></tr>';
        return;
    }

    users.forEach(u => {
        const inTop50 = u.proj_rank <= 50;
        const isTeam = u.is_team;

        // Row style
        let rowStyle = '';
        if (u.team_role === 'LEADER') rowStyle = 'background:rgba(99,102,241,0.12);';
        else if (isTeam) rowStyle = 'background:rgba(16,185,129,0.07);';

        // Rank change arrow
        const rankDiff = u.current_rank - u.proj_rank;
        let rankArrow = '';
        if (rankDiff > 0) rankArrow = `<span style="color:var(--success);font-size:0.75rem"> ▲${rankDiff}</span>`;
        else if (rankDiff < 0) rankArrow = `<span style="color:var(--danger);font-size:0.75rem"> ▼${Math.abs(rankDiff)}</span>`;

        // Proj rank badge
        const projRankColor = inTop50 ? 'var(--success)' : 'var(--text-muted)';
        const projRankStyle = inTop50
            ? 'font-weight:700; color:var(--success);'
            : 'color:var(--text-muted);';

        // Daily needed cell
        let dailyCell;
        if (inTop50) {
            dailyCell = `<td style="text-align:right; color:var(--success); font-weight:600;">✓ Top 50</td>`;
        } else if (isTeam) {
            dailyCell = `<td style="text-align:right; color:var(--danger); font-weight:600;">+${fmt(u.daily_needed)}</td>`;
        } else {
            dailyCell = `<td style="text-align:right; color:var(--text-muted);">+${fmt(u.daily_needed)}</td>`;
        }

        // Jade gap cell
        let gapCell;
        if (inTop50) {
            gapCell = `<td style="text-align:right; color:var(--success);">—</td>`;
        } else if (isTeam) {
            gapCell = `<td style="text-align:right; color:var(--warning);">${fmt(u.jade_gap_to_50)}</td>`;
        } else {
            gapCell = `<td style="text-align:right; color:var(--text-muted);">${fmt(u.jade_gap_to_50)}</td>`;
        }

        const row = document.createElement('tr');
        row.style.cssText = rowStyle + 'border-bottom:1px solid rgba(255,255,255,0.05);';
        row.innerHTML = `
            <td style="text-align:center; padding:0.6rem 0.5rem;">
                <span style="${projRankStyle}">#${u.proj_rank}</span>${rankArrow}
            </td>
            <td style="padding:0.6rem 0.5rem; font-weight:${isTeam ? '600' : '400'};">
                ${u.alias}${isTeam ? ' 🏷️' : ''}
            </td>
            <td style="padding:0.6rem 0.5rem; text-align:center;">${getRoleBadge(u.team_role)}</td>
            <td style="padding:0.6rem 0.5rem; text-align:center; color:var(--text-muted);">#${u.current_rank}</td>
            <td style="padding:0.6rem 0.5rem; text-align:right;">${fmt(u.current_jade)}</td>
            <td style="padding:0.6rem 0.5rem; text-align:right; color:${u.w_rate >= 0 ? 'var(--success)' : 'var(--danger)'};">
                ${u.w_rate >= 0 ? '+' : ''}${fmt(u.w_rate)}
            </td>
            <td style="padding:0.6rem 0.5rem; text-align:right; font-weight:600; color:${projRankColor};">
                ${fmt(u.proj_jade)}
            </td>
            ${gapCell}
            ${dailyCell}
        `;
        body.appendChild(row);
    });
}

// ─── FETCH & INIT ─────────────────────────────────────────────────────────────

async function fetchProjection() {
    try {
        const res = await fetch('/api/projection');
        const data = await res.json();

        if (data.error) {
            document.getElementById('proj-body').innerHTML =
                `<tr><td colspan="9" style="text-align:center;padding:2rem;color:var(--danger)">${data.error}</td></tr>`;
            return;
        }

        allUsers = data.users;

        // Update summary cards
        document.getElementById('days-remaining').textContent = data.days_remaining;
        document.getElementById('rank50-jade').textContent = fmt(data.rank50_projected_jade);
        document.getElementById('snapshot-date').textContent = data.latest_snapshot_date;

        const teamIn50 = data.users.filter(u => u.is_team && u.proj_rank <= 50).length;
        document.getElementById('team-in-top50').textContent = teamIn50;

        renderTable(allUsers);

    } catch (err) {
        console.error('Projection fetch error:', err);
        document.getElementById('proj-body').innerHTML =
            `<tr><td colspan="9" style="text-align:center;padding:2rem;color:var(--danger)">Lỗi tải dữ liệu</td></tr>`;
    }
}

document.addEventListener('DOMContentLoaded', fetchProjection);
