from __future__ import annotations

from collections import Counter


LABELS = ["green", "yellow", "red"]


def weather_features(weather: dict) -> dict:
    return {
        "temperature_max_c": float(weather.get("temperature_max_c") or 0),
        "humidity_mean_percent": float(weather.get("humidity_mean_percent") or 0),
        "precipitation_mm": float(weather.get("precipitation_mm") or 0),
        "wind_max_kmh": float(weather.get("wind_max_kmh") or 0),
        "wind_gust_max_kmh": float(weather.get("wind_gust_max_kmh") or 0),
        "dry_streak_days": float(weather.get("dry_streak_days") or 0),
    }


def rule_based_predict(weather: dict) -> dict:
    temp = float(weather.get("temperature_max_c") or 0)
    humidity = float(weather.get("humidity_mean_percent") or 100)
    rain = float(weather.get("precipitation_mm") or 0)
    wind = float(weather.get("wind_max_kmh") or 0)
    gust = float(weather.get("wind_gust_max_kmh") or 0)
    dry_days = float(weather.get("dry_streak_days") or 0)

    score = 0
    reasons = []

    if temp >= 28:
        score += 2
        reasons.append("hot day")
    elif temp >= 23:
        score += 1
        reasons.append("warm day")

    if humidity <= 35:
        score += 2
        reasons.append("low humidity")
    elif humidity <= 45:
        score += 1
        reasons.append("moderately low humidity")

    if rain < 0.5:
        score += 1
        reasons.append("little or no rain")
    elif rain >= 3:
        score -= 2
        reasons.append("meaningful rain expected")

    if wind >= 30:
        score += 2
        reasons.append("strong wind")
    elif wind >= 20:
        score += 1
        reasons.append("moderate wind")

    if gust >= 45:
        score += 2
        reasons.append("high wind gusts")

    if dry_days >= 5:
        score += 2
        reasons.append("several dry days")
    elif dry_days >= 3:
        score += 1
        reasons.append("short dry spell")

    if score >= 6:
        level = "red"
        confidence = min(90, 60 + score * 4)
    elif score >= 3:
        level = "yellow"
        confidence = min(85, 55 + score * 5)
    else:
        level = "green"
        confidence = max(55, 75 - score * 3)

    return {
        "level": level,
        "confidence": round(confidence),
        "model": "rule",
        "score": score,
        "reason": ", ".join(reasons) if reasons else "low fire-risk weather pattern",
    }


def distance(a: dict, b: dict) -> float:
    scales = {
        "temperature_max_c": 15,
        "humidity_mean_percent": 40,
        "precipitation_mm": 10,
        "wind_max_kmh": 30,
        "wind_gust_max_kmh": 50,
        "dry_streak_days": 7,
    }

    total = 0.0

    for key, scale in scales.items():
        total += ((float(a.get(key, 0)) - float(b.get(key, 0))) / scale) ** 2

    return total ** 0.5


def knn_predict(weather: dict, learning: list[dict]) -> dict | None:
    examples = [
        item for item in learning
        if item.get("actual") in LABELS and isinstance(item.get("weather"), dict)
    ]

    if len(examples) < 20:
        return None

    current = weather_features(weather)

    ranked = sorted(
        examples,
        key=lambda item: distance(current, weather_features(item["weather"]))
    )

    nearest = ranked[:7]
    votes = Counter(item["actual"] for item in nearest)
    level, count = votes.most_common(1)[0]

    confidence = round(50 + (count / len(nearest)) * 45)

    return {
        "level": level,
        "confidence": confidence,
        "model": "knn",
        "score": None,
        "reason": f"machine-learning prediction based on {len(examples)} past evaluated examples",
    }


def add_dry_streak(weather_records: list[dict]) -> list[dict]:
    dry_streak = 0
    output = []

    for item in weather_records:
        record = dict(item)
        rain = float(record.get("precipitation_mm") or 0)

        if rain < 0.5:
            dry_streak += 1
        else:
            dry_streak = 0

        record["dry_streak_days"] = dry_streak
        output.append(record)

    return output


def predict_many(weather_records: list[dict], learning: list[dict]) -> list[dict]:
    weather_records = add_dry_streak(weather_records)

    predictions = []

    for i, weather in enumerate(weather_records):
        ml = knn_predict(weather, learning)
        rule = rule_based_predict(weather)

        result = ml or rule

        predictions.append({
            "date": weather["date"],
            "horizon_days": i,
            "predicted_level": result["level"],
            "confidence": result["confidence"],
            "model": result["model"],
            "score": result["score"],
            "reason": result["reason"],
            "weather": weather,
        })

    return predictions