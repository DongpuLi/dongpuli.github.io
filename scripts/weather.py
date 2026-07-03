from __future__ import annotations

import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "America/Halifax"

COUNTY_COORDINATES = {
    "Annapolis-County": {"name": "Annapolis County", "latitude": 44.75, "longitude": -65.52},
    "Antigonish-County": {"name": "Antigonish County", "latitude": 45.62, "longitude": -61.99},
    "Cape-Breton-County": {"name": "Cape Breton County", "latitude": 46.14, "longitude": -60.19},
    "Colchester-County": {"name": "Colchester County", "latitude": 45.36, "longitude": -63.28},
    "Cumberland-County": {"name": "Cumberland County", "latitude": 45.83, "longitude": -64.21},
    "Digby-County": {"name": "Digby County", "latitude": 44.62, "longitude": -65.76},
    "Guysborough-County": {"name": "Guysborough County", "latitude": 45.39, "longitude": -61.50},
    "Halifax-County": {"name": "Halifax County", "latitude": 44.65, "longitude": -63.58},
    "Hants-County": {"name": "Hants County", "latitude": 44.99, "longitude": -64.13},
    "Inverness-County": {"name": "Inverness County", "latitude": 46.23, "longitude": -61.30},
    "Kings-County": {"name": "Kings County", "latitude": 45.07, "longitude": -64.50},
    "Lunenburg-County": {"name": "Lunenburg County", "latitude": 44.38, "longitude": -64.32},
    "Pictou-County": {"name": "Pictou County", "latitude": 45.59, "longitude": -62.65},
    "Queens-County": {"name": "Queens County", "latitude": 44.04, "longitude": -64.72},
    "Richmond-County": {"name": "Richmond County", "latitude": 45.62, "longitude": -61.00},
    "Shelburne-County": {"name": "Shelburne County", "latitude": 43.76, "longitude": -65.32},
    "Victoria-County": {"name": "Victoria County", "latitude": 46.10, "longitude": -60.75},
    "Yarmouth-County": {"name": "Yarmouth County", "latitude": 43.84, "longitude": -66.12},
}


def fetch_weather_forecast_for_coordinates(latitude: float, longitude: float) -> list[dict]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": TIMEZONE,
        "forecast_days": 7,
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "relative_humidity_2m_mean",
            "precipitation_sum",
            "rain_sum",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
        ]),
    }

    response = requests.get(OPEN_METEO_URL, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    daily = data["daily"]

    records = []

    for i, date in enumerate(daily["time"]):
        records.append({
            "date": date,
            "temperature_max_c": daily["temperature_2m_max"][i],
            "temperature_min_c": daily["temperature_2m_min"][i],
            "humidity_mean_percent": daily["relative_humidity_2m_mean"][i],
            "precipitation_mm": daily["precipitation_sum"][i],
            "rain_mm": daily["rain_sum"][i],
            "wind_max_kmh": daily["wind_speed_10m_max"][i],
            "wind_gust_max_kmh": daily["wind_gusts_10m_max"][i],
        })

    return records


def fetch_weather_forecast(county_id: str = "Halifax-County") -> list[dict]:
    county = COUNTY_COORDINATES[county_id]
    return fetch_weather_forecast_for_coordinates(
        county["latitude"],
        county["longitude"],
    )


def fetch_all_county_weather() -> dict:
    output = {}

    for county_id, county in COUNTY_COORDINATES.items():
        output[county_id] = {
            "county_id": county_id,
            "county": county["name"],
            "latitude": county["latitude"],
            "longitude": county["longitude"],
            "forecast": fetch_weather_forecast_for_coordinates(
                county["latitude"],
                county["longitude"],
            ),
        }

    return output