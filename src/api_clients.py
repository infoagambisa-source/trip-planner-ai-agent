import requests
import time

USER_AGENT = "trip-planner-capstone/1.0 (info.agambisa@gmail.com)"
HEADERS = {"User-Agent": USER_AGENT}


def geocode_city(city_name):
    """
    Convert a city name into latitude and longitude using Nominatim API.
    """

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": city_name,
        "format": "json",
        "limit": 1
    }

    try:
        response = requests.get(url, params=params, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        # Respect rate limits
        time.sleep(1)

        if not data:
            return None

        return {
            "name": data[0]["display_name"],
            "lat": float(data[0]["lat"]),
            "lon": float(data[0]["lon"])
        }

    except requests.RequestException as e:
        print(f"Geocoding error: {e}")
        return None
    

def search_pois(lat, lon, query="restaurant", radius=2000, limit=10):
    """
    Search for nearby Points of Interest using Overpass API.
    """
    overpass_url = "https://overpass-api.de/api/interpreter"

    overpass_query = f"""
    [out:json];
    (
      node["amenity"="{query}"](around:{radius},{lat},{lon});
      way["amenity"="{query}"](around:{radius},{lat},{lon});
      relation["amenity"="{query}"](around:{radius},{lat},{lon});
    );
    out center {limit};
    """

    try:
        response = requests.post(
            overpass_url,
            data=overpass_query,
            headers=HEADERS,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()

        pois = []
        for element in data.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name", "Unnamed")

            if "lat" in element and "lon" in element:
                poi_lat = element["lat"]
                poi_lon = element["lon"]
            elif "center" in element:
                poi_lat = element["center"]["lat"]
                poi_lon = element["center"]["lon"]
            else:
                continue

            pois.append({
                "name": name,
                "type": query,
                "lat": poi_lat,
                "lon": poi_lon,
                "address": tags.get("addr:full", "N/A")
            })

        return pois[:limit]

    except requests.RequestException as e:
        print(f"Overpass API error: {e}")
        return []