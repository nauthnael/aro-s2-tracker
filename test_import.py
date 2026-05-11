import requests
import json

def test_import():
    with open('bxh-29-04.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    payload = {
        "json_data": data,
        "import_date": "2026-04-29",
        "is_delayed": False,
        "note": "Initial import from JSON file"
    }
    
    response = requests.post("http://localhost:8000/api/import", json=payload)
    print(response.status_code)
    print(response.json())

if __name__ == "__main__":
    test_import()
