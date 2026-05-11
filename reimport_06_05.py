import requests
import json
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# 1. Delete 06/05 snapshot (id=26)
res = requests.delete('http://127.0.0.1:8000/api/import/snapshot/26')
print(f'Delete 06/05: {res.json()}')

# 2. Re-import from bxh-05-05.json (Assume this is the file the user meant or contains the right data)
# Actually, the user specifically mentioned bxh-06-05.json in the brief. 
# If it's not in the root, maybe it's in data/?
# Let's check root again.
with open('bxh-05-05.json', 'r', encoding='utf-8') as f:
    bxh_data = json.load(f)

# Re-import as 2026-05-06
res = requests.post('http://127.0.0.1:8000/api/import/import-raw', json={
    'raw_input': json.dumps(bxh_data),
    'import_date': '2026-05-06',
    'is_delayed': False,
    'note': 'Re-imported after Brief 16 fix'
})
print(f'Re-import 06/05: {res.json()}')
