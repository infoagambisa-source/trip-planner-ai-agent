import json
from src.api_clients import search_pois, retrieve_wikivoyage_context


def get_tool_definitions():
    return [
        {
            "type": "function",
            "name": "search_pois",
            "description": "Find points of interest in a destination city based on user interests.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "city_name": {
                        "type": "string",
                        "description": "Destination city name, e.g. Paris"
                    },
                    "interests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Interest categories such as food, museums, outdoors, history"
                    },
                    "radius": {
                        "type": "integer",
                        "description": "Search radius in meters"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of POIs to return"
                    }
                },
                "required": ["city_name", "interests", "radius", "limit"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "retrieve_guides",
            "description": "Retrieve relevant travel-guide text chunks for a destination and query.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Destination city or place name"
                    },
                    "query": {
                        "type": "string",
                        "description": "Semantic retrieval query"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of guide chunks to return"
                    }
                },
                "required": ["destination", "query", "top_k"],
                "additionalProperties": False
            }
        }
    ]


def execute_tool(tool_name, arguments, tool_state):
    """
    Execute a tool call and update tool_state.
    """
    if tool_name == "search_pois":
        results = search_pois(
            city_name=arguments["city_name"],
            interests=arguments["interests"],
            radius=arguments["radius"],
            limit=arguments["limit"]
        )

        for poi in results:
            tool_state["pois"][poi["poi_id"]] = poi

        tool_state["last_city"] = arguments["city_name"]
        tool_state["trace"].append({
            "step_type": "tool_execution",
            "tool_name": tool_name,
            "arguments": arguments,
            "result_count": len(results)
        })

        return results

    if tool_name == "retrieve_guides":
        results = retrieve_wikivoyage_context(
            destination=arguments["destination"],
            query=arguments["query"],
            top_k=arguments["top_k"]
        )

        for chunk in results:
            tool_state["guide_chunks"][chunk["chunk_id"]] = chunk

        tool_state["trace"].append({
            "step_type": "tool_execution",
            "tool_name": tool_name,
            "arguments": arguments,
            "result_count": len(results)
        })

        return results

    raise ValueError(f"Unknown tool: {tool_name}")


def format_tool_result(tool_name, result):
    return json.dumps(
        {
            "tool_name": tool_name,
            "result": result
        },
        ensure_ascii=False
    )