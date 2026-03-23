import json
import streamlit as st
import pydeck as pdk

from src.agent import generate_itinerary, refine_itinerary
from src.state_manager import load_app_state, save_app_state
from src.map_utils import itinerary_to_map_data, filter_points_by_day, build_path_data, compute_view_state
from src.feedback import save_feedback, normalize_city_key, feedback_stats_for_city
from src.utils import validate_trip_inputs

st.set_page_config(page_title="Trip Planner AI Agent", layout="wide")

# Session state setup
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = ""

saved_state = load_app_state()
if "itinerary" not in st.session_state:
    st.session_state.itinerary = saved_state.get("saved_itinerary")

if "tool_state" not in st.session_state:
    st.session_state.tool_state = saved_state.get(
        "saved_tool_state",
        {"pois": {}, "guide_chunks": {}, "trace": []}
    )

if "map_style" not in st.session_state:
    st.session_state.map_style = "light"

if "previous_itinerary" not in st.session_state:
    st.session_state.previous_itinerary = None

if "fast_mode" not in st.session_state:
    st.session_state.fast_mode = False

if "model_name" not in st.session_state:
    st.session_state.model_name = "gpt-4.1-mini"

if "max_steps" not in st.session_state:
    st.session_state.max_steps = 6

st.title("Trip Planner AI Agent")
st.write("Create personalised itineraries with POI search, optional travel-guide retrieval, and structured daily plans.")
st.info(
    "Enter a destination, choose your pace and interests, then generate an itinerary. "
    "Use Fast Mode for quicker drafts, and refine later for better results."
)

with st.sidebar:
    st.header("Settings")

    api_key_input = st.text_input(
        "OpenAI API Key",
        type="password",
        value=st.session_state.openai_api_key,
        key="api_key_input"
    )

    if api_key_input:
        st.session_state.openai_api_key = api_key_input

    if st.button("Clear API Key"):
        st.session_state.openai_api_key = ""
        st.rerun()

    st.header("Configuration")

    st.session_state.fast_mode = st.toggle(
        "Fast Mode",
        value=st.session_state.fast_mode,
        help="Uses fewer tool calls and lighter retrieval for faster results."
    )

    st.session_state.model_name = st.selectbox(
        "Model",
        options=["gpt-4.1-mini"],
        index=0,
        help="Choose the model used for itinerary generation when billing is enabled."
    )

    st.session_state.max_steps = st.slider(
        "Max Agent Steps",
        min_value=3,
        max_value=10,
        value=st.session_state.max_steps,
        help="Limits how many reasoning/tool steps the agent can take."
    )

    show_trace = st.checkbox(
        "Show execution trace",
        value=True,
        help="View tool calls and timings after generation."
    )

    st.caption("Tip: Fast Mode is useful for quick drafts and slower connections.")

    show_trace = st.checkbox("Show execution trace", value=True)
    
    map_style = st.radio("Map Style", options=["light", "dark"], index=0)
    st.session_state.map_style = map_style

st.subheader("Plan Your Trip")

col1, col2 = st.columns(2)

with col1:
    destination = st.text_input("Destination", placeholder="e.g. Paris")
    start_date =st.date_input("Start Date")
    duration = st.number_input("Trip length (days)", min_value=1, max_value=30, value=3)
    pace = st.selectbox("Pace", options=["relaxed", "balanced", "fast"], index=1)

with col2:
    interests = st.multiselect(
        "Interests",
        options=["food", "museums", "outdoors", "history", "art", "shopping", "nightlife", "family"],
        default=["food", "museums"]
    )
    st.caption("Pick interests that best match the kind of trip you want.")
    
    constraints = st.text_area(
        "Constraints",
        placeholder="e.g. vegetarian food only, budget-friendly, avoid late nights, family-friendly"
    )

generate_clicked = st.button("Generate Itinerary", type="primary")

if generate_clicked:
    error_message = validate_trip_inputs(destination, duration, pace, interests)

    if error_message:
        st.warning(error_message)
    else:
        with st.status("Generating itinerary...", expanded=True) as status:
            if st.session_state.fast_mode:
                st.write("⚡ Fast Mode is enabled: using fewer tool calls for quicker results.")
            
            st.write("Collecting destination context...")
            st.write("Searching for points of interest...")
            st.write("Retrieving travel-guide context...")
            st.write("Building itinerary...")

            try:
                itinerary, tool_state = generate_itinerary(
                    api_key=st.session_state.openai_api_key,
                    destination=destination,
                    duration=duration,
                    pace=pace,
                    interests=interests,
                    constraints=constraints,
                    start_date=str(start_date),
                    model_name=st.session_state.model_name,
                    max_steps=5 if st.session_state.fast_mode else st.session_state.max_steps,
                    fast_mode=st.session_state.fast_mode
                )

                if not itinerary or not itinerary.get("days"):
                    raise ValueError(
                        "The itinerary was generated but contains no day plans. "
                        "Try broadening your interests or choosing a larger city."
                    )

                st.session_state.itinerary = itinerary
                st.session_state.tool_state = tool_state
                save_app_state(itinerary, tool_state)

                status.update(label="Itinerary generated successfully.", state="complete")

            except ValueError as e:
                status.update(label="Generation failed.", state="error")
                st.error(str(e))

            except RuntimeError as e:
                status.update(label="Generation failed.", state="error")
                st.error(str(e))

            except Exception as e:
                status.update(label="Generation failed.", state="error")
                st.error(f"Unexpected error while generating itinerary: {e}")

itinerary = st.session_state.itinerary

def render_block(title, activities, destination):
    st.subheader(title)
    if not activities:
        st.caption("No activities planned.")
        return

    city_key = normalize_city_key(destination)

    for item in activities:
        st.markdown(f"**{item.get('time', '')} — {item.get('name', 'Unknown place')}**")
        st.write(item.get("activity", ""))
        st.caption(item.get("why", ""))

        meta_parts = []
        if item.get("category"):
            meta_parts.append(f"Category: {item['category']}")
        if item.get("poi_id"):
            meta_parts.append(f"POI ID: {item['poi_id']}")
        if meta_parts:
            st.caption(" | ".join(meta_parts))

        citations = item.get("citations", [])
        if citations:
            st.caption("Sources: " + ", ".join(citations))

        poi_id = item.get("poi_id")
        if poi_id:
            up_col, down_col, spacer = st.columns([1, 1, 6])

            with up_col:
                if st.button("👍", key=f"up_{title}_{poi_id}_{item.get('time', '')}"):
                    save_feedback(city_key=city_key, poi_id=poi_id, vote="up")
                    st.success(f"Saved upvote for {item.get('name', 'POI')}")
                    st.rerun()

            with down_col:
                if st.button("👎", key=f"down_{title}_{poi_id}_{item.get('time', '')}"):
                    save_feedback(city_key=city_key, poi_id=poi_id, vote="down")
                    st.success(f"Saved downvote for {item.get('name', 'POI')}")
                    st.rerun()

        st.markdown("---")

if itinerary:
    st.write("## Itinerary Overview")
    st.markdown(f"**Destination:** {itinerary.get('destination', '')}")
    st.markdown(f"**Duration:** {itinerary.get('duration_days', '')} day(s)")
    st.markdown(f"**Pace:** {itinerary.get('pace', '')}")
    st.markdown(f"**Constraints:** {itinerary.get('constraints', 'None') or 'None'}")
    st.write(itinerary.get("summary", ""))

    with st.expander("Feedback Stats", expanded=False):
        city_key = normalize_city_key(itinerary.get("destination", ""))
        stats = feedback_stats_for_city(city_key)

        if stats:
            feedback_rows = []
            poi_lookup = st.session_state.tool_state.get("pois", {})

            for poi_id, values in stats.items():
                feedback_rows.append({
                    "poi_id": poi_id,
                    "name": poi_lookup.get(poi_id, {}).get("name", "Unknown"),
                    "upvotes": values["up"],
                    "downvotes": values["down"],
                    "boost": values["boost"]
                })

            st.dataframe(feedback_rows)
        else:
            st.caption("No feedback recorded yet for this destination.")

    st.write("## Daily Itinerary")

    for day in itinerary.get("days", []):
        st.markdown(f"### {day.get('theme', '')}")

        col1, col2, col3 = st.columns(3)

        with col1:
            render_block("Morning", day.get("morning", []), itinerary.get("destination", ""))
        with col2:
            render_block("Afternoon", day.get("afternoon", []), itinerary.get("destination", ""))
        with col3:
            render_block("Evening", day.get("evening", []), itinerary.get("destination", ""))

    st.write("## Interactive Map")

    poi_lookup = st.session_state.tool_state.get("pois", {})
    points, day_paths = itinerary_to_map_data(itinerary, poi_lookup)

    day_options = ["All Days"] + [day.get("day") for day in itinerary.get("days", [])]
    selected_day = st.selectbox("Filter map by day", options=day_options, index=0)

    filtered_points = filter_points_by_day(points, selected_day=selected_day)
    filtered_paths = build_path_data(day_paths, selected_day=selected_day)

    if filtered_points:
        map_style_value = (
            "light" #"mapbox://styles/mapbox/light-v9"
            if st.session_state.map_style == "light"
            else "dark" #"mapbox://styles/mapbox/dark-v10"
        )

        view_state_dict = compute_view_state(filtered_points)

        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=filtered_points,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius=35,  
            radius_min_pixels=3, 
            radius_max_pixels=10, 
            pickable=True
        )

        text_layer = pdk.Layer(
            "TextLayer",
            data=filtered_points,
            get_position="[lon, lat]",
            get_text="name",
            get_size=12,
            get_angle=0,
            get_text_anchor="'start'",
            get_alignment_baseline="'center'",
            pickable=False
        )

        layers = [scatter_layer, text_layer]

        if filtered_paths:
            path_layer = pdk.Layer(
                "PathLayer",
                data=filtered_paths,
                get_path="path",
                get_color="color",
                width_scale=4,
                width_min_pixels=2,
                get_width=3,
                pickable=True
            )
            layers.insert(1, path_layer)

        deck = pdk.Deck(
            map_style=map_style_value,
            initial_view_state=pdk.ViewState(
                latitude=view_state_dict["latitude"],
                longitude=view_state_dict["longitude"],
                zoom=view_state_dict["zoom"],
                pitch=view_state_dict["pitch"]
            ),
            layers=layers,
            tooltip={
                "html": """
                <b>{name}</b><br/>
                Category: {category}<br/>
                Day: {day}<br/>
                Block: {block}<br/>
                Time: {time}<br/>
                {why}
                """,
                "style": {"backgroundColor": "steelblue", "color": "white"}
            }
        )

        st.pydeck_chart(deck, use_container_width=True)
    else:
        st.info("No map points available for the selected day filter.")

    st.write("## Refine Itinerary")

    refinement_request = st.text_input(
        "Refinement request",
        placeholder="e.g. make it more outdoorsy, add more food spots, avoid busy evenings"
    )

    day_numbers = [day.get("day") for day in itinerary.get("days", [])]
    refine_mode = st.radio(
        "Refinement mode",
        options=["Full itinerary", "Single day"],
        horizontal=True
    )

    target_day = None
    if refine_mode == "Single day":
        target_day = st.selectbox("Select day to regenerate", options=day_numbers)

    if st.button("Apply Refinement"):
        if not refinement_request.strip():
            st.warning("Please enter a refinement request.")
        else:
            try:
                st.session_state.previous_itinerary = json.loads(
                    json.dumps(st.session_state.itinerary)
                )

                with st.status("Refining itinerary...", expanded=True) as status:
                    if st.session_state.fast_mode:
                        status.write("⚡ Fast Mode is enabled for refinement.")
                    
                    status.write("Reviewing existing itinerary...")
                    status.write("Applying refinement instructions...")
                    status.write("Validating POI references...")

                    refined_itinerary, refined_tool_state = refine_itinerary(
                        api_key=st.session_state.openai_api_key,
                        existing_itinerary=st.session_state.itinerary,
                        user_request=refinement_request,
                        tool_state=st.session_state.tool_state,
                        target_day=target_day if refine_mode == "Single day" else None,
                        model_name=st.session_state.model_name,
                        max_steps=5 if st.session_state.fast_mode else st.session_state.max_steps
                    )

                    st.session_state.itinerary = refined_itinerary
                    st.session_state.tool_state = refined_tool_state
                    save_app_state(refined_itinerary, refined_tool_state)

                    status.update(label="Refinement applied successfully.", state="complete")

                st.success("Itinerary updated.")
                st.rerun()

            except ValueError as e:
                st.error(f"Refinement validation error: {e}")
            except RuntimeError as e:
                st.error(f"Refinement failed: {e}")
            except Exception as e:
                st.error(f"Unexpected refinement error: {e}")

    if st.session_state.previous_itinerary:
        with st.expander("Before / After Comparison", expanded=False):
            col_before, col_after = st.columns(2)

            with col_before:
                st.subheader("Before")
                st.json(st.session_state.previous_itinerary)

            with col_after:
                st.subheader("After")
                st.json(st.session_state.itinerary)

    st.write("## Export")
    itinerary_json = json.dumps(itinerary, indent=2, ensure_ascii=False)
    st.download_button(
        label="Download Itinerary JSON",
        data=itinerary_json,
        file_name="itinerary.json",
        mime="application/json"
    )

    if show_trace:
        st.write("## Agent Trace")

        trace_rows = []
        for entry in st.session_state.tool_state.get("trace", []):
            trace_rows.append({
                "step_type": entry.get("step_type", ""),
                "step": entry.get("step", ""),
                "tool_name": entry.get("tool_name", ""),
                "result_count": entry.get("result_count", ""),
                "elapsed_sec": entry.get("elapsed_sec", "")
            })

        if trace_rows:
            st.dataframe(trace_rows, use_container_width=True)
        else:
            st.caption("No trace data available.")

        st.write("## Tool Summary")
        st.write(f"POIs discovered: {len(st.session_state.tool_state.get('pois', {}))}")
        st.write(f"Guide chunks retrieved: {len(st.session_state.tool_state.get('guide_chunks', {}))}")
else:
    st.info("No itinerary generated yet. Fill in the trip details and click Generate Itinerary.")