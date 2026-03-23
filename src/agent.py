import copy
import json
import time
from openai import OpenAI
from src.prompts import SYSTEM_PROMPT
from src.tools import get_tool_definitions, execute_tool, format_tool_result
from src.utils import safe_json_loads


def validate_itinerary_poi_ids(itinerary, allowed_pois):
    valid_ids = set(allowed_pois.keys())

    for day in itinerary.get("days", []):
        for block in ["morning", "afternoon", "evening"]:
            for item in day.get(block, []):
                poi_id = item.get("poi_id")
                if poi_id not in valid_ids:
                    raise ValueError(f"Invalid poi_id in itinerary: {poi_id}")


def validate_single_day_unchanged(original_itinerary, refined_itinerary, target_day):
    original_days = original_itinerary.get("days", [])
    refined_days = refined_itinerary.get("days", [])

    if len(original_days) != len(refined_days):
        raise ValueError("Refined itinerary changed the number of days.")

    for orig_day, new_day in zip(original_days, refined_days):
        day_num = orig_day.get("day")
        if day_num == target_day:
            continue
        if orig_day != new_day:
            raise ValueError(f"Day {day_num} changed during single-day regeneration.")


def build_user_prompt(destination, duration, pace, interests, constraints, start_date, fast_mode=False):
    interests_text = ", ".join(interests) if interests else "general sightseeing"
    constraints_text = constraints if constraints else "None"

    tool_instructions = (
        "Call search_pois ONCE with broad criteria and keep tool usage minimal."
        if fast_mode
        else "You may call search_pois more than once if needed, but avoid unnecessary repetition."
    )

    return f"""
Create a {duration}-day itinerary for {destination}.

Start date: {start_date}
User interests: {interests_text}
Trip pace: {pace}
Constraints: {constraints_text}

Tool strategy:
{tool_instructions}

Requirements:
- Use tools when needed.
- Only use POIs that came from tool results.
- Keep the itinerary realistic for the requested pace.
- Return JSON with this structure:

{{
  "destination": "string",
  "start_date": "string",
  "duration_days": integer,
  "pace": "string",
  "constraints": "string",
  "summary": "string",
  "days": [
    {{
      "day": 1,
      "theme": "string",
      "morning": [
        {{
          "time": "string",
          "name": "string",
          "activity": "string",
          "why": "string",
          "poi_id": "string",
          "category": "string",
          "citations": ["string"]
        }}
      ],
      "afternoon": [],
      "evening": []
    }}
  ]
}}
"""


def build_refinement_prompt(existing_itinerary, user_request):
    return f"""
Refine this itinerary based on the user's request.

User request:
{user_request}

Rules:
- Preserve the same JSON structure.
- Only use POIs already available from tool calls.
- You may reorder activities or swap to other valid POIs returned by tools.
- Keep the trip coherent and realistic.

Existing itinerary:
{json.dumps(existing_itinerary, ensure_ascii=False)}
"""


def build_single_day_prompt(existing_itinerary, user_request, target_day):
    return f"""
Goal: ONLY modify day {target_day}. All other days must remain EXACTLY unchanged.

User request:
{user_request}

Rules:
- Preserve the same JSON structure.
- Only use POIs already available from tool calls.
- Days other than day {target_day} must remain unchanged.

Existing itinerary:
{json.dumps(existing_itinerary, ensure_ascii=False)}
"""


def mock_agent_plan(destination, duration, pace, interests, constraints, start_date, tool_state, fast_mode=False):
    poi_limit = 40 if fast_mode else 24

    start = time.perf_counter()
    pois = execute_tool(
        "search_pois",
        {
            "city_name": destination,
            "interests": interests,
            "radius": 3000,
            "limit": poi_limit
        },
        tool_state
    )
    tool_state["trace"][-1]["elapsed_sec"] = round(time.perf_counter() - start, 3)

    if not pois:
        raise ValueError(
            f"No matching POIs were found for {destination} with interests: {', '.join(interests)}. "
            "Try broader interests, a larger city, or fewer constraints."
        )

    start = time.perf_counter()
    guide_chunks = execute_tool(
        "retrieve_guides",
        {
            "destination": destination,
            "query": f"{destination} travel tips for {', '.join(interests)} with a {pace} pace",
            "top_k": 2 if fast_mode else 3
        },
        tool_state
    )
    tool_state["trace"][-1]["elapsed_sec"] = round(time.perf_counter() - start, 3)

    items_per_day = 2 if pace == "relaxed" else 3
    selected = pois[: min(len(pois), duration * items_per_day)]
    chunk_ids = [chunk["chunk_id"] for chunk in guide_chunks[:2]]

    days = []
    idx = 0
    for day_num in range(1, duration + 1):
        morning, afternoon, evening = [], [], []

        if idx < len(selected):
            poi = selected[idx]
            morning.append({
                "time": "09:00",
                "name": poi["name"],
                "activity": f"Visit {poi['name']}",
                "why": f"Good match for your interest in {poi['category']}.",
                "poi_id": poi["poi_id"],
                "category": poi["category"],
                "citations": chunk_ids
            })
            idx += 1

        if idx < len(selected):
            poi = selected[idx]
            afternoon.append({
                "time": "13:00",
                "name": poi["name"],
                "activity": f"Explore {poi['name']}",
                "why": f"Recommended as a worthwhile {poi['category']} stop in {destination}.",
                "poi_id": poi["poi_id"],
                "category": poi["category"],
                "citations": chunk_ids
            })
            idx += 1

        if pace != "relaxed" and idx < len(selected):
            poi = selected[idx]
            evening.append({
                "time": "18:00",
                "name": poi["name"],
                "activity": f"Spend the evening at {poi['name']}",
                "why": "Adds variety to the day and fits your selected interests.",
                "poi_id": poi["poi_id"],
                "category": poi["category"],
                "citations": chunk_ids
            })
            idx += 1

        days.append({
            "day": day_num,
            "theme": f"Day {day_num} in {destination}",
            "morning": morning,
            "afternoon": afternoon,
            "evening": evening
        })

    itinerary = {
        "destination": destination,
        "start_date": start_date,
        "duration_days": duration,
        "pace": pace,
        "constraints": constraints,
        "summary": f"A {duration}-day {pace}-pace itinerary for {destination} starting on {start_date}.",
        "days": days
    }

    validate_itinerary_poi_ids(itinerary, tool_state["pois"])
    return itinerary


def mock_refine_itinerary(existing_itinerary, user_request, tool_state, target_day=None):
    refined = copy.deepcopy(existing_itinerary)
    refined["summary"] = refined.get("summary", "") + f" Refined request: {user_request}"

    if target_day is None:
        for day in refined.get("days", []):
            day["theme"] = f"{day.get('theme', '')} (Refined)"
            for block in ["morning", "afternoon", "evening"]:
                for item in day.get(block, []):
                    item["why"] = f"{item.get('why', '')} Adjusted after refinement request."
    else:
        for day in refined.get("days", []):
            if day.get("day") == target_day:
                day["theme"] = f"{day.get('theme', '')} (Regenerated)"
                for block in ["morning", "afternoon", "evening"]:
                    for item in day.get(block, []):
                        item["why"] = f"{item.get('why', '')} Updated for day-specific refinement."

    validate_itinerary_poi_ids(refined, tool_state["pois"])
    if target_day is not None:
        validate_single_day_unchanged(existing_itinerary, refined, target_day)

    return refined


def run_openai_agent(api_key, prompt, tool_state, model_name="gpt-4.1-mini", max_steps=6):
    client = OpenAI(api_key=api_key)

    input_items = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    for step in range(max_steps):
        step_start = time.perf_counter()
        tool_state["trace"].append({
            "step_type": "model_call",
            "step": step + 1,
            "model": model_name
        })

        try:
            response = client.responses.create(
                model=model_name,
                input=input_items,
                tools=get_tool_definitions()
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI agent call failed at step {step + 1}: {e}") from e

        tool_state["trace"][-1]["elapsed_sec"] = round(time.perf_counter() - step_start, 3)

        function_calls = [item for item in response.output if item.type == "function_call"]

        if not function_calls:
            final_text = response.output_text
            itinerary = safe_json_loads(final_text, context="itinerary JSON")
            validate_itinerary_poi_ids(itinerary, tool_state["pois"])
            return itinerary, tool_state

        for call in function_calls:
            tool_name = call.name
            arguments = safe_json_loads(call.arguments, context=f"{tool_name} arguments")

            tool_start = time.perf_counter()
            result = execute_tool(tool_name, arguments, tool_state)
            tool_state["trace"][-1]["elapsed_sec"] = round(time.perf_counter() - tool_start, 3)

            input_items.append(call)
            input_items.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": format_tool_result(tool_name, result)
            })

    raise RuntimeError("Agent reached max_steps without producing a final itinerary.")


def generate_itinerary(
    api_key,
    destination,
    duration,
    pace,
    interests,
    constraints,
    start_date,
    model_name="gpt-4.1-mini",
    max_steps=6,
    fast_mode=False
):
    tool_state = {
        "pois": {},
        "guide_chunks": {},
        "last_city": None,
        "trace": []
    }

    if api_key:
        prompt = build_user_prompt(destination, duration, pace, interests, constraints, start_date, fast_mode=fast_mode)
        return run_openai_agent(
            api_key=api_key,
            prompt=prompt,
            tool_state=tool_state,
            model_name=model_name,
            max_steps=max_steps
        )

    itinerary = mock_agent_plan(
        destination,
        duration,
        pace,
        interests,
        constraints,
        start_date,
        tool_state,
        fast_mode=fast_mode
    )
    return itinerary, tool_state


def refine_itinerary(api_key, existing_itinerary, user_request, tool_state, target_day=None, model_name="gpt-4.1-mini", max_steps=6):
    if not existing_itinerary:
        raise ValueError("No existing itinerary to refine.")

    prompt = build_single_day_prompt(existing_itinerary, user_request, target_day) if target_day is not None else build_refinement_prompt(existing_itinerary, user_request)

    if api_key:
        refined_itinerary, updated_tool_state = run_openai_agent(
            api_key=api_key,
            prompt=prompt,
            tool_state=tool_state,
            model_name=model_name,
            max_steps=max_steps
        )
        validate_itinerary_poi_ids(refined_itinerary, updated_tool_state["pois"])
        if target_day is not None:
            validate_single_day_unchanged(existing_itinerary, refined_itinerary, target_day)
        return refined_itinerary, updated_tool_state

    refined_itinerary = mock_refine_itinerary(
        existing_itinerary=existing_itinerary,
        user_request=user_request,
        tool_state=tool_state,
        target_day=target_day
    )
    return refined_itinerary, tool_state