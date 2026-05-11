#!/usr/bin/env python3
"""
ARO Sprint 2 — Master Excel Builder (ARO_create_master.py)
=========================================================
Chạy 1 lần duy nhất để tạo ARO_MASTER.xlsx từ file v24 hiện tại.
Sau đó dùng ARO_update.py mỗi ngày.

Usage:
    python ARO_create_master.py
"""

import os, re
from datetime import date, timedelta
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR     = r"C:\Users\Administrator\OneDrive\Documents\ARO S2 top 100 tracking"
EXISTING_V24 = os.path.join(BASE_DIR, "ARO_Sprint2_v24_28Apr.xlsx")
MASTER_FILE  = os.path.join(BASE_DIR, "ARO_MASTER.xlsx")

# ─── Event constants ──────────────────────────────────────────────────────────
EVENT_START  = date(2026, 3, 30)
EVENT_END    = date(2026, 5, 31)
LEADER       = "nau***@gmail.com"

TEAM_T1 = ["dan***@gmail.com"]
TEAM_T2 = [
    "qua[T]***@gmail.com", "inf***@gmail.com", "caf***@gmail.com",
    "kdl***@gmail.com",    "nha***@gmail.com", "dic***@gmail.com",
    "xzo***@gmail.com",    "hun[mới]***@gmail.com",
    "qua[mới]***@gmail.com","cha***@gmail.com",
]
TEAM_ALL = [LEADER] + TEAM_T1 + TEAM_T2

KNOWN_FARM = [
    "kak***@gmail.com", "leg***@gmail.com", "aki***@gmail.com",
    "mac***@gmail.com", "dut***@gmail.com", "qua[F]***@gmail.com",
]

# Duplicate-name aliases (username_prefix → canonical alias)
ALIAS_MAP = {
    # These are set by comparing jade levels - update as needed
    # "qua***": resolved to qua[T]*** (team, ~31K) or qua[F]*** (farm, ~14K)
    # "hun***": resolved to hun[mới]*** (team, low jade) or hun*** (not team, ~66K)
}

PRIZE_TIERS = [(1,1,5000),(2,5,2000),(6,10,1000),(11,50,200),(51,100,50)]

# ─── Colors ───────────────────────────────────────────────────────────────────
C_DARK_BLUE  = "1F4E79"
C_MED_BLUE   = "2E75B6"
C_LITE_BLUE  = "BDD7EE"
C_LEADER     = "00B050"
C_TEAM       = "E2EFDA"
C_ORANGE     = "FF7700"
C_YELLOW     = "FFFF00"
C_GRAY_H     = "D9D9D9"
C_WHITE      = "FFFFFF"
C_RED        = "FF0000"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def prize_for_rank(rank):
    for r1, r2, p in PRIZE_TIERS:
        if r1 <= rank <= r2:
            return p
    return 0

def parse_jade(raw):
    """'800.84K' → 800840, '1.2M' → 1200000, '12345' → 12345"""
    if raw is None or str(raw).strip() == "":
        return None
    s = str(raw).strip().upper().replace(",", "")
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
    if raw is None or str(raw).strip() == "":
        return 0, 0
    s = str(raw)
    m = re.search(r"\((\d+)\s*Tier 1\s*\+\s*(\d+)\s*Tier 2\)", s, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Fallback: just a number = total refs
    m2 = re.match(r"(\d+)", s.strip())
    if m2:
        return int(m2.group(1)), 0
    return 0, 0

def excel_date(d: date) -> int:
    """Python date → Excel serial number"""
    return (d - date(1899, 12, 30)).days

def hdr_font(color=C_WHITE, bold=True, size=10):
    return Font(name="Arial", bold=bold, color=color, size=size)

def fill(color):
    return PatternFill("solid", fgColor=color)

def center():
    return Alignment(horizontal="center", vertical="center", wrap_text=True)

def left():
    return Alignment(horizontal="left", vertical="center", wrap_text=False)

def thin_border():
    s = Side(style="thin", color="AAAAAA")
    return Border(left=s, right=s, top=s, bottom=s)

def set_col_width(ws, col_letter, width):
    ws.column_dimensions[col_letter].width = width

# ─── Extract HISTORY from existing v24 ────────────────────────────────────────

def extract_history_from_v24(filepath):
    """
    Reads ARO_Sprint2_v24_28Apr.xlsx and returns a list of dicts:
    [{date, rank, username, jade, t1, t2, is_delayed, key}, ...]

    The v24 file has 2 sheets. This function tries to parse the Master Tracker.
    Returns empty list if file not found or parse fails.
    """
    records = []
    if not os.path.exists(filepath):
        print(f"[WARN] {filepath} not found — starting with empty HISTORY")
        return records

    try:
        print(f"[INFO] Reading {filepath}...")
        xl = pd.ExcelFile(filepath)
        print(f"[INFO] Sheets: {xl.sheet_names}")

        # Try to find the main tracker sheet
        tracker_sheet = None
        for s in xl.sheet_names:
            if "master" in s.lower() or "tracker" in s.lower():
                tracker_sheet = s
                break
        if tracker_sheet is None:
            tracker_sheet = xl.sheet_names[0]

        # Read raw (no header inference)
        raw = pd.read_excel(filepath, sheet_name=tracker_sheet, header=None)
        print(f"[INFO] Sheet '{tracker_sheet}' shape: {raw.shape}")

        # --- Detect structure ---
        # Strategy: look for username column (contains "@" or known pattern)
        # and date-like column headers

        username_col = None
        date_cols = {}  # col_idx → date

        # Scan rows 0 to 4 for dates, col 0/1/2 for usernames
        for scan_row in range(min(5, raw.shape[0])):
            for col_i in range(raw.shape[1]):
                val = raw.iloc[scan_row, col_i]
        
                # Case 1: pandas datetime object
                if hasattr(val, 'date') and callable(val.date):
                    d = val.date()
                    if EVENT_START <= d <= EVENT_END:
                        date_cols[col_i] = d
        
                # Case 2: Excel serial number (float/int in range ~45000-47000)
                elif isinstance(val, (int, float)) and 45000 <= val <= 47000:
                    try:
                        d = date(1899, 12, 30) + timedelta(days=int(val))
                        if EVENT_START <= d <= EVENT_END:
                            date_cols[col_i] = d
                    except:
                        pass
        
                # Case 3: string date "10/4", "10-04", "10/04/2026", "25-04*"
                elif isinstance(val, str):
                    s_val = val.strip().replace("*", "")
                    if re.match(r'^\d{1,2}[/-]\d{1,2}', s_val):
                        try:
                            s_val = s_val.replace("-", "/")
                            if len(s_val) <= 5:
                                s_val += "/2026"
                            d = pd.to_datetime(s_val, dayfirst=True).date()
                            if EVENT_START <= d <= EVENT_END:
                                date_cols[col_i] = d
                        except:
                            pass

            if date_cols:
                break  # Dừng khi tìm thấy ngày

        # Find username column by scanning first 5 columns for email-like data
        for col_i in range(min(5, raw.shape[1])):
            col_vals = raw.iloc[1:, col_i].astype(str)
            if col_vals.str.contains(r'\*{2,}|@', regex=True).mean() > 0.3:
                username_col = col_i
                break

        print("DEBUG RAW DATA:")
        print(raw.iloc[:3, :10])
        print(f"[INFO] Username col: {username_col}, Date cols: {list(date_cols.items())[:5]}...")

        if username_col is None or not date_cols:
            print("[WARN] Cannot detect structure in v24 — trying alternate parse...")
            # Alternate: assume rows=users, and search for date-like values
            # in row 1 or column headers
            # This is a best-effort fallback
            return records

        # --- For each date column, extract jade data ---
        # Look for rank and T1/T2 columns adjacent to each date column
        for date_col_i, dt in date_cols.items():
            if dt < EVENT_START or dt > EVENT_END:
                continue

            # Get jade column (could be same col or adjacent)
            jade_col_i = date_col_i  # often jade is in the date column itself

            # Look for rank in adjacent columns
            rank_col_i = None
            for offset in [-3, -2, -1, 1, 2, 3]:
                c = date_col_i + offset
                if 0 <= c < raw.shape[1]:
                    col_data = raw.iloc[1:6, c].astype(str)
                    # Rank: small numbers 1-10
                    if col_data.str.match(r'^\d{1,3}$').mean() > 0.5:
                        first_vals = pd.to_numeric(raw.iloc[1:6, c], errors='coerce')
                        if first_vals.between(1, 200).mean() > 0.5:
                            rank_col_i = c
                            break

            # Extract rows
            for row_i in range(1, raw.shape[0]):
                username = str(raw.iloc[row_i, username_col]).strip()
                if not username or username == 'nan' or username == '':
                    continue
                if username.lower() in ('username', 'user', 'email', 'nan'):
                    continue

                jade_raw = raw.iloc[row_i, jade_col_i]
                jade = parse_jade(jade_raw)
                if jade is None:
                    continue

                rank = None
                if rank_col_i is not None:
                    try:
                        rank = int(raw.iloc[row_i, rank_col_i])
                    except:
                        pass
                if rank is None:
                    rank = row_i  # fallback

                # T1/T2: look for columns after jade col
                t1, t2 = 0, 0
                for offset in [1, 2, 3]:
                    c = date_col_i + offset
                    if c < raw.shape[1]:
                        val = raw.iloc[row_i, c]
                        if isinstance(val, (int, float)) and 0 <= val < 1000:
                            if t1 == 0:
                                t1 = int(val)
                            elif t2 == 0:
                                t2 = int(val)
                                break

                key = f"{dt.strftime('%Y%m%d')}||{username}"
                records.append({
                    "date": dt,
                    "rank": rank,
                    "username": username,
                    "jade": jade,
                    "t1": t1,
                    "t2": t2,
                    "is_delayed": False,
                    "key": key,
                })

        # Remove duplicates (same key)
        seen = set()
        unique = []
        for r in records:
            if r["key"] not in seen:
                seen.add(r["key"])
                unique.append(r)
        records = unique
        print(f"[INFO] Extracted {len(records)} records from v24")

    except Exception as e:
        print(f"[ERROR] Failed to parse v24: {e}")
        print("[WARN] Starting with empty HISTORY")
        records = []

    return records

# ─── Sheet builders ────────────────────────────────────────────────────────────

def build_config_sheet(wb):
    ws = wb.create_sheet("⚙️ CONFIG")
    ws.tab_color = "808080"

    # Title
    ws.merge_cells("A1:E1")
    ws["A1"] = "⚙️ ARO Sprint 2 — CONFIG (Đừng sửa trực tiếp)"
    ws["A1"].font = hdr_font(size=12)
    ws["A1"].fill = fill(C_DARK_BLUE)
    ws["A1"].alignment = center()
    ws.row_dimensions[1].height = 22

    # Event settings
    ws["A3"] = "EVENT SETTINGS"
    ws["A3"].font = Font(name="Arial", bold=True, size=10)

    settings = [
        ("A4", "Event Start",     "B4", date(2026,3,30), "dd/mm/yyyy"),
        ("A5", "Event End",       "B5", date(2026,5,31), "dd/mm/yyyy"),
        ("A6", "Leader Account",  "B6", LEADER,          None),
        ("A7", "Today",           "B7", "=TODAY()",      "dd/mm/yyyy"),
        ("A8", "Days Remaining",  "B8", '=B5-TODAY()',   '0" ngày"'),
    ]
    for label_cell, label, val_cell, val, fmt in settings:
        ws[label_cell] = label
        ws[label_cell].font = Font(name="Arial", size=9)
        ws[val_cell] = val
        ws[val_cell].font = Font(name="Arial", bold=True, size=9)
        if fmt:
            ws[val_cell].number_format = fmt

    ws["B5"].font = Font(name="Arial", bold=True, color=C_RED, size=9)
    ws["B6"].font = Font(name="Arial", bold=True, color=C_LEADER, size=9)

    # W.Rate weights (row 10-11)
    ws["A10"] = "W.RATE WEIGHTS (newest → oldest):"
    ws["A10"].font = Font(name="Arial", bold=True, size=9)
    weights = list(range(15, 0, -1))  # [15, 14, ..., 1]
    for i, w in enumerate(weights):
        cell = ws.cell(row=11, column=i+2)
        cell.value = w
        cell.font = Font(name="Arial", size=9)
        cell.alignment = center()
    ws["A11"] = "Weights:"
    ws["A11"].font = Font(name="Arial", size=9)

    # Prize tiers (row 13+)
    ws["A13"] = "PRIZE TIERS"
    ws["A13"].font = Font(name="Arial", bold=True, size=9)
    # Header row
    ws.cell(14,1).value = "Rank Min"
    ws.cell(14,2).value = "Rank Max"
    ws.cell(14,3).value = "Prize ($)"
    for c in [1,2,3]:
        ws.cell(14,c).font = Font(name="Arial", bold=True, size=9)
        ws.cell(14,c).fill = fill(C_GRAY_H)

    for i, (r1, r2, prize) in enumerate(PRIZE_TIERS):
        row = 15 + i
        ws.cell(row,1).value = r1
        ws.cell(row,2).value = r2
        ws.cell(row,3).value = prize
        for c in [1,2,3]:
            ws.cell(row,c).font = Font(name="Arial", size=9)

    # Team roster (row 22+)
    ws["A22"] = "TEAM ROSTER"
    ws["A22"].font = Font(name="Arial", bold=True, size=9)
    ws.cell(23,1).value = "Username"
    ws.cell(23,2).value = "Level"
    ws.cell(23,3).value = "Ghi chú"
    for c in [1,2,3]:
        ws.cell(23,c).font = Font(name="Arial", bold=True, size=9)
        ws.cell(23,c).fill = fill(C_GRAY_H)

    team_rows = [(LEADER,"LEADER","Account chính")] + \
                [(u,"T1","") for u in TEAM_T1] + \
                [(u,"T2","") for u in TEAM_T2]
    for i, (user, level, note) in enumerate(team_rows):
        row = 24 + i
        ws.cell(row,1).value = user
        ws.cell(row,2).value = level
        ws.cell(row,3).value = note
        for c in [1,2,3]:
            ws.cell(row,c).font = Font(name="Arial", size=9)
        if level == "LEADER":
            ws.cell(row,1).font = Font(name="Arial", bold=True, color=C_LEADER, size=9)

    # Known farm list (row 40+)
    ws["A40"] = "KNOWN FARM / BOT ACCOUNTS"
    ws["A40"].font = Font(name="Arial", bold=True, size=9, color=C_RED)
    for i, u in enumerate(KNOWN_FARM):
        ws.cell(41+i, 1).value = u
        ws.cell(41+i, 1).font = Font(name="Arial", size=9, color=C_RED)

    # Column widths
    set_col_width(ws, "A", 32)
    set_col_width(ws, "B", 28)
    set_col_width(ws, "C", 30)
    for i in range(16):
        set_col_width(ws, get_column_letter(i+4), 6)

    return ws


def build_input_sheet(wb):
    ws = wb.create_sheet("📥 INPUT")
    ws.tab_color = "00B050"

    # Title
    ws.merge_cells("A1:G1")
    ws["A1"] = "📥 INPUT — Dán Data BXH Hàng Ngày"
    ws["A1"].font = hdr_font(size=13)
    ws["A1"].fill = fill(C_LEADER)
    ws["A1"].alignment = center()
    ws.row_dimensions[1].height = 26

    # Instructions
    ws.merge_cells("A2:G2")
    ws["A2"] = ("Hướng dẫn: (1) Nhập ngày vào C3  (2) Copy 4 cột từ BXH ARO dán vào B6:E105  "
                "(3) Lưu file  (4) Nói với Claude: 'Cập nhật và viết báo cáo'")
    ws["A2"].font = Font(name="Arial", size=9, italic=True, color="444444")
    ws["A2"].alignment = left()

    # Date input
    ws["A3"] = "📅 Ngày hôm nay:"
    ws["A3"].font = Font(name="Arial", bold=True, size=10)
    ws["C3"] = date.today()
    ws["C3"].number_format = "dd/mm/yyyy"
    ws["C3"].font = Font(name="Arial", bold=True, size=11, color=C_DARK_BLUE)
    ws["C3"].fill = fill(C_YELLOW)
    ws["C3"].alignment = center()
    ws["C3"].border = thin_border()

    # Column headers row 5
    headers = ["", "# Rank", "Username", "Jade (ví dụ: 800.84K)", "Refs (ví dụ: 46 (19 Tier 1 + 27 Tier 2))"]
    for i, h in enumerate(headers):
        cell = ws.cell(5, i+1)
        cell.value = h
        cell.font = hdr_font()
        cell.fill = fill(C_MED_BLUE)
        cell.alignment = center()
        cell.border = thin_border()
    ws.row_dimensions[5].height = 20

    # Paste area (rows 6-105)
    for row in range(6, 106):
        for col in range(2, 6):  # B to E
            cell = ws.cell(row, col)
            cell.border = thin_border()
            if col == 2:  # Rank
                cell.alignment = center()
            else:
                cell.alignment = left()

        # Row number label in col A
        ws.cell(row, 1).value = row - 5
        ws.cell(row, 1).font = Font(name="Arial", size=8, color="888888")
        ws.cell(row, 1).alignment = center()

    # Alternate row colors for paste area
    for row in range(6, 106, 2):
        for col in range(1, 6):
            ws.cell(row, col).fill = fill("F5F9FF")

    # Column widths
    set_col_width(ws, "A", 5)
    set_col_width(ws, "B", 8)
    set_col_width(ws, "C", 32)
    set_col_width(ws, "D", 18)
    set_col_width(ws, "E", 38)

    # Note
    ws["A107"] = "⚠️ SAU KHI DÁN: Lưu file → Nói với Claude 'Cập nhật ngày [date] và viết báo cáo'"
    ws["A107"].font = Font(name="Arial", bold=True, size=9, color=C_ORANGE)
    ws.merge_cells("A107:G107")

    ws["A109"] = "Sau khi Claude chạy update, dữ liệu tự động xuất hiện trong sheet TRACKER và DASHBOARD."
    ws["A109"].font = Font(name="Arial", size=9, italic=True, color="555555")
    ws.merge_cells("A109:G109")

    return ws


def build_history_sheet(wb, records):
    ws = wb.create_sheet("🗃️ HISTORY")
    ws.tab_color = "808080"

    # Title
    ws.merge_cells("A1:H1")
    ws["A1"] = "🗃️ HISTORY — Raw Database (Do NOT edit manually)"
    ws["A1"].font = hdr_font()
    ws["A1"].fill = fill(C_DARK_BLUE)
    ws["A1"].alignment = center()

    # Headers
    history_headers = ["Date", "Rank", "Username", "Jade", "T1", "T2", "IsDelayed", "Key"]
    for i, h in enumerate(history_headers):
        cell = ws.cell(2, i+1)
        cell.value = h
        cell.font = hdr_font()
        cell.fill = fill(C_MED_BLUE)
        cell.alignment = center()
        cell.border = thin_border()

    ws.row_dimensions[2].height = 18

    # Populate with extracted records
    records_sorted = sorted(records, key=lambda r: (r["date"], r["rank"]))
    for i, rec in enumerate(records_sorted):
        row = i + 3
        d = rec["date"]
        ws.cell(row, 1).value = excel_date(d)
        ws.cell(row, 1).number_format = "dd/mm/yyyy"
        ws.cell(row, 2).value = rec["rank"]
        ws.cell(row, 3).value = rec["username"]
        ws.cell(row, 4).value = rec["jade"]
        ws.cell(row, 5).value = rec["t1"]
        ws.cell(row, 6).value = rec["t2"]
        ws.cell(row, 7).value = rec["is_delayed"]
        ws.cell(row, 8).value = rec["key"]

        for c in range(1, 9):
            ws.cell(row, c).font = Font(name="Arial", size=9)
            ws.cell(row, c).border = thin_border()

        # Highlight leader
        if rec["username"] == LEADER:
            for c in range(1, 9):
                ws.cell(row, c).fill = fill("E2EFDA")
        elif rec["username"] in TEAM_ALL:
            for c in range(1, 9):
                ws.cell(row, c).fill = fill("EBF3FB")

    # Column widths
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 7
    ws.column_dimensions["C"].width = 32
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 6
    ws.column_dimensions["F"].width = 6
    ws.column_dimensions["G"].width = 10
    ws.column_dimensions["H"].width = 38

    # Freeze row 2
    ws.freeze_panes = "A3"

    return ws


def build_tracker_sheet(wb, all_users=None):
    """
    TRACKER: One row per user, all computed values (written by ARO_update.py).
    This function creates the shell — ARO_update.py fills the data.
    """
    ws = wb.create_sheet("📊 TRACKER")
    ws.tab_color = "2E75B6"

    # Title
    ws.merge_cells("A1:O1")
    ws["A1"] = "📊 TRACKER — Per-User Metrics (Auto-updated by ARO_update.py)"
    ws["A1"].font = hdr_font(size=11)
    ws["A1"].fill = fill(C_DARK_BLUE)
    ws["A1"].alignment = center()
    ws.row_dimensions[1].height = 22

    # Column definitions
    tracker_cols = [
        ("A", "Username",        32),
        ("B", "Team?",           7),
        ("C", "Level",           8),
        ("D", "Rank\n(latest)",  8),
        ("E", "Jade\n(latest)",  13),
        ("F", "T1",              6),
        ("G", "T2",              6),
        ("H", "Δ Today",         11),
        ("I", "Δ Prev",          11),
        ("J", "W.Rate\n(wgt)",   11),
        ("K", "Proj\n31/05",     14),
        ("L", "Prize\n(USD)",    10),
        ("M", "Days\nActive",    8),
        ("N", "First\nSeen",     12),
        ("O", "Status",          10),
    ]

    for i, (col_letter, header, width) in enumerate(tracker_cols):
        cell = ws.cell(2, i+1)
        cell.value = header
        cell.font = hdr_font(size=9)
        cell.fill = fill(C_MED_BLUE)
        cell.alignment = center()
        cell.border = thin_border()
        ws.column_dimensions[col_letter].width = width

    ws.row_dimensions[2].height = 28

    # Pre-populate with known users if provided
    if all_users:
        for i, username in enumerate(all_users):
            row = i + 3
            ws.cell(row, 1).value = username
            ws.cell(row, 1).font = Font(name="Arial", size=9)

            # Style based on team membership
            if username == LEADER:
                for c in range(1, 16):
                    ws.cell(row, c).fill = fill("E2EFDA")
                ws.cell(row, 1).font = Font(name="Arial", bold=True, color=C_LEADER, size=9)
            elif username in TEAM_ALL:
                for c in range(1, 16):
                    ws.cell(row, c).fill = fill("EBF3FB")
            elif i % 2 == 0:
                for c in range(1, 16):
                    ws.cell(row, c).fill = fill("F7F7F7")

            for c in range(1, 16):
                ws.cell(row, c).border = thin_border()

    # Freeze
    ws.freeze_panes = "A3"

    return ws


def build_dashboard_sheet(wb):
    """
    DASHBOARD: Structured zones for Claude to read.
    Filled by ARO_update.py.
    """
    ws = wb.create_sheet("🏆 DASHBOARD")
    ws.tab_color = "FF7700"

    def section_title(row, text, color=C_DARK_BLUE):
        ws.merge_cells(f"A{row}:J{row}")
        ws[f"A{row}"] = text
        ws[f"A{row}"].font = hdr_font(size=10)
        ws[f"A{row}"].fill = fill(color)
        ws[f"A{row}"].alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[row].height = 20

    # ── Title ─────────────────────────────────────────
    ws.merge_cells("A1:J1")
    ws["A1"] = "🏆 ARO Sprint 2 — DASHBOARD (Auto-generated by ARO_update.py)"
    ws["A1"].font = hdr_font(size=13)
    ws["A1"].fill = fill(C_DARK_BLUE)
    ws["A1"].alignment = center()
    ws.row_dimensions[1].height = 26

    # ── Section 1: nau*** Stats (rows 3-14) ─────────────────────────────────
    section_title(3, "📌 SECTION 1 — nau*** STATUS", C_LEADER)

    stats_labels = [
        (4,  "Rank",              "D4",  ""),
        (5,  "Jade",              "D5",  ""),
        (6,  "T1 Refs",           "D6",  ""),
        (7,  "T2 Refs",           "D7",  ""),
        (8,  "Δ Hôm nay",         "D8",  ""),
        (9,  "W.Rate (/ngày)",    "D9",  ""),
        (10, "Dự báo 31/05",      "D10", ""),
        (11, "Prize dự kiến",     "D11", ""),
        (12, "Gap vs #2",         "D12", ""),
        (13, "Gap vs #3",         "D13", ""),
        (14, "Ngày cập nhật",     "D14", ""),
    ]
    for row, label, val_cell, default in stats_labels:
        ws[f"A{row}"] = label
        ws[f"A{row}"].font = Font(name="Arial", bold=True, size=9)
        ws[f"D{row}"] = default
        ws[f"D{row}"].font = Font(name="Arial", size=9)

    # ── Section 2: Top 10 (rows 16-28) ────────────────────────────────────
    section_title(16, "🥇 SECTION 2 — TOP 10 BXH")
    top10_headers = ["#", "Username", "Jade", "Δ Hôm nay", "Δ Hôm qua",
                     "W.Rate", "Proj 31/05", "Prize", "T1", "T2", "Ghi chú"]
    for i, h in enumerate(top10_headers):
        cell = ws.cell(17, i+1)
        cell.value = h
        cell.font = hdr_font(size=9)
        cell.fill = fill(C_MED_BLUE)
        cell.alignment = center()
        cell.border = thin_border()
    ws.row_dimensions[17].height = 18
    for row in range(18, 28):
        for col in range(1, 12):
            ws.cell(row, col).border = thin_border()
            ws.cell(row, col).font = Font(name="Arial", size=9)
            ws.cell(row, col).alignment = center()

    # ── Section 3: Top T1 Refs (rows 30-42) ───────────────────────────────
    section_title(30, "🔗 SECTION 3 — TOP 10 T1 REFS NHIỀU NHẤT")
    t1_headers = ["#", "Username", "T1", "T2", "Jade", "Δ/ngày", "W.Rate", "Verdict"]
    for i, h in enumerate(t1_headers):
        cell = ws.cell(31, i+1)
        cell.value = h
        cell.font = hdr_font(size=9)
        cell.fill = fill(C_MED_BLUE)
        cell.alignment = center()
        cell.border = thin_border()
    for row in range(32, 42):
        for col in range(1, 9):
            ws.cell(row, col).border = thin_border()
            ws.cell(row, col).font = Font(name="Arial", size=9)
            ws.cell(row, col).alignment = center()

    # ── Section 4: Team Status (rows 44-60) ─────────────────────────────────
    section_title(44, "👥 SECTION 4 — TEAM nau*** STATUS")
    team_headers = ["Username", "Level", "Rank", "Jade", "Δ Hôm nay",
                    "W.Rate", "Proj 31/05", "Prize", "Ghi chú"]
    for i, h in enumerate(team_headers):
        cell = ws.cell(45, i+1)
        cell.value = h
        cell.font = hdr_font(size=9)
        cell.fill = fill(C_LEADER)
        cell.alignment = center()
        cell.border = thin_border()
    for row in range(46, 60):
        for col in range(1, 10):
            ws.cell(row, col).border = thin_border()
            ws.cell(row, col).font = Font(name="Arial", size=9)

    # ── Section 5: Thresholds (rows 62-68) ────────────────────────────────
    section_title(62, "📏 SECTION 5 — NGƯỠNG BXH")
    thresh_headers = ["Ngưỡng", "Jade Hôm nay", "Jade Hôm qua", "Δ", "Trend"]
    for i, h in enumerate(thresh_headers):
        cell = ws.cell(63, i+1)
        cell.value = h
        cell.font = hdr_font(size=9)
        cell.fill = fill(C_MED_BLUE)
        cell.alignment = center()
    thresholds = ["Top #50", "Top #100"]
    for i, t in enumerate(thresholds):
        row = 64 + i
        ws.cell(row, 1).value = t
        ws.cell(row, 1).font = Font(name="Arial", bold=True, size=9)
        for col in range(1, 6):
            ws.cell(row, col).border = thin_border()

    # ── Section 6: Alerts (rows 70-80) ──────────────────────────────────
    section_title(70, "🚨 SECTION 6 — CẢNH BÁO TỰ ĐỘNG", C_ORANGE)
    ws.cell(71, 1).value = "Status"
    ws.cell(71, 1).font = Font(name="Arial", bold=True, size=9)
    ws.cell(71, 1).fill = fill(C_GRAY_H)
    ws.cell(71, 2).value = "Chi tiết"
    ws.cell(71, 2).font = Font(name="Arial", bold=True, size=9)
    ws.cell(71, 2).fill = fill(C_GRAY_H)
    ws.merge_cells("B71:J71")
    for row in range(72, 80):
        ws.cell(row, 1).border = thin_border()
        ws.merge_cells(f"B{row}:J{row}")
        ws.cell(row, 2).border = thin_border()
        ws.cell(row, 2).font = Font(name="Arial", size=9)

    # Column widths
    dashboard_widths = {
        "A":14, "B":30, "C":13, "D":13, "E":13,
        "F":13, "G":14, "H":10, "I":8, "J":8, "K":20
    }
    for col_letter, width in dashboard_widths.items():
        ws.column_dimensions[col_letter].width = width

    # Freeze
    ws.freeze_panes = "A2"

    return ws


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("ARO Sprint 2 — Master Excel Builder")
    print("=" * 60)

    # Step 1: Extract history from v24
    print("\n[1/4] Extracting history from v24...")
    records = extract_history_from_v24(EXISTING_V24)

    # Derive unique user list (sorted by latest jade desc)
    from collections import defaultdict
    user_latest_jade = defaultdict(int)
    for rec in records:
        if rec["jade"] > user_latest_jade[rec["username"]]:
            user_latest_jade[rec["username"]] = rec["jade"]

    all_users_sorted = sorted(user_latest_jade.keys(),
                              key=lambda u: -user_latest_jade[u])

    # Ensure team members are included even if not yet on BXH
    for tm in TEAM_ALL:
        if tm not in all_users_sorted:
            all_users_sorted.append(tm)

    print(f"    → {len(records)} history records, {len(all_users_sorted)} unique users")

    # Step 2: Create workbook
    print("\n[2/4] Creating workbook...")
    wb = Workbook()
    wb.remove(wb.active)  # Remove default sheet

    ws_config  = build_config_sheet(wb)
    ws_input   = build_input_sheet(wb)
    ws_history = build_history_sheet(wb, records)
    ws_tracker = build_tracker_sheet(wb, all_users_sorted)
    ws_dash    = build_dashboard_sheet(wb)

    # Step 3: Save
    print(f"\n[3/4] Saving to {MASTER_FILE}...")
    wb.save(MASTER_FILE)
    print(f"    ✅ Saved!")

    # Step 4: Run initial update
    print("\n[4/4] Running initial data computation...")
    print("    → Run ARO_update.py to populate TRACKER and DASHBOARD")
    print("       (or run it now automatically if records exist)")

    if records:
        try:
            import subprocess
            result = subprocess.run(
                ["python", os.path.join(BASE_DIR, "ARO_update.py"), "--skip-input"],
                capture_output=True, text=True, cwd=BASE_DIR
            )
            print(result.stdout)
            if result.returncode != 0:
                print(f"[WARN] Update script error: {result.stderr}")
        except Exception as e:
            print(f"[WARN] Could not auto-run update: {e}")
            print("       → Run 'python ARO_update.py --skip-input' manually")

    print("\n" + "=" * 60)
    print("✅ DONE! ARO_MASTER.xlsx created successfully.")
    print("=" * 60)
    print("\nQuy trình hàng ngày:")
    print("  1. Mở ARO_MASTER.xlsx")
    print("  2. Sheet 📥 INPUT: nhập ngày vào C3, dán 4 cột BXH vào B6:E105")
    print("  3. Lưu file")
    print("  4. Nói với Claude: 'Cập nhật và viết báo cáo đi'")
    print("  5. Claude chạy ARO_update.py → đọc DASHBOARD → viết báo cáo")


if __name__ == "__main__":
    main()
