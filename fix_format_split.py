import sys
import openpyxl
from collections import defaultdict
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import date, timedelta
import ARO_update

def from_excel_date(serial: int) -> date:
    return date(1899, 12, 30) + timedelta(days=int(serial))

def main():
    print("Loading ARO_MASTER.xlsx...")
    wb = openpyxl.load_workbook("ARO_MASTER.xlsx")
    ws = wb["🗃️ HISTORY"]

    rows_data = []
    print("Reading history...")
    for row in ws.iter_rows(min_row=3, values_only=False):
        if row[0].value is None: continue
        
        date_val = row[0].value
        rank = row[1].value
        username = str(row[2].value).strip()
        jade = row[3].value
        t1 = row[4].value
        t2 = row[5].value
        delayed = row[6].value
        
        rows_data.append({
            "date_val": date_val,
            "rank": rank,
            "username": username,
            "jade": jade or 0,
            "t1": t1 or 0,
            "t2": t2 or 0,
            "delayed": delayed,
            "original_user": username
        })

    # Normalize
    for r in rows_data:
        if "@gmail.com" in r["username"]:
            r["username"] = r["username"].replace("@gmail.com", "")

    # Verify and merge
    history_by_user = defaultdict(list)
    for r in rows_data:
        history_by_user[r["username"]].append(r)

    merged_count = 0
    for u, recs in history_by_user.items():
        orig = set(r["original_user"] for r in recs)
        if len(orig) > 1:
            merged_count += 1
            # jade trajectory check
            short_jades = [r["jade"] for r in recs if "@gmail.com" not in r["original_user"]]
            full_jades = [r["jade"] for r in recs if "@gmail.com" in r["original_user"]]
            
            max_short = max(short_jades) if short_jades else 0
            max_full = max(full_jades) if full_jades else 0
            
            if max_short > 0 and max_full > 0:
                if max_short > max_full * 1.05:
                    print(f"[WARNING] Possible collision: {u} (max {max_short}) vs {u}@gmail.com (max {max_full}) — review manually")
            
            print(f"Merged {orig} -> {u}")

    # Remove duplicates
    unique_rows = {}
    deleted_duplicates = 0
    for r in rows_data:
        key = (r["date_val"], r["username"])
        if key not in unique_rows:
            unique_rows[key] = r
        else:
            deleted_duplicates += 1
            if r["jade"] > unique_rows[key]["jade"]:
                unique_rows[key] = r

    final_rows = sorted(unique_rows.values(), key=lambda x: (x["date_val"], -x["jade"]))

    print(f"Merged {merged_count} pairs, deleted {deleted_duplicates} duplicates")

    # Rewrite history
    print("Rewriting history...")
    max_row = ws.max_row
    if max_row >= 3:
        ws.delete_rows(3, max_row - 2)

    s = Side(style="thin", color="BBBBBB")
    border = Border(left=s, right=s, top=s, bottom=s)
    font = Font(name="Arial", size=9)

    # Make team sets without @gmail.com since history users are now stripped
    team_set_normalized = {u.replace("@gmail.com", "") for u in ARO_update.TEAM_SET}
    leader_normalized = ARO_update.LEADER.replace("@gmail.com", "")

    for i, r in enumerate(final_rows, start=3):
        if type(r["date_val"]) == int or type(r["date_val"]) == float:
            d_obj = from_excel_date(int(r["date_val"]))
        else:
            d_obj = r["date_val"]
            if hasattr(d_obj, 'date'): d_obj = d_obj.date()
        
        date_str = d_obj.strftime("%Y%m%d")
        key_str = f"{date_str}||{r['username']}"
        
        date_serial = r["date_val"] if isinstance(r["date_val"], (int, float)) else ARO_update.excel_date(d_obj)

        values = [date_serial, r["rank"], r["username"], r["jade"], r["t1"], r["t2"], r["delayed"], key_str]
        
        for col_i, val in enumerate(values, start=1):
            c = ws.cell(row=i, column=col_i)
            c.value = val
            c.font = font
            c.border = border
            if col_i == 1:
                c.number_format = "dd/mm/yyyy"

        # Highlights
        if r["username"] == leader_normalized:
            for col_i in range(1, 9):
                ws.cell(row=i, column=col_i).fill = PatternFill("solid", fgColor="E2EFDA")
        elif r["username"] in team_set_normalized:
            for col_i in range(1, 9):
                ws.cell(row=i, column=col_i).fill = PatternFill("solid", fgColor="EBF3FB")

    print("Saving ARO_MASTER.xlsx...")
    wb.save("ARO_MASTER.xlsx")

    print("Rebuilding TRACKER...")
    # Update ARO_update.LEADER temporarily? No, because we want it to work globally, 
    # but ARO_update hasn't been updated yet with normalize_username logic.
    # It's better to just save the workbook and we will run ARO_update.py script from command line later
    # after updating ARO_update.py
    
    print("Done!")

if __name__ == "__main__":
    main()
