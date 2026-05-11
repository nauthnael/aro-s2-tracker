# Brief 15 — Fix team.js bị truncate (sort / prize banner / header lệch)
> PM: Adam | Dev: atigravity | Priority: P0  
> Root cause đã xác định qua Chrome debug. Chỉ sửa `static/team.js`. Không đụng backend, không đụng `team.html`.

---

## ROOT CAUSE

File `static/team.js` hiện tại bị **truncate ở dòng 172** — đứt giữa câu lệnh `document.getE...` bên trong `editMember()`. Hậu quả:

- Browser gặp syntax error → **chỉ load được phần code trước lỗi** (tức `fetchTeam` cũ ở dòng 1–13)
- `cachedMembers`, `sortState`, `renderTeam`, `sortMembers`, `attachSortListeners`, `updatePrizeBanner` đều **không được define**
- `fetchTeam` cũ vẫn render rows với **9 `<td>`** trong khi `<thead>` đã có **10 `<th>`** → cột "Hành động" bị đẩy lệch ra ngoài

Đã verify qua `typeof window.renderTeam === 'undefined'` và `typeof window.cachedMembers === 'undefined'` trong Chrome DevTools.

---

## FIX — Thay toàn bộ `static/team.js`

Viết lại file hoàn chỉnh. Code dưới đây là **toàn bộ nội dung file**, thay thế file hiện tại:

```javascript
let editingMemberId = null;
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
        teamBody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-muted)">Chưa có thành viên. Bấm "+ Thêm Thành Viên" để thêm.</td></tr>';
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
            <td>
                <button onclick="editMember(${member.id})"
                    style="background:rgba(59,130,246,0.2);color:#3b82f6;border:none;padding:0.25rem 0.5rem;border-radius:0.25rem;cursor:pointer;font-size:0.75rem;margin-right:0.25rem">
                    Sửa
                </button>
                <button onclick="deleteMember(${member.id}, '${member.alias}')"
                    style="background:rgba(239,68,68,0.2);color:#ef4444;border:none;padding:0.25rem 0.5rem;border-radius:0.25rem;cursor:pointer;font-size:0.75rem">
                    Xóa
                </button>
            </td>
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

// ─── MEMBER MODAL ─────────────────────────────────────────────────────────────

async function editMember(memberId) {
    const res = await fetch('/api/team-members');
    const members = await res.json();
    const member = members.find(m => m.id === memberId);
    if (!member) { alert("Không tìm thấy thành viên"); return; }

    document.getElementById('member-username').value = member.username;
    document.getElementById('member-alias').value = member.alias;
    document.getElementById('member-role').value = member.role;
    document.getElementById('member-rank').value = member.bxh_rank || '';
    document.getElementById('member-note').value = member.note || '';

    editingMemberId = memberId;
    document.getElementById('modal-title').textContent = 'Sửa Thành Viên';
    document.getElementById('save-member-btn').textContent = 'Cập Nhật';

    showMemberModal();
}

function showMemberModal() {
    document.getElementById('member-modal').style.display = 'flex';
}

function hideMemberModal() {
    document.getElementById('member-modal').style.display = 'none';
    editingMemberId = null;
    document.getElementById('modal-title').textContent = 'Thêm Thành Viên';
    document.getElementById('save-member-btn').textContent = 'Lưu';

    document.getElementById('member-username').value = '';
    document.getElementById('member-alias').value = '';
    document.getElementById('member-role').value = 'T1';
    document.getElementById('member-rank').value = '';
    document.getElementById('member-note').value = '';
}

async function saveMember() {
    const username = document.getElementById('member-username').value.trim();
    const alias    = document.getElementById('member-alias').value.trim();
    const role     = document.getElementById('member-role').value;
    const bxh_rank = document.getElementById('member-rank').value
                     ? parseInt(document.getElementById('member-rank').value)
                     : null;
    const note = document.getElementById('member-note').value.trim();

    if (!username || !alias) {
        alert("Vui lòng điền đủ Username và Alias");
        return;
    }

    try {
        let response;
        const payload = { username, alias, role, bxh_rank, note };

        if (editingMemberId) {
            response = await fetch(`/api/team-members/${editingMemberId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else {
            response = await fetch('/api/team-members', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        }

        if (response.ok) {
            hideMemberModal();
            fetchTeam();
        } else {
            const err = await response.json();
            alert("Lỗi: " + (err.detail || "Không thể lưu thành viên"));
        }
    } catch (err) {
        console.error(err);
    }
}

async function deleteMember(memberId, alias) {
    if (!confirm(`Xóa thành viên "${alias}" khỏi team?`)) return;
    try {
        const res = await fetch(`/api/team-members/${memberId}`, { method: 'DELETE' });
        if (res.ok) {
            fetchTeam();
        } else {
            alert("Lỗi khi xóa thành viên");
        }
    } catch (err) {
        console.error(err);
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
```

---

## LƯU Ý QUAN TRỌNG KHI THAY FILE

- **Copy toàn bộ** đoạn code trên vào file `static/team.js`, xóa sạch nội dung cũ
- **Không sửa `team.html`** — file HTML đã đúng từ Brief 14 (10 `<th>`, prize-banner div đã có)
- Sau khi save: **Ctrl+Shift+R** (hard refresh) trên browser, không chỉ F5

---

## EXPECTED RESULT SAU FIX

Dựa trên data API hiện tại (đã verify):
- Prize banner phải hiển thị **$2,900** — tổng của: dan*** $2,000 + nha*** $200 + caf*** $200 + kdl*** $50 + inf*** $200 + qua[TEAM] $200 + hun[TEAM] $50
- Note: "(7 thành viên trong top 100, 5 ngoài top)"

---

## VERIFY CHECKLIST

**Prize Banner:**
- [ ] Hiển thị `$2,900` (không phải `—`)
- [ ] Note đúng: `(7 thành viên trong top 100, 5 ngoài top)`

**Sort:**
- [ ] Click header "Rank" → sort tăng dần (rank nhỏ lên trên), click lại → giảm dần
- [ ] Click header "Prize" → sort đúng theo giá trị số ($2,000 > $200 > $50), không phải alphabetical
- [ ] Click header "Alias" → sort A→Z
- [ ] Members "Ngoài top 100" xếp cuối khi sort theo cột số
- [ ] Icon ↑/↓/↕ đổi đúng theo chiều sort
- [ ] Sort giữ nguyên sau khi đóng/mở modal Sửa

**Header alignment:**
- [ ] Cột "Hành động" nằm đúng vị trí cuối, không bị lệch ra ngoài bảng
- [ ] Mỗi row có đúng 10 `<td>` tương ứng 10 `<th>`

**Regression:**
- [ ] Nút Sửa mở đúng modal với data thành viên đó
- [ ] Nút Xóa xác nhận và xóa đúng
- [ ] Thêm thành viên mới vẫn hoạt động
- [ ] STT (cột #) hiển thị 1, 2, 3… và cập nhật lại sau khi sort

---

## YÊU CẦU SAU KHI HOÀN THÀNH

Sau khi implement và verify xong, AG tạo file `Review_Report_Brief_15.md` trong thư mục project, ghi rõ:
- Xác nhận file `team.js` đã được thay toàn bộ (không còn bị truncate)
- Kết quả verify từng item trong checklist (pass/fail)
- Bất kỳ phát hiện hoặc thay đổi nào ngoài scope brief (nếu có)
