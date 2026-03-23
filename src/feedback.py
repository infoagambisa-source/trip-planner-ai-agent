import json
import os
import time

FEEDBACK_PATH = "data/feedback.jsonl"


def normalize_city_key(city_name: str) -> str:
    return city_name.strip().lower()


def save_feedback(city_key: str, poi_id: str, vote: str) -> None:
    """
    Append a feedback event to the JSONL file.
    """
    if vote not in {"up", "down"}:
        raise ValueError("vote must be 'up' or 'down'")

    event = {
        "ts": time.time(),
        "city_key": city_key,
        "poi_id": poi_id,
        "vote": vote
    }

    with open(FEEDBACK_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_feedback_events():
    """
    Load all feedback events from disk.
    """
    if not os.path.exists(FEEDBACK_PATH):
        return []

    events = []
    with open(FEEDBACK_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return events


def feedback_boost_map(city_key: str) -> dict:
    """
    Compute boost values per POI for a specific city.
    +0.25 per upvote
    -0.35 per downvote
    """
    city_key = normalize_city_key(city_key)
    events = load_feedback_events()

    boosts = {}
    for event in events:
        if event.get("city_key") != city_key:
            continue

        poi_id = event.get("poi_id")
        vote = event.get("vote")

        if not poi_id:
            continue

        if poi_id not in boosts:
            boosts[poi_id] = 0.0

        if vote == "up":
            boosts[poi_id] += 0.25
        elif vote == "down":
            boosts[poi_id] -= 0.35

    return boosts


def feedback_stats_for_city(city_key: str) -> dict:
    """
    Optional summary stats for display/debugging.
    """
    city_key = normalize_city_key(city_key)
    events = load_feedback_events()

    stats = {}
    for event in events:
        if event.get("city_key") != city_key:
            continue

        poi_id = event.get("poi_id")
        vote = event.get("vote")

        if not poi_id:
            continue

        if poi_id not in stats:
            stats[poi_id] = {"up": 0, "down": 0, "boost": 0.0}

        if vote == "up":
            stats[poi_id]["up"] += 1
            stats[poi_id]["boost"] += 0.25
        elif vote == "down":
            stats[poi_id]["down"] += 1
            stats[poi_id]["boost"] -= 0.35

    return stats