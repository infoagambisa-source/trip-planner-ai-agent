import requests
import time
import streamlit as st

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
    Make an HTTP request with basic retry logic. 
    """
    for attempt in range(max_retries):
        try:
            response = requests.request(method, url, headers=HEADERS, timeout=60, **kwargs)
            response.raise_for_status()
            return response
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
        "q": city_name,
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
        if not data:
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
        except ValueError as e:
            print(f"Error parsing Overpass response: {e}")
            continue

        for element in data.get("elements", []):
            poi = _extract_poi(element, interest)
            if not poi:
                continue

            if poi["poi_id"] in seen_ids:
                continue

            seen_ids.add(poi["poi_id"])
            all_pois.append(poi)

    return all_pois[:limit]