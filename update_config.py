import openpyxl

wb = openpyxl.load_workbook("ARO_MASTER.xlsx")
ws = wb["⚙️ CONFIG"]

# Find TEAM ROSTER
start_row = None
for r in range(1, 50):
    if ws.cell(row=r, column=1).value == "TEAM ROSTER":
        start_row = r + 1
        break

if start_row:
    # It has 'Username', 'Level', 'Ghi chú'
    # We will insert 'Jade_Cap' at column 3, shift 'Ghi chú' to 4
    if ws.cell(row=start_row, column=3).value != "Jade_Cap":
        ws.cell(row=start_row, column=3).value = "Jade_Cap"
        ws.cell(row=start_row, column=4).value = "Ghi chú"
        
        for r in range(start_row + 1, 50):
            user = ws.cell(row=r, column=1).value
            if user:
                # normalize user
                if "@gmail.com" in user:
                    ws.cell(row=r, column=1).value = user.replace("@gmail.com", "")
                    user = ws.cell(row=r, column=1).value
                
                # set Jade_Cap
                if user == "hun***":
                    ws.cell(row=r, column=3).value = 30000
                else:
                    ws.cell(row=r, column=3).value = 999999

wb.save("ARO_MASTER.xlsx")
print("CONFIG updated!")
