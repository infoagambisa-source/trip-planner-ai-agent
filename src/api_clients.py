import requests
import time
import streamlit as st
import re
import html

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.feedback import feedback_boost_map, normalize_city_key

USER_AGENT = "trip-planner-capstone/1.0 (info.agambisa@gmail.com)"
HEADERS = {"User-Agent": USER_AGENT}

INTEREST_TO_TAGS = {
    "museums": [("tourism", "museum|gallery")],
    "food": [("amenity", "restaurant|cafe|fast_food")],
    "outdoors": [("leisure", "park|nature_reserve"), ("natural", "peak|beach|wood")],
    "history": [("historic", "museum|monument|memorial|castle|ruins|archaeological_site")],
    "art": [("tourism", "gallery|museum"), ("amenity", "arts_centre")],
    "shopping": [("shop", "mall|supermarket|department_store|boutique")],
    "nightlife": [("amenity", "bar|pub|nightclub")],
    "family": [("leisure", "park|playground"), ("tourism", "zoo|theme_park|aquarium")]
}

def _make_request_with_retries(method, url, max_retries=3, backoff=2, **kwargs):
    """
    Make an HTTP request with retry logic and basic rate-limit handling.
    """
    for attempt in range(max_retries):
        try:
            response = requests.request(
                method,
                url,
                headers=HEADERS,
                timeout=20,
                **kwargs
            )

            if response.status_code == 429:
                wait_time = backoff ** attempt
                print(f"Rate limited by {url}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response

        except requests.Timeout:
            if attempt == max_retries - 1:
                print(f"Request timed out after {max_retries} attempts: {url}")
                return None
            wait_time = backoff ** attempt
            print(f"Timeout calling {url}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

        except requests.RequestException as e:
            if attempt == max_retries - 1:
                print(f"Request failed after {max_retries} attempts: {e}")
                return None
            wait_time = backoff ** attempt
            print(f"Request error: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    return None

@st.cache_data(show_spinner=False)
def geocode_city(city_name):
    """
    Convert a city name into latitude and longitude using Nominatim API.
    Cached to reduce repeated API calls.
    """

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": city_name.strip(),
        "format": "json",
        "limit": 1
    }
    response = _make_request_with_retries("GET", url, params=params)
    # Respect rate limits
    time.sleep(1)

    if response is None:
        return None

    try:
        data = response.json()
        if not isinstance(data, list) or not data:
            return None
        
        return {
            "name": data[0]["display_name"],
            "lat": float(data[0]["lat"]),
            "lon": float(data[0]["lon"])
        }

    except (ValueError, KeyError, IndexError) as e:
        print(f"Error parsing geocode response: {e}")
        return None

def _build_overpass_query(lat, lon, tag_pairs, radius=3000):
    """
    Build an Overpass QL query using regex tag matching.
    """
    query_parts = []

    for key, value_pattern in tag_pairs:
        query_parts.append(f'node["{key}"~"^({value_pattern})$"](around:{radius},{lat},{lon});')
        query_parts.append(f'way["{key}"~"^({value_pattern})$"](around:{radius},{lat},{lon});')
        query_parts.append(f'relation["{key}"~"^({value_pattern})$"](around:{radius},{lat},{lon});')

    query_body = "\n".join(query_parts)

    return f"""
    [out:json][timeout:25];
    (
        {query_body}
    );
    out center;
    """


def _extract_poi(element, category):
    """
    Extract structured POI data from an Overpass element.
    """
    tags = element.get("tags", {})
    name = tags.get("name", "Unnamed")

    if "lat" in element and "lon" in element:
        poi_lat = element["lat"]
        poi_lon = element["lon"]
    elif "center" in element:
        poi_lat = element["center"]["lat"]
        poi_lon = element["center"]["lon"]
    else:
        return None

    website = tags.get("website") or tags.get("contact:website") or tags.get("url")
    poi_type = element.get("type", "unknown")
    poi_id_num = element.get("id", "unknown")

    return {
        "poi_id": f"{poi_type}/{poi_id_num}",
        "name": name,
        "category": category,
        "lat": poi_lat,
        "lon": poi_lon,
        "url": website if website else ""
    }
   

@st.cache_data(show_spinner=False)
def search_pois(city_name, interests, radius=3000, limit=20):
    """
    Search for POIs in a city based on one or more interests.

    Args:
        city_name (str): Destination city
        interests (list[str] or str): Interest categories such as food, museums, outdoors
        radius (int): Search radius in meters
        limit (int): Maximum POIs to return

    Returns:
        list[dict]: Structured POI data with poi_id, name, category, lat, lon, url
    """
    if isinstance(interests, str):
        interests = [interests]

    interests = [interest.strip().lower() for interest in interests if interest.strip()]

    location = geocode_city(city_name)
    if not location:
        return []

    lat = location["lat"]
    lon = location["lon"]

    all_pois = []
    seen_ids = set()

    for interest in interests:
        tag_pairs = INTEREST_TO_TAGS.get(interest)
        if not tag_pairs:
            continue

        overpass_query = _build_overpass_query(lat, lon, tag_pairs, radius=radius)

        response = _make_request_with_retries(
            "POST",
            "https://overpass-api.de/api/interpreter",
            data=overpass_query
        )

        if response is None:
            continue

        try:
            data = response.json()
            if not isinstance(data, dict):
                continue
            elements = data.get("elements", [])
            if not isinstance(elements, list):
                continue
        except ValueError as e:
            print(f"Error parsing Overpass response: {e}")
            continue

        for element in elements:
            poi = _extract_poi(element, interest)
            if not poi:
                continue

            if poi["poi_id"] in seen_ids:
                continue

            poi["_base_score"] = 1.0
            seen_ids.add(poi["poi_id"])
            all_pois.append(poi)

    city_key = normalize_city_key(city_name)
    boost_map = feedback_boost_map(city_key)

    for poi in all_pois:
        poi["_score"] = poi["_base_score"] + boost_map.get(poi["poi_id"], 0.0)

    all_pois.sort(key=lambda p: p["_score"], reverse=True)

    for poi in all_pois:
        poi.pop("_base_score", None)
        poi.pop("_score", None)

    return all_pois[:limit]

def _strip_html(raw_html):
    """
    Convert HTML into readable plain text.
    """
    if not raw_html:
        return ""

    text = html.unescape(raw_html)

    # Remove unwanted blocks first
    text = re.sub(r"<script.*?>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)

    # Preserve paragraph-like breaks
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</h[1-6]\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li\s*>", "\n", text, flags=re.IGNORECASE)

    # Remove remaining tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Clean whitespace
    text = re.sub(r"\r", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


def _chunk_text(text, chunk_size=900, min_chunk_size=250):
    """
    Chunk text while preserving paragraph boundaries and avoiding awkward splits.
    """
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())

            # If a single paragraph is too long, split on sentence boundaries
            if len(paragraph) > chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", paragraph)
                temp = ""

                for sentence in sentences:
                    sentence_candidate = f"{temp} {sentence}".strip() if temp else sentence
                    if len(sentence_candidate) <= chunk_size:
                        temp = sentence_candidate
                    else:
                        if temp:
                            chunks.append(temp.strip())
                        temp = sentence

                if temp:
                    current = temp.strip()
                else:
                    current = ""
            else:
                current = paragraph

    if current:
        chunks.append(current.strip())

    # Merge very small trailing chunks where possible
    merged = []
    for chunk in chunks:
        if merged and len(chunk) < min_chunk_size and len(merged[-1]) + len(chunk) + 2 <= chunk_size:
            merged[-1] = f"{merged[-1]}\n\n{chunk}".strip()
        else:
            merged.append(chunk)

    return merged


@st.cache_data(show_spinner=False)
def fetch_wikivoyage_article(destination):
    """
    Fetch rendered HTML content for a Wikivoyage page using the MediaWiki API.
    """
    search_url = "https://en.wikivoyage.org/w/api.php"
    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": destination,
        "format": "json",
        "srlimit": 1
    }

    search_response = _make_request_with_retries("GET", search_url, params=search_params)
    if search_response is None:
        return None

    try:
        search_data = search_response.json()
        results = search_data.get("query", {}).get("search", [])
        if not isinstance(results, list) or not results:
            return None
        title = results[0]["title"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        print(f"Error parsing Wikivoyage search response: {e}")
        return None

    parse_params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json"
    }

    parse_response = _make_request_with_retries("GET", search_url, params=parse_params)
    if parse_response is None:
        return None

    try:
        parse_data = parse_response.json()
        raw_html = parse_data["parse"]["text"]["*"]
        plain_text = _strip_html(raw_html)

        return {
            "title": title,
            "source": f"Wikivoyage:{title}",
            "text": plain_text
        }
    except (ValueError, KeyError, TypeError) as e:
        print(f"Error parsing Wikivoyage article content: {e}")
        return None


@st.cache_data(show_spinner=False)
def build_wikivoyage_index(destination, chunk_size=900):
    """
    Fetch, clean, chunk, and vectorize a Wikivoyage article for a destination.
    """
    article = fetch_wikivoyage_article(destination)
    if not article:
        return None

    chunks = _chunk_text(article["text"], chunk_size=chunk_size)
    if not chunks:
        return None

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        max_features=5000
    )
    chunk_vectors = vectorizer.fit_transform(chunks)

    chunk_records = []
    for idx, chunk in enumerate(chunks):
        chunk_records.append({
            "chunk_id": f"{article['title'].replace(' ', '_').lower()}_{idx}",
            "source": article["source"],
            "text": chunk
        })

    return {
        "title": article["title"],
        "source": article["source"],
        "chunks": chunk_records,
        "vectorizer": vectorizer,
        "chunk_vectors": chunk_vectors
    }


@st.cache_data(show_spinner=False)
def retrieve_wikivoyage_context(destination, query, top_k=5):
    """
    Retrieve the most relevant Wikivoyage chunks for a query.
    """
    index = build_wikivoyage_index(destination)
    if not index:
        return []

    vectorizer = index["vectorizer"]
    chunk_vectors = index["chunk_vectors"]
    chunk_records = index["chunks"]

    try:
        query_vector = vectorizer.transform([query])
        scores = cosine_similarity(query_vector, chunk_vectors)[0]
    except Exception as e:
        print(f"Error during semantic retrieval: {e}")
        return []

    ranked_indices = scores.argsort()[::-1][:top_k]

    results = []
    for idx in ranked_indices:
        results.append({
            "chunk_id": chunk_records[idx]["chunk_id"],
            "source": chunk_records[idx]["source"],
            "text": chunk_records[idx]["text"],
            "score": float(scores[idx])
        })

    return results