async function fetchDashboard() {
    try {
        const response = await fetch('/api/dashboard');
        const data = await response.json();
        
        if (data.message === "No data available") {
            document.getElementById('latest-date').innerText = "Chưa có dữ liệu. Vui lòng import.";
            return;
        }

        const { snapshot, nau, top10, alerts } = data;
        window.allRankings = top10; // Cache for search
        
        document.getElementById('latest-date').innerText = `Cập nhật lúc: ${snapshot.date}`;
        
        if (nau) {
            document.getElementById('nau-rank').innerText = `#${nau.rank}`;
            document.getElementById('nau-jade').innerText = formatNumber(nau.jade);
            document.getElementById('nau-delta').innerText = `+${formatNumber(nau.delta)}`;
            document.getElementById('nau-wrate').innerText = formatNumber(Math.round(nau.w_rate));
            document.getElementById('nau-proj').innerText = formatNumber(nau.proj_may31);
            document.getElementById('nau-prize').innerText = nau.prize_est;
        }

        renderLeaderboardRows(top10);

        const alertsList = document.getElementById('alerts-list');
        alertsList.innerHTML = '';
        alerts.forEach(alert => {
            const div = document.createElement('div');
            div.style.marginBottom = '0.75rem';
            div.style.padding = '0.5rem';
            div.style.borderRadius = '0.25rem';
            div.style.background = 'rgba(255,255,255,0.05)';
            
            const badgeClass = alert.level === 'RED' ? 'badge-red' : (alert.level === 'YELLOW' ? 'badge-yellow' : 'badge-info');
            const snapshotDate = data.snapshot?.date || '';
            div.innerHTML = `<span class="badge ${badgeClass}">${alert.level}</span> <span style="color: var(--text-muted); font-size: 0.75rem; margin: 0 0.4rem;">${snapshotDate}</span><span style="font-size: 0.875rem">${alert.message}</span>`;
            alertsList.appendChild(div);
        });

    } catch (err) {
        console.error("Error fetching dashboard:", err);
    }
}

function renderLeaderboardRows(users) {
    const top10Body = document.getElementById('top10-body');
    top10Body.innerHTML = '';
    users.forEach(user => {
        const row = document.createElement('tr');
        if (user.username === "nau***@gmail.com") row.className = 'row-nau';
        else if (user.is_team) row.className = 'row-team';
        
        const deltaClass = (user.delta || 0) >= 0 ? 'mode-delta-pos' : 'mode-delta-neg';
        const verdict = getVerdict(user);

        row.innerHTML = `
            <td>${user.rank}</td>
            <td>${user.alias}</td>
            <td>${formatNumber(user.jade)}</td>
            <td class="${deltaClass}">${user.delta !== null ? (user.delta >= 0 ? '+' : '') + formatNumber(user.delta) : '—'}</td>
            <td>${user.w_rate !== null ? formatNumber(Math.round(user.w_rate)) : '—'}</td>
            <td title="${user.t1_refs} T1 + ${user.t2_refs} T2">
                ${user.t1_refs + user.t2_refs}
                <span style="color:var(--text-muted);font-size:0.75rem;display:block">
                    ${user.t1_refs}T1 + ${user.t2_refs}T2
                </span>
            </td>
            <td>${verdict}</td>
            <td style="color:var(--success)">${user.prize_est || '—'}</td>
        `;
        top10Body.appendChild(row);
    });
}

function getVerdict(user) {
    if (user.is_team) return '<span class="badge badge-team">TEAM</span>';
    const totalRefs = user.t1_refs + user.t2_refs;
    if (totalRefs > 50 && user.w_rate !== null && user.w_rate < 5000) {
        return '<span class="badge badge-red">Farm</span>';
    }
    return '<span class="badge mode-muted">—</span>';
}

function filterLeaderboard(searchText) {
    if (!window.allRankings) return;
    const filtered = window.allRankings.filter(u => 
        (u.alias || u.username).toLowerCase().includes(searchText.toLowerCase())
    );
    renderLeaderboardRows(filtered);
}

function formatNumber(num) {
    if (num === null || num === undefined) return "-";
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function showImportModal() {
    document.getElementById('import-modal').style.display = 'flex';
    document.getElementById('import-date').valueAsDate = new Date();
    document.getElementById('import-step-1').style.display = 'block';
    document.getElementById('import-step-2').style.display = 'none';
    loadSnapshotList();
}

function hideImportModal() {
    document.getElementById('import-modal').style.display = 'none';
}

async function loadSnapshotList() {
    try {
        const res = await fetch('/api/import/snapshots');
        const snapshots = await res.json();
        const container = document.getElementById('snapshot-list');
        if (!container) return;

        // Hiển thị 5 snapshot gần nhất, mới nhất lên trên
        const recent = [...snapshots].reverse().slice(0, 5);

        container.innerHTML = recent.map(s => `
            <div style="display:flex; justify-content:space-between; align-items:center;
                        background:var(--background); padding:0.5rem 0.75rem;
                        border-radius:0.375rem; font-size:0.875rem;">
                <span>
                    <span style="color:white; font-weight:500">${s.date}</span>
                    ${s.is_delayed ? '<span style="color:#f59e0b; font-size:0.75rem; margin-left:0.5rem">⚠️ delay</span>' : ''}
                    <span style="color:var(--text-muted); margin-left:0.5rem; font-size:0.75rem">
                        (id: ${s.id})
                    </span>
                </span>
                <button onclick="deleteSnapshot(${s.id}, '${s.date}')"
                    style="background:rgba(239,68,68,0.15); color:#ef4444; border:none;
                           padding:0.25rem 0.6rem; border-radius:0.25rem; cursor:pointer;
                           font-size:0.75rem;">
                    Xóa
                </button>
            </div>
        `).join('');
    } catch(err) {
        console.error('Error loading snapshots:', err);
    }
}

async function deleteSnapshot(snapshotId, dateStr) {
    if (!confirm(
        `Xóa snapshot ngày ${dateStr}?\n\n` +
        `Toàn bộ dữ liệu BXH ngày này sẽ bị xóa khỏi DB.\n` +
        `Sau đó import lại nếu cần.`
    )) return;

    try {
        const res = await fetch(`/api/import/snapshot/${snapshotId}`, { method: 'DELETE' });
        if (res.ok) {
            const data = await res.json();
            alert(`✅ ${data.message}`);
            loadSnapshotList();   // Refresh list
            fetchDashboard();      // Refresh dashboard data
        } else {
            const err = await res.json();
            alert('Lỗi: ' + (err.detail || 'Không thể xóa'));
        }
    } catch(err) {
        console.error(err);
        alert('Lỗi kết nối');
    }
}

async function previewImport() {
    const date = document.getElementById('import-date').value;
    const rawInput = document.getElementById('json-input').value.trim();
    if (!date || !rawInput) { alert("Vui lòng nhập đủ ngày và data"); return; }
    
    const btn = document.getElementById('preview-btn');
    btn.innerText = "Đang parse...";
    btn.disabled = true;
    
    try {
        const response = await fetch('/api/import/preview-raw', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                raw_input: rawInput,
                import_date: date 
            })
        });
        
        const preview = await response.json();
        if (!response.ok) { alert("Error: " + preview.detail); return; }
        
        // Hiện input type để user biết đã detect đúng
        const inputTypeLabel = preview.input_type === 'html' ? '🌐 HTML table' : '📋 JSON';
        
        const content = document.getElementById('import-preview-content');
        content.innerHTML = `
            <div class="preview-summary" style="background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                <h3 style="color: var(--success)">✅ Parse thành công</h3>
                <p>📅 Ngày: <strong>${preview.date}</strong></p>
                <p>📥 Định dạng: <strong>${inputTypeLabel}</strong></p>
                <p>👥 Tổng users: <strong>${preview.total_users}</strong></p>
                ${preview.warning ? `<p style="color: var(--warning)">⚠️ ${preview.warning}</p>` : ''}
            </div>
            <h4>Xem trước 5 dòng đầu:</h4>
            <table style="font-size: 0.8rem; margin-top: 0.5rem;">
                <thead><tr><th>Rank</th><th>User</th><th>Jade</th><th>T1</th><th>T2</th></tr></thead>
                <tbody>
                    ${preview.preview_top5.map(u => `
                        <tr><td>${u.rank}</td><td>${u.username}</td><td>${formatNumber(u.jade)}</td><td>${u.t1_refs}</td><td>${u.t2_refs}</td></tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        
        document.getElementById('import-step-1').style.display = 'none';
        document.getElementById('import-step-2').style.display = 'block';
        
        // Lưu rawInput để dùng khi confirmImport
        window._pendingRawInput = rawInput;
        
    } catch (err) {
        alert("Lỗi parse: " + err.message);
    } finally {
        btn.innerText = "🔍 Parse & Preview";
        btn.disabled = false;
    }
}

function backToStep1() {
    document.getElementById('import-step-1').style.display = 'block';
    document.getElementById('import-step-2').style.display = 'none';
}

async function confirmImport() {
    const btn = document.getElementById('import-btn');
    const date = document.getElementById('import-date').value;
    const rawInput = window._pendingRawInput || document.getElementById('json-input').value.trim();
    const isDelayed = document.getElementById('import-delayed').checked;
    
    try {
        btn.innerText = "Importing...";
        btn.disabled = true;
        
        const response = await fetch('/api/import/import-raw', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                raw_input: rawInput,
                import_date: date,
                is_delayed: isDelayed,
                note: ""
            })
        });
        
        const result = await response.json();
        if (response.ok) {
            alert(result.message);
            hideImportModal();
            window._pendingRawInput = null;
            fetchDashboard();
        } else {
            alert("Error: " + result.detail);
        }
    } catch (err) {
        alert("Error during import");
    } finally {
        btn.innerText = "✅ Confirm Import";
        btn.disabled = false;
    }
}

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    fetchDashboard();
});
