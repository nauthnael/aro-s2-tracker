import json
import re
from bs4 import BeautifulSoup

def parse_jade(jade_str):
    """Convert '800.84K' to 800840 or '1.2M' to 1200000"""
    if not jade_str:
        return 0
    jade_str = jade_str.replace(',', '').upper()
    multiplier = 1
    if 'K' in jade_str:
        multiplier = 1000
        jade_str = jade_str.replace('K', '')
    elif 'M' in jade_str:
        multiplier = 1000000
        jade_str = jade_str.replace('M', '')
    
    try:
        return int(float(jade_str) * multiplier)
    except ValueError:
        return 0

def parse_refs(refs_str):
    """Parse '46 (19 Tier 1 + 27 Tier 2)' to (19, 27)"""
    if not refs_str:
        return 0, 0
    
    # Try to find Tier 1 and Tier 2 numbers
    t1_match = re.search(r'(\d+)\s+Tier\s+1', refs_str)
    t2_match = re.search(r'(\d+)\s+Tier\s+2', refs_str)
    
    t1 = int(t1_match.group(1)) if t1_match else 0
    t2 = int(t2_match.group(1)) if t2_match else 0
    
    return t1, t2

def parse_leaderboard_json(json_data):
    """
    Parse JSON string or list from ARO leaderboard.
    Example item: {"#":"1","username":"nau***@gmail.com","jades earned from campaign":"800.84K","referral count":"46 (19 Tier 1 + 27 Tier 2)"}
    """
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data
        
    parsed_results = []
    for item in data:
        # Skip separators or empty lines
        if item.get("#") == "s" or not item.get("username"):
            continue
            
        rank = int(item.get("#", 0))
        username = item.get("username", "")
        jade = parse_jade(item.get("jades earned from campaign", "0"))
        t1, t2 = parse_refs(item.get("referral count", ""))
        
        parsed_results.append({
            "rank": rank,
            "username": username,
            "jade": jade,
            "t1_refs": t1,
            "t2_refs": t2
        })
        
    return parsed_results

def parse_leaderboard_html(html_str):
    """
    Parse HTML table từ BXH ARO.
    Cấu trúc: <table> với 4 cột: #, Username, Jades Earned From Campaign, Referral Count
    Mỗi user có 2 row: 1 separator (# = "s") + 1 data row thật.
    """
    soup = BeautifulSoup(html_str, 'html.parser')
    table = soup.find('table')
    if not table:
        raise ValueError("Không tìm thấy thẻ <table> trong HTML")

    parsed_results = []
    for row in table.find_all('tr'):
        cells = row.find_all('td')
        if not cells:
            continue  # skip header row (th)
        
        rank_text = cells[0].get_text(strip=True)
        
        # Bỏ qua separator rows
        if rank_text == 's' or not rank_text.isdigit():
            continue
        
        rank = int(rank_text)
        username = cells[1].get_text(strip=True)
        jade_str = cells[2].get_text(strip=True)
        refs_str = cells[3].get_text(strip=True)
        
        jade = parse_jade(jade_str)
        t1, t2 = parse_refs(refs_str)
        
        parsed_results.append({
            "rank": rank,
            "username": username,
            "jade": jade,
            "t1_refs": t1,
            "t2_refs": t2
        })

    if len(parsed_results) == 0:
        raise ValueError("Parse HTML không tìm thấy dữ liệu. Kiểm tra lại HTML.")
    
    return parsed_results
