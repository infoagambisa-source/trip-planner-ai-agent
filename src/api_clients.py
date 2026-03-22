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

    except Exception as e:
        print(f"Geocoding error: {e}")
        return None