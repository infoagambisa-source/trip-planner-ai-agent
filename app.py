import streamlit as st

st.set_page_config(page_title="Trip Planner AI Agent", layout="wide")

st.title("Trip Planner AI Agent")
st.write("Plan intelligent trips with AI, live POI search and interactive maps.")

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("OpenAI API Key", type="password")
    use_wikivoyage = st.checkbox("Enable Wikivoyage travel context", value=True)

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

    elif not api_key:
        st.warning("Please ennter your OpenAI API key in the sidebar.")
    
    else:
        st.success("Setup looks good. Next we’ll connect the APIs and AI agent.")
        st.write("### Preview")
        st.write(f"**Destination:** {destination}")
        st.write(f"**Duration:** {duration} day(s)")
        st.write(f"**Interests:** {interests if interests else 'Not provided'}")
        st.write(f"**Wikivoyage enabled:** {'Yes' if use_wikivoyage else 'No'}")