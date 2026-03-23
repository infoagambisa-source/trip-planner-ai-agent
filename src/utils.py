import json


def safe_json_loads(text: str, context: str = "JSON"):
    """
    Parse JSON safely and raise a clearer ValueError.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse {context}: {e.msg} at line {e.lineno}, column {e.colno}") from e


def validate_trip_inputs(destination, duration, pace, interests):
    """
    Validate user inputs before calling the agent.
    Returns None if valid, otherwise a user-friendly error string.
    """
    if not destination or not destination.strip():
        return "Please enter a destination."

    if len(destination.strip()) < 2:
        return "Destination must be at least 2 characters long."

    if duration < 1 or duration > 30:
        return "Trip length must be between 1 and 30 days."

    if pace not in {"relaxed", "balanced", "fast"}:
        return "Please choose a valid pace."

    if not interests:
        return "Please select at least one interest."

    return None