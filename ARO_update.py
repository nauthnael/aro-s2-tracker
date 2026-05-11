#!/usr/bin/env python3
"""
ARO Sprint 2 — Daily Update Script (ARO_update.py)
====================================================
Đọc data từ sheet INPUT, tính toán toàn bộ metrics, ghi vào HISTORY + TRACKER + DASHBOARD.
Claude chạy script này mỗi ngày rồi đọc DASHBOARD để viết báo cáo.

Usage:
    python ARO_update.py                    # Đọc từ INPUT sheet + ngày hiện tại
    python ARO_update.py --date 2026-04-29  # Override ngày
    python ARO_update.py --json data.json   # Đọc từ JSON file thay vì INPUT sheet
    python ARO_update.py --skip-input       # Chỉ recompute từ HISTORY (không cần INPUT)
"""

import os, re, sys, json, argparse
from datetime import date, datetime, timedelta
from collections import defaultdict
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR    = r"C:\Users\Administrator\OneDrive\Documents\ARO S2 top 100 tracking"
MASTER_FILE = os.path.join(BASE_DIR, "ARO_MASTER.xlsx")

# ─── Constants ────────────────────────────────────────────────────────────────
EVENT_END   = date(2026, 5, 31)

PRIZE_TIERS = [(1,1,5000),(2,5,2000),(6,10,1000),(11,50,200),(51,100,50)]

KNOWN_FARM = {
    "kak***", "leg***", "aki***",
    "mac***", "dut***", "qua[F]***",
}

# W.Rate weights: index 0 = most recent day, index 14 = 15 days ago
WRATE_WEIGHTS = list(range(15, 0, -1))   # [15, 14, 13, ..., 1]
WRATE_DAYS    = len(WRATE_WEIGHTS)       # 15

# ─── Style helpers ─────────────────────────────────────────────────────────────
C_DARK_BLUE = "1F4E79"
C_MED_BLUE  = "2E75B6"
C_LEADER    = "00B050"
C_TEAM      = "EBF3FB"
C_ORANGE    = "FF7700"
C_RED       = "C00000"
C_GRAY_H    = "D9D9D9"
C_WHITE     = "FFFFFF"
C_YELLOW    = "FFFF00"

def _font(bold=False, color="000000", size=9, italic=False):
    return Font(name="Arial", bold=bold, color=color, size=size, italic=italic)

def _fill(color):
    return PatternFill("solid", fgColor=color)

def _center():
    return Alignment(horizontal="center", vertical="center")

def _left():
    return Alignment(horizontal="left", vertical="center")

def _border():
    s = Side(style="thin", color="BBBBBB")
    return Border(left=s, right=s, top=s, bottom=s)

def _set(cell, value, bold=False, color="000000", size=9,
         fill_color=None, align="left", fmt=None, italic=False):
    cell.value = value
    cell.font  = _font(bold=bold, color=color, size=size, italic=italic)
    if fill_color:
        cell.fill = _fill(fill_color)
    cell.alignment = _center() if align == "center" else _left()
    if fmt:
        cell.number_format = fmt
    cell.border = _border()

# ─── New Helpers ─────────────────────────────────────────────────────────────

def normalize_username(username: str) -> str:
    """Strip @gmail.com suffix for consistent storage."""
    if not username: return ""
    return str(username).strip().replace("@gmail.com", "")

def load_team_config(wb) -> dict:
    """
    Returns dict: username_mask -> {"level": "T2", "jade_cap": 30000}
    """
    ws = wb["⚙️ CONFIG"]
    config = {}
    
    # Find TEAM ROSTER header
    start_row = None
    for r in range(1, 100):
        if ws.cell(r, 1).value == "TEAM ROSTER":
            start_row = r + 2 # Skip header row
            break
            
    if not start_row:
        print("[ERROR] Could not find 'TEAM ROSTER' in CONFIG sheet")
        return {}
        
    for row in ws.iter_rows(min_row=start_row, max_row=start_row+50, values_only=True):
        username = normalize_username(row[0])
        if not username: continue
        level    = str(row[1]).strip() if row[1] else "T2"
        jade_cap = float(row[2]) if row[2] else float("inf")
        config[username] = {"level": level, "jade_cap": jade_cap}
        
    return config

def is_team_member(username: str, jade: float, team_config: dict) -> tuple:
    """
    Returns (is_team: bool, level: str)
    """
    if username not in team_config:
        return False, "—"
    
    conf = team_config[username]
    if jade <= conf["jade_cap"]:
        return True, conf["level"]
        
    return False, "—"

# ─── Parsing helpers ───────────────────────────────────────────────────────────

def extract_date_from_filename(filepath: str):
    """
    'bxh-29-04.json' → date(2026, 4, 29)
    Trả về None nếu không match pattern.
    """
    import re
    fname = os.path.basename(filepath)
    m = re.match(r'bxh-(\d{1,2})-(\d{1,2})\.json', fname, re.IGNORECASE)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        try:
            return date(2026, month, day)
        except ValueError:
            return None
    return None

def parse_jade(raw):
    """'800.84K' → 800840 | '1.2M' → 1200000 | '12345' → 12345"""
    if raw is None:
        return None
    s = str(raw).strip().upper().replace(",", "")
    if not s or s == "NAN":
        return None
    try:
        if s.endswith("M"):
            return int(float(s[:-1]) * 1_000_000)
        elif s.endswith("K"):
            return int(float(s[:-1]) * 1_000)
        else:
            return int(float(s))
    except:
        return None

def parse_refs(raw):
    """'46 (19 Tier 1 + 27 Tier 2)' → (19, 27)"""
    if raw is None:
        return 0, 0
    s = str(raw).strip()
    m = re.search(r"\((\d+)\s*Tier\s*1\s*\+\s*(\d+)\s*Tier\s*2\)", s, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.match(r"^(\d+)$", s)
    if m2:
        return int(m2.group(1)), 0
    return 0, 0

def excel_date(d: date) -> int:
    return (d - date(1899, 12, 30)).days

def from_excel_date(serial: int) -> date:
    return date(1899, 12, 30) + timedelta(days=int(serial))

def prize_for_rank(rank: int) -> int:
    for r1, r2, p in PRIZE_TIERS:
        if r1 <= rank <= r2:
            return p
    return 0

def farm_verdict(username: str, t1: int, wrate: float) -> str:
    """Đánh giá farm/real/mix dựa trên heuristics."""
    if username in KNOWN_FARM:
        return "❌ Farm"
    if t1 > 50 and wrate < 5000:
        return "❌ Farm"
    if t1 > 20 and wrate < 2000:
        return "⚠️ Nghi farm"
    if t1 > 10 and wrate > 15000:
        return "✅ Thật"
    if wrate > 20000:
        return "✅ Thật"
    return "—"

# ─── JSON parser (for --json mode) ────────────────────────────────────────────

def parse_json_data(raw_text: str):
    """
    Parse ARO JSON format:
    [{"#":"1","username":"nau***@gmail.com",
      "jades earned from campaign":"800.84K",
      "referral count":"46 (19 Tier 1 + 27 Tier 2)"}...]
    Returns list of (rank, username, jade, t1, t2)
    """
    rows = []
    text = raw_text.strip()

    # Try proper JSON first
    try:
        data = json.loads(text)
        for item in data:
            rank_raw = item.get("#", "") or item.get("rank", "")
            # Skip separator rows
            if str(rank_raw).lower() in ("s", "", "sep"):
                continue
            try:
                rank = int(rank_raw)
            except:
                continue
            username  = normalize_username(item.get("username", ""))
            jade_raw  = item.get("jades earned from campaign",
                        item.get("jade", item.get("jades", "")))
            refs_raw  = item.get("referral count",
                        item.get("refs", item.get("referrals", "")))
            jade = parse_jade(jade_raw)
            t1, t2 = parse_refs(refs_raw)
            if jade is not None and username:
                rows.append((rank, username, jade, t1, t2))
        return rows
    except json.JSONDecodeError:
        pass

    # Fallback: parse line by line
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Try to extract fields with regex
        m = re.search(r'"#"\s*:\s*"(\d+)".*?"username"\s*:\s*"([^"]+)".*?"jades[^"]*"\s*:\s*"([^"]+)".*?"referral[^"]*"\s*:\s*"([^"]+)"', line)
        if m:
            try:
                rank     = int(m.group(1))
                username = normalize_username(m.group(2))
                jade     = parse_jade(m.group(3))
                t1, t2   = parse_refs(m.group(4))
                if jade is not None:
                    rows.append((rank, username, jade, t1, t2))
            except:
                pass
    return rows

# ─── Load HISTORY from Excel ───────────────────────────────────────────────────

def load_history(wb):
    """
    Returns dict: username → list of (date_obj, rank, jade, t1, t2, is_delayed)
    sorted by date ascending.
    """
    ws = wb["🗃️ HISTORY"]
    history = defaultdict(list)

    for row in ws.iter_rows(min_row=3, values_only=True):
        if not row[0]:
            continue
        try:
            d       = from_excel_date(int(row[0]))
            rank    = int(row[1]) if row[1] else 999
            username= normalize_username(row[2])
            jade    = int(row[3]) if row[3] else 0
            t1      = int(row[4]) if row[4] else 0
            t2      = int(row[5]) if row[5] else 0
            delayed = bool(row[6]) if row[6] is not None else False
        except:
            continue
        if username:
            history[username].append((d, rank, jade, t1, t2, delayed))

    # Sort each user's records by date
    for u in history:
        history[u].sort(key=lambda x: x[0])

    return history

# ─── Compute W.Rate ───────────────────────────────────────────────────────────

def compute_wrate(jade_series: list, is_delayed: list = None) -> float:
    """
    jade_series: list of (date, jade) sorted by date ascending.
    is_delayed: list of bools per date (same index).
    Returns weighted average daily jade gain.
    """
    if len(jade_series) < 2:
        return 0.0

    # Compute raw deltas (jade diff / days between)
    deltas = []
    for i in range(1, len(jade_series)):
        d0, j0 = jade_series[i-1]
        d1, j1 = jade_series[i]
        days_gap = max(1, (d1 - d0).days)
        raw_delta = (j1 - j0) / days_gap
        is_del = (is_delayed and is_delayed[i]) or (is_delayed and is_delayed[i-1])
        deltas.append((raw_delta, is_del))

    # Take last WRATE_DAYS deltas
    recent = deltas[-WRATE_DAYS:]

    total_weight = 0.0
    weighted_sum = 0.0
    n = len(recent)

    for i, (delta, delayed) in enumerate(recent):
        # Index 0 = oldest, index n-1 = newest
        pos_from_newest = n - 1 - i  # 0 = newest
        base_weight = WRATE_WEIGHTS[pos_from_newest] if pos_from_newest < len(WRATE_WEIGHTS) else 1
        # Downweight delayed days
        weight = base_weight * (0.3 if delayed else 1.0)
        weighted_sum += delta * weight
        total_weight  += weight

    return round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0

# ─── Compute all user metrics ─────────────────────────────────────────────────

def compute_metrics(history: dict, today: date, team_config: dict):
    """
    Returns dict: username → metrics dict
    """
    days_left = max(0, (EVENT_END - today).days)
    metrics   = {}

    # Mechanism 3: Auto-Alias for new collisions
    COLLISION_THRESHOLD = 0.30 
    
    # We'll create a new dict to store processed metrics to allow renaming
    processed_metrics = {}

    for username, records in history.items():
        if not records:
            continue

        latest  = records[-1]
        d_latest, rank, jade, t1, t2, delayed = latest

        # Mechanism 3 check: If today's jade is way lower than history max
        history_max_jade = max(r[2] for r in records[:-1]) if len(records) > 1 else 0
        display_name = username
        if jade < history_max_jade * (1 - COLLISION_THRESHOLD) and jade > 0:
            print(f"[COLLISION] User {username} jade drop: {history_max_jade:,} -> {jade:,}. Appending [2].")
            display_name = f"{username} [2]"

        # Delta today vs previous day
        delta_today = 0
        delta_prev  = 0
        if len(records) >= 2:
            prev = records[-2]
            gap  = max(1, (d_latest - prev[0]).days)
            delta_today = round((jade - prev[2]) / gap)
        if len(records) >= 3:
            r2 = records[-2]
            r3 = records[-3]
            gap2 = max(1, (r2[0] - r3[0]).days)
            delta_prev = round((r2[2] - r3[2]) / gap2)

        # W.Rate
        jade_series = [(r[0], r[2]) for r in records]
        delayed_flags = [r[5] for r in records]
        wrate = compute_wrate(jade_series, delayed_flags)

        # Projection
        proj = jade + wrate * days_left

        # First/last seen
        first_seen = records[0][0]
        last_seen  = d_latest
        days_active = (last_seen - first_seen).days + 1

        # Team info (Mechanism 2: Jade Cap)
        is_team, team_level = is_team_member(username, jade, team_config)

        # Status (farm analysis)
        status = farm_verdict(username, t1, wrate)

        processed_metrics[display_name] = {
            "original_username": username,
            "rank":         rank,
            "jade":         jade,
            "t1":           t1,
            "t2":           t2,
            "delta_today":  delta_today,
            "delta_prev":   delta_prev,
            "wrate":        wrate,
            "proj":         round(proj),
            "prize":        0,           # filled after rank sort
            "is_team":      is_team,
            "team_level":   team_level,
            "days_active":  days_active,
            "first_seen":   first_seen,
            "last_seen":    last_seen,
            "status":       status,
            "delayed":      delayed,
        }

    # Assign prize based on projected rank
    sorted_by_proj = sorted(processed_metrics.items(), key=lambda x: -x[1]["proj"])
    for i, (name, m) in enumerate(sorted_by_proj):
        proj_rank = i + 1
        processed_metrics[name]["proj_rank"] = proj_rank
        processed_metrics[name]["prize"]     = prize_for_rank(proj_rank)

    return processed_metrics

# ─── Read INPUT sheet ─────────────────────────────────────────────────────────

def read_input_sheet(wb, override_date=None):
    """
    Returns (date_obj, list_of_rows)
    where list_of_rows = [(rank, username, jade, t1, t2), ...]
    """
    ws = wb["📥 INPUT"]

    # Get date
    if override_date:
        today = override_date
    else:
        date_val = ws["C3"].value
        if isinstance(date_val, datetime):
            today = date_val.date()
        elif isinstance(date_val, date):
            today = date_val
        else:
            today = date.today()
            print(f"[WARN] No date in INPUT!C3 — using today: {today}")

    rows = []
    for row_i in range(6, 106):
        rank_val  = ws.cell(row_i, 2).value   # Col B
        user_val  = ws.cell(row_i, 3).value   # Col C
        jade_val  = ws.cell(row_i, 4).value   # Col D
        refs_val  = ws.cell(row_i, 5).value   # Col E

        if not user_val or str(user_val).strip() == "":
            continue

        username = normalize_username(user_val)

        # Rank
        try:
            rank = int(rank_val)
        except:
            rank = len(rows) + 1

        jade = parse_jade(jade_val)
        if jade is None:
            continue

        t1, t2 = parse_refs(refs_val)
        rows.append((rank, username, jade, t1, t2))

    return today, rows

# ─── Append to HISTORY ────────────────────────────────────────────────────────

def append_to_history(wb, today: date, rows: list, is_delayed: bool = False, team_config: dict = {}):
    """
    Appends today's rows to HISTORY sheet.
    Removes existing rows for today first (to allow re-run).
    """
    ws = wb["🗃️ HISTORY"]
    today_serial = excel_date(today)
    today_str    = today.strftime("%Y%m%d")

    # Find last row + remove any existing entries for today
    rows_to_delete = []
    last_row = 2
    for row in ws.iter_rows(min_row=3):
        if row[0].value is None:
            break
        last_row = row[0].row
        if row[0].value == today_serial:
            rows_to_delete.append(row[0].row)

    # Delete existing rows for today (reverse order to preserve indices)
    for r in sorted(rows_to_delete, reverse=True):
        ws.delete_rows(r)
        last_row -= 1

    # Append new rows
    start_row = last_row + 1 if last_row > 2 else 3

    s = Side(style="thin", color="BBBBBB")
    border = Border(left=s, right=s, top=s, bottom=s)

    for rank, username, jade, t1, t2 in rows:
        row_i = start_row
        start_row += 1

        key = f"{today_str}||{username}"
        values = [today_serial, rank, username, jade, t1, t2, is_delayed, key]
        for col_i, val in enumerate(values, start=1):
            c = ws.cell(row_i, col_i)
            c.value = val
            c.font  = Font(name="Arial", size=9)
            c.border = border
            if col_i == 1:
                c.number_format = "dd/mm/yyyy"

        # Highlight special users
        conf = team_config.get(username)
        if conf:
            if conf["level"] == "LEADER":
                for col_i in range(1, 9):
                    ws.cell(row_i, col_i).fill = PatternFill("solid", fgColor="E2EFDA")
            else:
                for col_i in range(1, 9):
                    ws.cell(row_i, col_i).fill = PatternFill("solid", fgColor="EBF3FB")

    print(f"[HISTORY] Appended {len(rows)} rows for {today.strftime('%d/%m/%Y')}")
    return len(rows)

# ─── Update TRACKER sheet ─────────────────────────────────────────────────────

def update_tracker(wb, metrics: dict, today: date, team_config: dict = {}):
    """Rewrites TRACKER sheet with all computed metrics."""
    ws = wb["📊 TRACKER"]

    # Clear data rows (keep header rows 1-2)
    max_row = ws.max_row
    if max_row > 2:
        ws.delete_rows(3, max_row - 2)

    # Sort: team first (leader, T1, T2), then by jade desc
    def sort_key(item):
        u, m = item
        conf = team_config.get(u)
        if conf:
            if conf["level"] == "LEADER": return (0, -m["jade"])
            if conf["level"] == "T1":     return (1, -m["jade"])
            if conf["level"] == "T2":     return (2, -m["jade"])
        return (3, -m["jade"])

    sorted_users = sorted(metrics.items(), key=sort_key)

    s = Side(style="thin", color="BBBBBB")
    border = Border(left=s, right=s, top=s, bottom=s)

    for i, (username, m) in enumerate(sorted_users):
        row = i + 3

        values = [
            username,
            "✅" if m["is_team"] else "",
            m["team_level"],
            m["rank"],
            m["jade"],
            m["t1"],
            m["t2"],
            m["delta_today"],
            m["delta_prev"],
            m["wrate"],
            m["proj"],
            f"${m['prize']:,}" if m["prize"] > 0 else "—",
            m["days_active"],
            m["first_seen"].strftime("%d/%m/%Y") if m["first_seen"] else "",
            m["status"],
        ]

        for col_i, val in enumerate(values, start=1):
            c = ws.cell(row, col_i)
            c.value = val
            c.border = border
            c.font   = Font(name="Arial", size=9)
            c.alignment = Alignment(horizontal="center", vertical="center")

        # Number formats
        ws.cell(row, 5).number_format  = "#,##0"   # Jade
        ws.cell(row, 8).number_format  = "+#,##0;-#,##0;0"  # Delta today
        ws.cell(row, 9).number_format  = "+#,##0;-#,##0;0"  # Delta prev
        ws.cell(row, 10).number_format = "#,##0"   # W.Rate
        ws.cell(row, 11).number_format = "#,##0"   # Proj

        # Row coloring
        conf = team_config.get(username)
        if conf and conf["level"] == "LEADER":
            for c in range(1, 16):
                ws.cell(row, c).fill = PatternFill("solid", fgColor="CCFFCC")
            ws.cell(row, 1).font = Font(name="Arial", bold=True, color=C_LEADER, size=9)
        elif m["is_team"]:
            for c in range(1, 16):
                ws.cell(row, c).fill = PatternFill("solid", fgColor="EBF3FB")
        elif i % 2 == 0:
            for c in range(1, 16):
                ws.cell(row, c).fill = PatternFill("solid", fgColor="F7F7F7")

        # Color delta: green if positive, red if negative
        delta_cell = ws.cell(row, 8)
        if isinstance(m["delta_today"], (int, float)):
            if m["delta_today"] > 0:
                delta_cell.font = Font(name="Arial", size=9, color="00B050")
            elif m["delta_today"] < 0:
                delta_cell.font = Font(name="Arial", size=9, color=C_RED)

    print(f"[TRACKER] Updated {len(sorted_users)} users")

# ─── Update DASHBOARD sheet ───────────────────────────────────────────────────

def update_dashboard(wb, metrics: dict, today: date, team_config: dict = {}):
    """Fills the DASHBOARD sheet with structured report data."""
    ws = wb["🏆 DASHBOARD"]

    # Safety: Unmerge existing ranges to avoid "MergedCell is read-only" error
    merged_ranges = list(ws.merged_cells.ranges)
    for mr in merged_ranges:
        if mr.min_row >= 4:
            ws.unmerge_cells(str(mr))

    days_left = max(0, (EVENT_END - today).days)
    date_str  = today.strftime("%d/%m/%Y")

    # Sort all users by latest jade
    by_jade = sorted(metrics.items(), key=lambda x: -x[1]["jade"])
    # Sort by projected jade for rank
    by_proj = sorted(metrics.items(), key=lambda x: -x[1]["proj"])

    def get_jade_rank(username):
        for i, (u, _) in enumerate(by_jade):
            if u == username:
                return i + 1
        return 999

    # ── Update title with date ────────────────────────────────────────────────
    ws.merge_cells("A1:J1")
    ws["A1"] = f"🏆 ARO Sprint 2 — DASHBOARD  |  Cập nhật: {date_str}  |  Còn {days_left} ngày"
    ws["A1"].font = Font(name="Arial", bold=True, color=C_WHITE, size=12)
    ws["A1"].fill = PatternFill("solid", fgColor=C_DARK_BLUE)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    # ── Section 1: Leader stats ───────────────────────────────────────────────
    leader_user = next((u for u, c in team_config.items() if c["level"] == "LEADER"), "nau***")
    lm = metrics.get(leader_user, {})
    lrank = get_jade_rank(leader_user)

    # Gap vs #2 and #3
    gap2 = gap3 = "—"
    if len(by_jade) >= 2:
        gap2 = f"+{lm.get('jade', 0) - by_jade[1][1]['jade']:,}"
    if len(by_jade) >= 3:
        gap3 = f"+{lm.get('jade', 0) - by_jade[2][1]['jade']:,}"

    stats = [
        (4,  "Rank",              f"#{lrank}",                         "center", True,  C_LEADER),
        (5,  "Jade",              f"{lm.get('jade', 0):,}",            "center", True,  "000000"),
        (6,  "T1 Refs",           lm.get("t1", 0),                     "center", False, "000000"),
        (7,  "T2 Refs",           lm.get("t2", 0),                     "center", False, "000000"),
        (8,  "Δ Hôm nay",         f"+{lm.get('delta_today', 0):,}" if lm.get('delta_today', 0) >= 0 else f"{lm.get('delta_today', 0):,}",
                                                                        "center", False, C_LEADER if lm.get("delta_today", 0) >= 0 else C_RED),
        (9,  "W.Rate (/ngày)",    f"{lm.get('wrate', 0):,.0f}",        "center", False, "000000"),
        (10, "Dự báo 31/05",      f"{lm.get('proj', 0):,}",            "center", True,  "000000"),
        (11, "Prize dự kiến",     f"${lm.get('prize', 0):,}",          "center", True,  C_LEADER),
        (12, "Gap vs #2",         gap2,                                 "center", False, "000000"),
        (13, "Gap vs #3",         gap3,                                 "center", False, "000000"),
        (14, "Ngày cập nhật",     date_str,                             "center", False, "444444"),
    ]

    for row, label, val, align, bold, color in stats:
        ws[f"A{row}"].value = label
        ws[f"A{row}"].font  = Font(name="Arial", bold=True, size=9)
        ws[f"A{row}"].border = _border()
        ws.merge_cells(f"B{row}:J{row}")
        ws[f"B{row}"].value = val
        ws[f"B{row}"].font  = Font(name="Arial", bold=bold, size=10, color=color)
        ws[f"B{row}"].alignment = Alignment(horizontal=align, vertical="center")
        ws[f"B{row}"].border = _border()

    # ── Section 2: Top 10 ─────────────────────────────────────────────────────
    # (rows 18-27, after section title at 16, headers at 17)
    for i, (username, m) in enumerate(by_jade[:10]):
        row   = 18 + i
        urank = i + 1
        note  = ""
        conf = team_config.get(username)
        if conf:
            if conf["level"] == "LEADER":
                note = "⭐ LEADER"
            else:
                note = f"👥 Team ({conf['level']})"
        elif username in KNOWN_FARM:
            note = "❌ Farm"

        vals = [urank, username, f"{m['jade']:,}",
                f"+{m['delta_today']:,}" if m["delta_today"] >= 0 else f"{m['delta_today']:,}",
                f"+{m['delta_prev']:,}"  if m["delta_prev"]  >= 0 else f"{m['delta_prev']:,}",
                f"{m['wrate']:,.0f}", f"{m['proj']:,}",
                f"${m['prize']:,}" if m["prize"] > 0 else "—",
                m["t1"], m["t2"], note]

        for col_i, val in enumerate(vals, start=1):
            c = ws.cell(row, col_i)
            c.value = val
            c.font  = Font(name="Arial", size=9, bold=(conf and conf["level"] == "LEADER"))
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _border()

        # Highlight row
        if conf and conf["level"] == "LEADER":
            for col_i in range(1, 12):
                ws.cell(row, col_i).fill = PatternFill("solid", fgColor="CCFFCC")
        elif m["is_team"]:
            for col_i in range(1, 12):
                ws.cell(row, col_i).fill = PatternFill("solid", fgColor="EBF3FB")
        elif i % 2 == 0:
            for col_i in range(1, 12):
                ws.cell(row, col_i).fill = PatternFill("solid", fgColor="F7F7F7")

    # ── Section 3: Top 10 T1 refs ─────────────────────────────────────────────
    top_t1 = sorted(metrics.items(), key=lambda x: -x[1]["t1"])[:10]
    for i, (username, m) in enumerate(top_t1):
        row = 32 + i
        verdict = farm_verdict(username, m["t1"], m["wrate"])
        vals = [i+1, username, m["t1"], m["t2"],
                f"{m['jade']:,}", f"{m['delta_today']:,}",
                f"{m['wrate']:,.0f}", verdict]
        for col_i, val in enumerate(vals, start=1):
            c = ws.cell(row, col_i)
            c.value = val
            c.font  = Font(name="Arial", size=9)
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _border()
        if i % 2 == 0:
            for col_i in range(1, 9):
                ws.cell(row, col_i).fill = PatternFill("solid", fgColor="F7F7F7")

    # ── Section 4: Team status ────────────────────────────────────────────────
    team_order = sorted(team_config.keys(), key=lambda x: (0 if team_config[x]["level"]=="LEADER" else 1 if team_config[x]["level"]=="T1" else 2, x))
    row = 46
    for username in team_order:
        # Check both display name and original username
        m = metrics.get(username)
        if not m:
            # Maybe it was aliased to "[2]"
            m = metrics.get(f"{username} [2]")
            
        if not m:
            # Not yet on BXH
            vals = [username, team_config[username]["level"],
                    "—", "—", "—", "—", "—", "—", "⚠️ Chưa có BXH"]
            for col_i, val in enumerate(vals, start=1):
                c = ws.cell(row, col_i)
                c.value = val
                c.font  = Font(name="Arial", size=9, italic=True, color="888888")
                c.border = _border()
        else:
            urank = get_jade_rank(username if username in metrics else f"{username} [2]")
            note = ""
            conf = team_config.get(username)
            if m["wrate"] < 1000 and m.get("days_active", 0) > 3:
                note = "⚠️ Rate thấp"
            elif m["delta_today"] == 0:
                note = "⚠️ Không tăng hôm nay"

            vals = [username if username in metrics else f"{username} [2]", 
                    conf["level"] if conf else m["team_level"],
                    f"#{urank}", f"{m['jade']:,}",
                    f"+{m['delta_today']:,}" if m["delta_today"] >= 0 else f"{m['delta_today']:,}",
                    f"{m['wrate']:,.0f}", f"{m['proj']:,}",
                    f"${m['prize']:,}" if m["prize"] > 0 else "—", note]

            for col_i, val in enumerate(vals, start=1):
                c = ws.cell(row, col_i)
                c.value = val
                c.font  = Font(name="Arial", size=9,
                                bold=(conf and conf["level"] == "LEADER"),
                                color=C_LEADER if (conf and conf["level"] == "LEADER") else "000000")
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.border = _border()

            if conf and conf["level"] == "LEADER":
                for col_i in range(1, 10):
                    ws.cell(row, col_i).fill = PatternFill("solid", fgColor="CCFFCC")
            elif row % 2 == 0:
                for col_i in range(1, 10):
                    ws.cell(row, col_i).fill = PatternFill("solid", fgColor="F0F7FF")
                c.border = _border()

            if conf and conf["level"] == "LEADER":
                for col_i in range(1, 10):
                    ws.cell(row, col_i).fill = PatternFill("solid", fgColor="CCFFCC")
            elif row % 2 == 0:
                for col_i in range(1, 10):
                    ws.cell(row, col_i).fill = PatternFill("solid", fgColor="F0F7FF")

        row += 1

    # ── Section 5: Thresholds ─────────────────────────────────────────────────
    jades_sorted = sorted([m["jade"] for m in metrics.values()], reverse=True)
    jade_50  = jades_sorted[49]  if len(jades_sorted) >= 50  else "—"
    jade_100 = jades_sorted[99]  if len(jades_sorted) >= 100 else "—"

    for i, (label, jade_val) in enumerate([("#50", jade_50), ("#100", jade_100)]):
        row = 64 + i
        ws.cell(row, 1).value = label
        ws.cell(row, 1).font  = Font(name="Arial", bold=True, size=9)
        ws.cell(row, 2).value = f"{jade_val:,}" if isinstance(jade_val, int) else jade_val
        ws.cell(row, 2).font  = Font(name="Arial", size=9)
        for col_i in range(1, 6):
            ws.cell(row, col_i).border = _border()

    # ── Section 6: Alerts ────────────────────────────────────────────────────
    alerts = []
    leader_user = next((u for u, c in team_config.items() if c["level"] == "LEADER"), "nau***")
    lm = metrics.get(leader_user, {})

    # Alert 1: Rate drop
    if lm.get("wrate", 0) > 0 and lm.get("delta_today", 0) > 0:
        ratio = lm["delta_today"] / lm["wrate"]
        if ratio < 0.7:
            alerts.append(("🔴", f"Rate {leader_user} hôm nay ({lm['delta_today']:,}) thấp hơn W.Rate {lm['wrate']:,.0f} ({ratio:.0%})"))
        else:
            alerts.append(("✅", f"Rate {leader_user} bình thường: {lm['delta_today']:,} vs W.Rate {lm['wrate']:,.0f}"))

    # Alert 2: Gap with #2
    if len(by_jade) >= 2:
        gap_abs = lm.get("jade", 0) - by_jade[1][1]["jade"]
        u2      = by_jade[1][0]
        u2_rate = by_jade[1][1].get("wrate", 0)
        days_to_overtake = "∞"
        if u2_rate > lm.get("wrate", 0):
            rate_diff = u2_rate - lm.get("wrate", 0)
            if rate_diff > 0:
                days_to_overtake = round(gap_abs / rate_diff)
        if gap_abs < 100_000:
            alerts.append(("🟡", f"Gap vs #{u2}: +{gap_abs:,} jade — NGUY HIỂM! {u2} đang đuổi gần"))
        else:
            alerts.append(("✅", f"Gap vs #2 ({u2}): +{gap_abs:,} jade — Ổn định"))

    # Alert 3: Team member issues
    for tm, tconf in team_config.items():
        if tconf["level"] == "LEADER": continue
        if tm in metrics:
            tm_delta = metrics[tm].get("delta_today", 0)
            if tm_delta == 0:
                alerts.append(("⚠️", f"Team {tm}: delta = 0 hôm nay — kiểm tra node"))

    # Alert 4: New high-ref user
    for username, m in by_jade[:30]:
        if m["t1"] > 100 and username not in KNOWN_FARM and username != leader_user:
            if m["wrate"] < 5000:
                alerts.append(("ℹ️", f"Farm mới: {username} có {m['t1']} T1 refs nhưng W.Rate chỉ {m['wrate']:,.0f}"))

    # Write alerts
    row = 72
    for status, detail in alerts[:8]:
        ws.cell(row, 1).value = status
        ws.cell(row, 1).font  = Font(name="Arial", bold=True, size=10)
        ws.cell(row, 1).border = _border()
        ws.cell(row, 1).alignment = Alignment(horizontal="center", vertical="center")
        ws.merge_cells(f"B{row}:J{row}")
        ws.cell(row, 2).value = detail
        ws.cell(row, 2).font  = Font(name="Arial", size=9)
        ws.cell(row, 2).border = _border()
        row += 1

    print(f"[DASHBOARD] Updated for {date_str} ({len(alerts)} alerts)")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ARO Sprint 2 Daily Update")
    parser.add_argument("--date",       help="Override date (YYYY-MM-DD)")
    parser.add_argument("--json",       help="Path to JSON file with BXH data")
    parser.add_argument("--auto",       action="store_true",
                        help="Tự tìm file bxh-*.json mới nhất trong BASE_DIR")
    parser.add_argument("--skip-input", action="store_true",
                        help="Skip reading INPUT sheet, just recompute from HISTORY")
    parser.add_argument("--delayed",    action="store_true",
                        help="Mark today as delayed (downweight in W.Rate)")
    args = parser.parse_args()

    # Auto-find latest json
    if args.auto and not args.json:
        import glob
        pattern = os.path.join(BASE_DIR, "bxh-*.json")
        candidates = glob.glob(pattern)
        if not candidates:
            print("[ERROR] Không tìm thấy file bxh-*.json trong thư mục")
            sys.exit(1)
        # Sort by extracted date, lấy mới nhất
        def sort_key(f):
            d = extract_date_from_filename(f)
            return d if d else date(2000, 1, 1)
        args.json = max(candidates, key=sort_key)
        print(f"[AUTO] Dùng file: {os.path.basename(args.json)}")

    # Parse date
    if args.date:
        try:
            today = datetime.strptime(args.date, "%Y-%m-%d").date()
        except:
            print(f"[ERROR] Invalid date format: {args.date} (use YYYY-MM-DD)")
            sys.exit(1)
    else:
        today = date.today()

    # Auto-detect date from JSON filename (nếu chưa có --date)
    if args.json and not args.date:
        detected = extract_date_from_filename(args.json)
        if detected:
            today = detected
            print(f"[INFO] Ngày tự suy từ tên file: {today.strftime('%d/%m/%Y')}")

    print("=" * 60)
    print(f"ARO Sprint 2 — Daily Update  [{today.strftime('%d/%m/%Y')}]")
    print("=" * 60)

    # Load workbook
    if not os.path.exists(MASTER_FILE):
        print(f"[ERROR] {MASTER_FILE} not found!")
        print("        Run ARO_create_master.py first.")
        sys.exit(1)

    print(f"\n[1/4] Loading {os.path.basename(MASTER_FILE)}...")
    wb = load_workbook(MASTER_FILE)
    team_config = load_team_config(wb)
    print(f"      → Loaded config for {len(team_config)} team members")

    # Read input data
    new_rows = []
    if not args.skip_input:
        if args.json:
            # Read from JSON file
            print(f"[2/4] Reading JSON: {args.json}...")
            try:
                with open(args.json, "r", encoding="utf-8") as f:
                    content = f.read()
                new_rows = parse_json_data(content)
                print(f"      → Parsed {len(new_rows)} rows")
            except Exception as e:
                print(f"[ERROR] Cannot read JSON: {e}")
                sys.exit(1)
        else:
            # Read from INPUT sheet
            print("[2/4] Reading INPUT sheet...")
            try:
                today_input, new_rows = read_input_sheet(wb, today if args.date else None)
                today = today_input
                print(f"      → Date: {today.strftime('%d/%m/%Y')}, Rows: {len(new_rows)}")
            except Exception as e:
                print(f"[ERROR] Cannot read INPUT sheet: {e}")
                sys.exit(1)

        if new_rows:
            print(f"[3/4] Appending {len(new_rows)} rows to HISTORY...")
            append_to_history(wb, today, new_rows, is_delayed=args.delayed, team_config=team_config)
        else:
            print("[WARN] No data rows found in INPUT — skipping HISTORY update")
    else:
        print("[2/4] Skipping INPUT (--skip-input mode)")
        print("[3/4] Skipping HISTORY append")

    # Compute metrics from HISTORY
    print("[4/4] Computing metrics...")
    history = load_history(wb)
    print(f"      → {len(history)} users in HISTORY")

    if not history:
        print("[WARN] HISTORY is empty — nothing to compute")
        wb.save(MASTER_FILE)
        return

    metrics = compute_metrics(history, today, team_config)
    print(f"      → Metrics computed for {len(metrics)} users")

    # Update sheets
    update_tracker(wb, metrics, today, team_config)
    update_dashboard(wb, metrics, today, team_config)

    # Save
    wb.save(MASTER_FILE)
    print(f"\n✅ Saved: {MASTER_FILE}")

    # Print quick summary to console
    leader_user = next((u for u, c in team_config.items() if c["level"] == "LEADER"), "nau***")
    lm = metrics.get(leader_user, {})
    by_jade = sorted(metrics.items(), key=lambda x: -x[1]["jade"])
    lrank   = next((i+1 for i, (u,_) in enumerate(by_jade) if u == leader_user), "?")

    print("\n" + "─" * 50)
    print(f"{leader_user} → #{lrank}  |  {lm.get('jade',0):,} jade  |  Δ +{lm.get('delta_today',0):,}  |  W.Rate {lm.get('wrate',0):,.0f}/ngày")
    if len(by_jade) >= 2:
        gap = lm.get("jade", 0) - by_jade[1][1]["jade"]
        print(f"Gap vs #2 ({by_jade[1][0]}): +{gap:,}")
    days_left = (EVENT_END - today).days
    print(f"Proj 31/05: {lm.get('proj',0):,}  |  Prize: ${lm.get('prize',0):,}  |  {days_left} ngày còn lại")
    print("─" * 50)
    print("\n→ DASHBOARD đã được cập nhật. Claude có thể đọc file và viết báo cáo.")


if __name__ == "__main__":
    main()
