import json
import streamlit as st

from src.agent import generate_itinerary
from src.state_manager import load_app_state, save_app_state

st.set_page_config(page_title="Trip Planner AI Agent", layout="wide")

# Session state setup
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = ""

if "itinerary" not in st.session_state:
    saved_state = load_app_state()
    st.session_state.itinerary = saved_state.get("saved_itinerary")

if "tool_state" not in st.session_state:
    st.session_state.tool_state = {"pois": {}, "guide_chunks": {}, "trace": []}

st.title("Trip Planner AI Agent")
st.write("Create personalised itineraries with POI search, optional travel-guide retrieval, and structured daily plans.")

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

    show_trace = st.checkbox("Show execution trace", value=True)

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
    constraints = st.text_area(
        "Constraints",
        placeholder="e.g. vegetarian food only, budget-friendly, avoid late nights, family-friendly"
    )

generate_clicked = st.button("Generate Itinerary", type="primary")

if generate_clicked:
    if not destination:
        st.warning("Please enter a destination.")
    elif not interests:
        st.warning("Please select at least one interest.")
    else:
        with st.status("Generating itinerary...", expanded=True) as status:
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
                    start_date=str(start_date)
                )

                st.session_state.itinerary = itinerary
                st.session_state.tool_state = tool_state
                save_app_state(itinerary)

                status.update(label="Itinerary generated successfully.", state="complete")
            except Exception as e:
                status.update(label="Generation failed.", state="error")
                st.error(f"Agent error: {e}")

itinerary = st.session_state.itinerary

def render_block(title, activities):
    st.subheader(title)
    if not activities:
        st.caption("No activities planned.")
        return

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

        st.markdown("---")

if itinerary:
    st.write("## Itinerary Overview")
    st.markdown(f"**Destination:** {itinerary.get('destination', '')}")
    st.markdown(f"**Duration:** {itinerary.get('duration_days', '')} day(s)")
    st.markdown(f"**Pace:** {itinerary.get('pace', '')}")
    st.markdown(f"**Constraints:** {itinerary.get('constraints', 'None') or 'None'}")
    st.write(itinerary.get("summary", ""))

    st.write("## Daily Itinerary")

    for day in itinerary.get("days", []):
        st.markdown(f"### Day {day.get('day')} — {day.get('theme', '')}")

        col1, col2, col3 = st.columns(3)

        with col1:
            render_block("Morning", day.get("morning", []))
        with col2:
            render_block("Afternoon", day.get("afternoon", []))
        with col3:
            render_block("Evening", day.get("evening", []))

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
        st.json(st.session_state.tool_state.get("trace", []))

        st.write("## Tool Summary")
        st.write(f"POIs discovered: {len(st.session_state.tool_state.get('pois', {}))}")
        st.write(f"Guide chunks retrieved: {len(st.session_state.tool_state.get('guide_chunks', {}))}")
else:
    st.info("No itinerary generated yet. Fill in the trip details and click Generate Itinerary.")