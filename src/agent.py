import json
from openai import OpenAI
from src.prompts import SYSTEM_PROMPT
from src.tools import get_tool_definitions, execute_tool, format_tool_result


def validate_itinerary_poi_ids(itinerary, allowed_pois):
    valid_ids = set(allowed_pois.keys())

    for day in itinerary.get("days", []):
        for block in ["morning", "afternoon", "evening"]:
            for item in day.get(block, []):
                poi_id = item.get("poi_id")
                if poi_id not in valid_ids:
                    raise ValueError(f"Invalid poi_id in itinerary: {poi_id}")


def build_user_prompt(destination, duration, interests):
    interests_text = ", ".join(interests) if interests else "general sightseeing"
    return f"""
Create a {duration}-day itinerary for {destination}.

User interests: {interests_text}

Requirements:
- Use tools when needed.
- Only use POIs that came from tool results.
- Return JSON with this structure:

{{
  "destination": "string",
  "duration_days": integer,
  "summary": "string",
  "days": [
    {{
      "day": 1,
      "theme": "string",
      "morning": [
        {{
          "time": "string",
          "activity": "string",
          "poi_id": "string"
        }}
      ],
      "afternoon": [],
      "evening": []
    }}
  ]
}}
"""


def mock_agent_plan(destination, duration, interests, tool_state):
    """
    Temporary fallback until billing is enabled.
    Uses already-built tools to simulate an agent flow.
    """
    pois = execute_tool(
        "search_pois",
        {
            "city_name": destination,
            "interests": interests,
            "radius": 3000,
            "limit": 15
        },
        tool_state
    )

    guide_chunks = execute_tool(
        "retrieve_guides",
        {
            "destination": destination,
            "query": f"{destination} travel tips for {', '.join(interests)}",
            "top_k": 3
        },
        tool_state
    )

    selected = pois[: min(len(pois), duration * 3)]

    days = []
    idx = 0
    for day_num in range(1, duration + 1):
        morning = []
        afternoon = []
        evening = []

        if idx < len(selected):
            morning.append({
                "time": "09:00",
                "activity": f"Visit {selected[idx]['name']}",
                "poi_id": selected[idx]["poi_id"]
            })
            idx += 1

        if idx < len(selected):
            afternoon.append({
                "time": "13:00",
                "activity": f"Explore {selected[idx]['name']}",
                "poi_id": selected[idx]["poi_id"]
            })
            idx += 1

        if idx < len(selected):
            evening.append({
                "time": "18:00",
                "activity": f"Enjoy time at {selected[idx]['name']}",
                "poi_id": selected[idx]["poi_id"]
            })
            idx += 1

        days.append({
            "day": day_num,
            "theme": f"Day {day_num} in {destination}",
            "morning": morning,
            "afternoon": afternoon,
            "evening": evening
        })

    summary = f"A {duration}-day itinerary for {destination} focused on {', '.join(interests)}."
    if guide_chunks:
        summary += f" Enhanced with {len(guide_chunks)} travel-guide chunks."

    itinerary = {
        "destination": destination,
        "duration_days": duration,
        "summary": summary,
        "days": days
    }

    validate_itinerary_poi_ids(itinerary, tool_state["pois"])
    return itinerary


def run_openai_agent(api_key, destination, duration, interests, max_steps=6):
    client = OpenAI(api_key=api_key)

    tool_state = {
        "pois": {},
        "guide_chunks": {},
        "last_city": None,
        "trace": []
    }

    input_items = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": build_user_prompt(destination, duration, interests)
        }
    ]

    for step in range(max_steps):
        tool_state["trace"].append({
            "step_type": "model_call",
            "step": step + 1
        })

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=input_items,
            tools=get_tool_definitions()
        )

        function_calls = [
            item for item in response.output
            if item.type == "function_call"
        ]

        if not function_calls:
            final_text = response.output_text
            try:
                itinerary = json.loads(final_text)
            except json.JSONDecodeError as e:
                raise ValueError(f"Final model output was not valid JSON: {e}")

            validate_itinerary_poi_ids(itinerary, tool_state["pois"])
            return itinerary, tool_state

        for call in function_calls:
            tool_name = call.name
            arguments = json.loads(call.arguments)

            result = execute_tool(tool_name, arguments, tool_state)

            input_items.append(call)
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": format_tool_result(tool_name, result)
                }
            )

    raise RuntimeError("Agent stopped after reaching max_steps without producing a final itinerary.")


def generate_itinerary(api_key, destination, duration, interests):
    tool_state = {
        "pois": {},
        "guide_chunks": {},
        "last_city": None,
        "trace": []
    }

    if api_key:
        itinerary, tool_state = run_openai_agent(
            api_key=api_key,
            destination=destination,
            duration=duration,
            interests=interests
        )
        return itinerary, tool_state

    itinerary = mock_agent_plan(destination, duration, interests, tool_state)
    return itinerary, tool_state