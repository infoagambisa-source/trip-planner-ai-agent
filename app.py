import streamlit as st
from src.api_clients import (
    geocode_city,
    search_pois,
    fetch_wikivoyage_article,
    retrieve_wikivoyage_context
)

st.set_page_config(page_title="Trip Planner AI Agent", layout="wide")

if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = ""

st.title("Trip Planner AI Agent")
st.write("Plan intelligent trips with AI, live POI search, and optional Wikivoyage RAG.")

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
    destination = st.text_input("Destination", placeholder="e.g. Paris")
    start_date = st.date_input("Start date")

with col2:
    duration = st.number_input("Trip duration (days)", min_value=1, max_value=30, value=3)
    interests = st.multiselect(
        "Interests",
        options=["food", "museums", "outdoors", "history", "art", "shopping", "nightlife", "family"],
        default=["food", "museums"]
    )

if st.button("Generate Itinerary"):
    if not destination:
        st.warning("Please enter a destination.")
    else:
        if api_key:
            st.success("OpenAI API key stored in session.")
        else:
            st.info("No API key detected — running in MOCK mode.")

        location = geocode_city(destination)

        if not location:
            st.error("Could not find that location.")
        else:
            st.write("### Geocoding Result")
            st.json(location)

            pois = search_pois(destination, interests, radius=3000, limit=20)

            st.write("### Points of Interest")
            if pois:
                st.success(f"Found {len(pois)} POIs.")
                st.dataframe(pois)
            else:
                st.warning("No POIs found for the selected interests.")

            if use_wikivoyage:
                article = fetch_wikivoyage_article(destination)

                st.write("### Wikivoyage")
                if article:
                    st.success(f"Fetched article: {article['title']}")
                    st.text_area("Article Preview", article["text"][:2000], height=250)

                    rag_query = f"{destination} travel tips for {', '.join(interests)}"
                    chunks = retrieve_wikivoyage_context(destination, rag_query, top_k=3)

                    st.write("### Retrieved Travel Context")
                    if chunks:
                        for chunk in chunks:
                            st.markdown(
                                f"""
**Chunk ID:** {chunk['chunk_id']}  
**Source:** {chunk['source']}  
**Score:** {chunk['score']:.4f}

{chunk['text']}
---
"""
                            )
                    else:
                        st.warning("No relevant Wikivoyage chunks found.")
                else:
                    st.warning("Could not fetch Wikivoyage content for this destination.")