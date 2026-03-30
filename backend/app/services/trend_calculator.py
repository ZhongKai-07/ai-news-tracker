import math

TITLE_WEIGHT = 2.0
CONTENT_WEIGHT = 1.0

def calculate_daily_score(mentions):
    """Calculate trend score for a keyword on a single day.
    Each mention dict: {match_location: "title"|"content", source_weight: float}.
    Returns log-normalized score: log(1 + raw_score).
    """
    if not mentions:
        return 0.0
    raw = 0.0
    for m in mentions:
        location_weight = TITLE_WEIGHT if m["match_location"] == "title" else CONTENT_WEIGHT
        raw += location_weight * m.get("source_weight", 1.0)
    return math.log(1 + raw)

def detect_trend_direction(scores):
    """Detect trend direction from a list of daily scores (oldest first).
    Returns: "rising", "falling", or "stable".
    """
    if len(scores) < 2:
        return "stable"
    mid = len(scores) // 2
    first_half_avg = sum(scores[:mid]) / mid if mid > 0 else 0
    second_half_avg = sum(scores[mid:]) / (len(scores) - mid) if (len(scores) - mid) > 0 else 0
    diff = second_half_avg - first_half_avg
    threshold = 0.3
    if diff > threshold:
        return "rising"
    elif diff < -threshold:
        return "falling"
    return "stable"
