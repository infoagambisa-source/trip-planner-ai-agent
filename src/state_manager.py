import json
import os

APP_STATE_PATH = "data/app_state.json"


def load_app_state():
    if not os.path.exists(APP_STATE_PATH):
        return {"saved_itinerary": None}

    try:
        with open(APP_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "saved_itinerary" not in data:
                data["saved_itinerary"] = None
            return data
    except (json.JSONDecodeError, OSError):
        return {"saved_itinerary": None}


def save_app_state(itinerary):
    state = {"saved_itinerary": itinerary}
    with open(APP_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)