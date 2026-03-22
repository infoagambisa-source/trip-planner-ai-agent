import streamlit as st
from src.api_clients import geocode_city, search_pois

st.set_page_config(page_title="Trip Planner AI Agent", layout="wide")

# Session state setup
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = ""

st.title("Trip Planner AI Agent")
st.write("Plan intelligent trips with AI, live POI search and interactive maps.")

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

    use_wikivoyage = st.checkbox("Enable Wikivoyage travel context", value=True)

api_key = st.session_state.openai_api_key

st.subheader("Trip Details")

col1, col2 = st.columns(2)

with col1:
    destination = st.text_input("Destination", placeholder="e.g. Madrid")
    start_date = st.date_input("Start date")

with col2:
    duration = st.number_input("Trip duration (days)", min_value=1, max_value=30, value=3)
    interests = st.text_input("Interests", placeholder="e.g. museums, food, history")

if st.button("Generate Itinerary"):
    if not destination:
        st.warning("Please enter a destination.")

    else:
        if api_key:
            st.success("OpeanAI API key stored in session.")
        else:
            st.info("No API key detected - running in MOCK mode.")
        
        location = geocode_city(destination)

        if location:
            st.success("Location found!")
            st.write("### Geocoding Result")
            st.json(location)

            pois = search_pois(location["lat"], location["lon"], query="restaurant")

            st.write("### Nearby POIs (restaurants)")
            if pois:
                st.write(f"Found {len(pois)} POIs.")
                st.dataframe(pois)
            else:
                st.warning("No POIs found.")

        else: 
            st.error("Could not find that location.")
    
    