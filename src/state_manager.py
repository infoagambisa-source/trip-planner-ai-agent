import json
import os

APP_STATE_PATH = "data/app_state.json"


def load_app_state():
    if not os.path.exists(APP_STATE_PATH):
        return {"saved_itinerary": None, "saved_tool_state": {"pois": {}, "guide_chunks": {}, "trace": []}}

    try:
        with open(APP_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "saved_itinerary" not in data:
            data["saved_itinerary"] = None

        if "saved_tool_state" not in data:
            data["saved_tool_state"] = {"pois": {}, "guide_chunks": {}, "trace": []}

        return data
    except (json.JSONDecodeError, OSError):
        return {"saved_itinerary": None, "saved_tool_state": {"pois": {}, "guide_chunks": {}, "trace": []}}


def save_app_state(itinerary, tool_state):
    state = {
        "saved_itinerary": itinerary,
        "saved_tool_state": tool_state
    }
    with open(APP_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)