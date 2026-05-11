from datetime import date

def calculate_delta(current_jade, previous_jade):
    if previous_jade is None:
        return None
    return current_jade - previous_jade

def calculate_w_rate(history_deltas, is_delayed_list):
    """
    history_deltas: list of deltas from newest to oldest
    is_delayed_list: list of boolean flags corresponding to the deltas
    """
    if not history_deltas:
        return 0
    
    # Take up to 18 days
    deltas = history_deltas[:18]
    delayed = is_delayed_list[:18]
    
    total_weighted_delta = 0
    total_weight = 0
    
    for i, delta in enumerate(deltas):
        if delta is None:
            continue
            
        # Default weight: 15 for newest, 14, ..., 1 for oldest
        # Note: if deltas has fewer than 18 items, we should adjust
        # Spec says: weight[0] = 15 (mới nhất), ..., weight[17] = 1 (xa nhất)
        default_weight = 15 - i if i < 15 else 1
        
        # If delayed, weight = 2
        weight = 2 if (i < len(delayed) and delayed[i]) else default_weight
        
        total_weighted_delta += delta * weight
        total_weight += weight
        
    if total_weight == 0:
        return 0
        
    return total_weighted_delta / total_weight

def project_may31(current_jade, w_rate, current_date):
    target_date = date(2026, 5, 31)
    days_left = (target_date - current_date).days
    if days_left < 0:
        days_left = 0
    return int(current_jade + w_rate * days_left)

def estimate_prize(rank):
    if rank == 1:
        return "$5,000"
    elif 2 <= rank <= 5:
        return "$2,000"
    elif 6 <= rank <= 10:
        return "$1,000"
    elif 11 <= rank <= 50:
        return "$200"
    elif 51 <= rank <= 100:
        return "$50"
    else:
        return "$0"
