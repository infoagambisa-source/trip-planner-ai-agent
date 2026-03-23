import math


def itinerary_to_map_data(itinerary, poi_lookup):
    """
    Convert itinerary + POI lookup into flat point and path data for mapping.
    """
    points = []
    day_paths = {}

    for day in itinerary.get("days", []):
        day_num = day.get("day")
        ordered_positions = []

        for block_name in ["morning", "afternoon", "evening"]:
            for item in day.get(block_name, []):
                poi_id = item.get("poi_id")
                poi = poi_lookup.get(poi_id)

                if not poi:
                    continue
                
                if poi.get("lat") is None or poi.get("lon") is None:
                    continue

                point = {
                    "poi_id": poi_id,
                    "name": item.get("name", poi.get("name", "Unknown")),
                    "category": item.get("category", poi.get("category", "")),
                    "lat": poi.get("lat"),
                    "lon": poi.get("lon"),
                    "day": day_num,
                    "block": block_name.title(),
                    "time": item.get("time", ""),
                    "why": item.get("why", "")
                }

                points.append(point)
                ordered_positions.append([poi.get("lon"), poi.get("lat")])

        if ordered_positions:
            day_paths[day_num] = ordered_positions

    return points, day_paths


def build_path_data(day_paths, selected_day="All Days"):
    """
    Build PyDeck PathLayer data.
    """
    path_data = []

    if selected_day == "All Days":
        for day_num, path in day_paths.items():
            if len(path) >= 2:
                path_data.append({
                    "name": f"Day {day_num}",
                    "day": day_num,
                    "path": path
                })
    else:
        path = day_paths.get(selected_day, [])
        if len(path) >= 2:
            path_data.append({
                "name": f"Day {selected_day}",
                "day": selected_day,
                "path": path
            })

    return path_data


def filter_points_by_day(points, selected_day="All Days"):
    """
    Filter map points for either a single day or the full trip.
    """
    if selected_day == "All Days":
        return points
    return [point for point in points if point["day"] == selected_day]


def compute_view_state(points):
    """
    Compute a reasonable map center and zoom level from point spread.
    """
    if not points:
        return {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "zoom": 10,
            "pitch": 0
        }

    lats = [p["lat"] for p in points if p.get("lat") is not None]
    lons = [p["lon"] for p in points if p.get("lon") is not None]

    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    lat_range = max(lats) - min(lats) if len(lats) > 1 else 0.01
    lon_range = max(lons) - min(lons) if len(lons) > 1 else 0.01
    max_range = max(lat_range, lon_range)

    if max_range < 0.02:
        zoom = 13
    elif max_range < 0.05:
        zoom = 12
    elif max_range < 0.1:
        zoom = 11
    elif max_range < 0.3:
        zoom = 10
    elif max_range < 0.8:
        zoom = 9
    else:
        zoom = 8

    return {
        "latitude": center_lat,
        "longitude": center_lon,
        "zoom": zoom,
        "pitch": 35
    }