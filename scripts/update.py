"""
Nova Scotia Burn Tracker updater v4.0

Generates:
- latest.json
- counties.json
- weather.json
- county_weather.json
- prediction.json
- county_prediction.json
- history.json
- county_history.json
- metrics.json
- county_metrics.json
- learning.json
- county_learning.json
- predictions_archive.json
- county_predictions_archive.json
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement
from zoneinfo import ZoneInfo

from burnsafe import fetch_all_counties
from fire_weather import ensure_fire_weather_files, update_fire_weather_files
from predictor import predict_many
from weather import fetch_all_county_weather, fetch_weather_forecast


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

DATA_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

TIMEZONE = ZoneInfo("America/Halifax")
POSTING_HOUR = 14
DEFAULT_COUNTY_ID = "Halifax-County"

BURN_SEASON_START = (3, 15)
BURN_SEASON_END = (10, 15)


def save_json_to_both(filename: str, data) -> None:
    for directory in (DATA_DIR, DOCS_DIR):
        path = directory / filename
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)


def load_json(filename: str, default):
    path = DATA_DIR / filename

    if not path.exists() or path.stat().st_size == 0:
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return default


def normalize_level(level: str | None) -> str:
    value = (level or "unknown").strip().lower()

    if value in {"green", "yellow", "red"}:
        return value

    return "unknown"


def is_burn_season(now: datetime) -> bool:
    current = (now.month, now.day)
    return BURN_SEASON_START <= current <= BURN_SEASON_END


def update_county_history(
    county_history: dict,
    counties: list[dict],
    today: str,
    now: datetime,
) -> dict:
    """
    Insert or replace today's official BurnSafe record for every county.

    This function is idempotent: running it multiple times on the same day
    replaces the existing record instead of creating duplicates.
    """
    for county in counties:
        county_id = county["id"]

        record = {
            "date": today,
            "updated_at": now.isoformat(timespec="seconds"),
            "timezone": "America/Halifax",
            "county_id": county_id,
            "county": county.get("name", county_id),
            "level": normalize_level(county.get("level")),
            "status": county.get("status", ""),
            "source": county.get(
                "source",
                "https://novascotia.ca/burnsafe/",
            ),
        }

        history = county_history.get(county_id, [])

        history = [
            item
            for item in history
            if item.get("date") != today
        ]

        history.append(record)
        history.sort(key=lambda item: item.get("date", ""))

        county_history[county_id] = history

    return county_history


def latest_halifax_record(
    county_history: dict,
    previous_latest: dict | None,
):
    halifax_history = county_history.get(DEFAULT_COUNTY_ID, [])

    if halifax_history:
        return max(
            halifax_history,
            key=lambda item: item.get("date", ""),
        )

    return previous_latest


def build_actual_history_lookup(county_history: dict) -> dict:
    """
    Convert county history into:

    {
        county_id: {
            date: official_level
        }
    }
    """
    lookup = {}

    for county_id, records in county_history.items():
        lookup[county_id] = {}

        for record in records:
            date = record.get("date")
            level = normalize_level(record.get("level"))

            if date and level != "unknown":
                lookup[county_id][date] = level

    return lookup


def evaluate_county_predictions(
    county_archive: dict,
    county_learning: dict,
    county_history: dict,
    now: datetime,
) -> tuple[dict, dict]:
    """
    Evaluate every archived prediction whose target date now has an official
    BurnSafe history record.

    This is deliberately idempotent:

    - already evaluated archive records are skipped;
    - existing evaluation keys are not duplicated;
    - missed evaluations from previous runs are filled automatically.
    """
    actual_lookup = build_actual_history_lookup(county_history)

    for county_id, archive in county_archive.items():
        learning = county_learning.get(county_id, [])

        existing_keys = {
            item.get("evaluation_key")
            for item in learning
            if item.get("evaluation_key")
        }

        county_actuals = actual_lookup.get(county_id, {})

        for item in archive:
            target_date = item.get("target_date")

            if not target_date:
                continue

            actual = county_actuals.get(target_date)

            # No official record is available for this target date yet.
            if not actual:
                continue

            # Archive record has already been evaluated.
            if item.get("actual_level"):
                continue

            predicted = normalize_level(item.get("predicted_level"))
            horizon_days = item.get("horizon_days")

            correct = predicted == actual

            item["actual_level"] = actual
            item["correct"] = correct
            item["evaluated_at"] = now.isoformat(timespec="seconds")

            evaluation_key = (
                f"{county_id}:"
                f"{item.get('issued_date')}->{target_date}:"
                f"h{horizon_days}"
            )

            if evaluation_key in existing_keys:
                continue

            learning.append(
                {
                    "evaluation_key": evaluation_key,
                    "county_id": county_id,
                    "issued_date": item.get("issued_date"),
                    "target_date": target_date,
                    "horizon_days": horizon_days,
                    "predicted": predicted,
                    "actual": actual,
                    "correct": correct,
                    "confidence": item.get("confidence"),
                    "model": item.get("model"),
                    "reason": item.get("reason"),
                    "weather": item.get("weather"),
                }
            )

            existing_keys.add(evaluation_key)

        county_archive[county_id] = archive
        county_learning[county_id] = learning

    return county_archive, county_learning


def accuracy_block(items: list[dict]) -> dict:
    total = len(items)
    correct = sum(
        1
        for item in items
        if item.get("correct") is True
    )

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else None,
    }


def build_one_metrics(learning: list[dict]) -> dict:
    labels = ["green", "yellow", "red", "unknown"]

    evaluated = [
        item
        for item in learning
        if item.get("actual") and item.get("predicted")
    ]

    # Main public metric: one-day-ahead planning outlook.
    headline = [
        item
        for item in evaluated
        if item.get("horizon_days") == 1
    ]

    confusion_matrix = {
        actual: {
            predicted: 0
            for predicted in labels
        }
        for actual in labels
    }

    for item in evaluated:
        actual = normalize_level(item.get("actual"))
        predicted = normalize_level(item.get("predicted"))
        confusion_matrix[actual][predicted] += 1

    by_horizon = {}

    # Current predictor uses 0–6, but the public evaluation starts at
    # one-day-ahead, so metrics use horizons 1–6.
    for horizon in range(1, 7):
        horizon_items = [
            item
            for item in evaluated
            if item.get("horizon_days") == horizon
        ]

        by_horizon[str(horizon)] = accuracy_block(horizon_items)

    by_actual_level = {}

    for level in labels:
        level_items = [
            item
            for item in evaluated
            if normalize_level(item.get("actual")) == level
        ]

        by_actual_level[level] = accuracy_block(level_items)

    by_predicted_level = {}

    for level in labels:
        level_items = [
            item
            for item in evaluated
            if normalize_level(item.get("predicted")) == level
        ]

        by_predicted_level[level] = accuracy_block(level_items)

    headline_metrics = accuracy_block(headline)
    all_metrics = accuracy_block(evaluated)

    return {
        "version": "4.1",
        "primary_metric": "one_day_ahead",
        "total_evaluated": headline_metrics["total"],
        "correct": headline_metrics["correct"],
        "accuracy": headline_metrics["accuracy"],
        "all_evaluated": all_metrics,
        "by_horizon": by_horizon,
        "by_actual_level": by_actual_level,
        "by_predicted_level": by_predicted_level,
        "confusion_matrix": confusion_matrix,
        "updated_at": datetime.now(TIMEZONE).isoformat(
            timespec="seconds"
        ),
    }


def build_county_metrics(
    county_learning: dict,
    counties: list[dict],
) -> dict:
    return {
        county["id"]: build_one_metrics(
            county_learning.get(county["id"], [])
        )
        for county in counties
    }


def archive_county_predictions(
    today: str,
    now: datetime,
    counties: list[dict],
    predictions_by_county: dict,
    county_archive: dict,
) -> dict:
    """
    Archive today's complete outlook once per county and target date.

    Existing issued_date -> target_date pairs are not duplicated.
    """
    for county in counties:
        county_id = county["id"]
        archive = county_archive.get(county_id, [])

        existing_keys = {
            (
                item.get("issued_date"),
                item.get("target_date"),
            )
            for item in archive
        }

        for item in predictions_by_county.get(county_id, []):
            key = (today, item["date"])

            if key in existing_keys:
                continue

            archive.append(
                {
                    "issued_date": today,
                    "issued_at": now.isoformat(timespec="seconds"),
                    "county_id": county_id,
                    "target_date": item["date"],
                    "horizon_days": item["horizon_days"],
                    "predicted_level": item["predicted_level"],
                    "confidence": item["confidence"],
                    "model": item["model"],
                    "score": item["score"],
                    "reason": item["reason"],
                    "weather": item["weather"],
                    "actual_level": None,
                    "correct": None,
                    "evaluated_at": None,
                }
            )

            existing_keys.add(key)

        archive.sort(
            key=lambda item: (
                item.get("target_date", ""),
                item.get("issued_date", ""),
            )
        )

        county_archive[county_id] = archive

    return county_archive

SITE_URL = "https://dongpuli.github.io"

def write_sitemap(today: str) -> None:
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{SITE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
"""

    for directory in (DATA_DIR, DOCS_DIR):
        with open(
            directory / "sitemap.xml",
            "w",
            encoding="utf-8",
        ) as file:
            file.write(sitemap)

def main() -> None:
    now = datetime.now(TIMEZONE)
    today = now.date().isoformat()

    ensure_fire_weather_files()
    fire_weather_forecast, fire_weather_actuals = (
        update_fire_weather_files()
    )

    in_burn_season = is_burn_season(now)

    previous_latest = load_json("latest.json", None)

    county_history = load_json("county_history.json", {})
    county_archive = load_json(
        "county_predictions_archive.json",
        {},
    )
    county_learning = load_json("county_learning.json", {})

    if not in_burn_season:
        latest = previous_latest or {
            "date": today,
            "updated_at": now.isoformat(timespec="seconds"),
            "timezone": "America/Halifax",
            "county_id": DEFAULT_COUNTY_ID,
            "county": "Halifax County",
            "level": "offseason",
            "status": (
                "Static archive mode. BurnSafe wildfire risk season "
                "runs from March 15 to October 15. Verify local "
                "municipal and provincial rules before burning."
            ),
            "source": "https://novascotia.ca/burnsafe/",
        }

        latest["site_mode"] = "offseason"
        latest["level"] = "offseason"
        latest["status"] = (
            "Static archive mode. BurnSafe wildfire risk season "
            "runs from March 15 to October 15. Verify local "
            "municipal and provincial rules before burning."
        )
        latest["updated_at"] = now.isoformat(timespec="seconds")
        latest["archive_season"] = str(now.year)

        save_json_to_both("latest.json", latest)

        print("Outside burn season.")
        print("Static archive mode enabled.")
        print("No BurnSafe/weather fetch performed.")
        return

    after_posting_time = now.hour >= POSTING_HOUR

    counties_data = fetch_all_counties()
    counties = counties_data.get("counties", [])

    counties_data["fetched_at"] = now.isoformat(timespec="seconds")
    counties_data["timezone"] = "America/Halifax"

    county_weather = fetch_all_county_weather()

    halifax_weather = county_weather.get(
        DEFAULT_COUNTY_ID,
        {},
    )

    weather_forecast = halifax_weather.get("forecast")

    if not weather_forecast:
        weather_forecast = fetch_weather_forecast(
            DEFAULT_COUNTY_ID
        )

    county_fire_weather = load_json(
        "county_fire_weather.json",
        {},
    )

    predictions_by_county = {}

    for county in counties:
        county_id = county["id"]

        weather_records = county_weather.get(
            county_id,
            {},
        ).get(
            "forecast",
            weather_forecast,
        )

        predictions_by_county[county_id] = predict_many(
            weather_records,
            county_learning.get(county_id, []),
            official_fire_weather=county_fire_weather.get(
                county_id
            ),
        )

    # Official BurnSafe records and today's outlook archive should only be
    # written after the official afternoon posting time.
    if after_posting_time:
        county_history = update_county_history(
            county_history=county_history,
            counties=counties,
            today=today,
            now=now,
        )

        county_archive = archive_county_predictions(
            today=today,
            now=now,
            counties=counties,
            predictions_by_county=predictions_by_county,
            county_archive=county_archive,
        )

        halifax = next(
            (
                county
                for county in counties
                if county.get("id") == DEFAULT_COUNTY_ID
            ),
            {},
        )

        latest = {
            "date": today,
            "updated_at": now.isoformat(timespec="seconds"),
            "timezone": "America/Halifax",
            "site_mode": "active",
            "county_id": halifax.get(
                "id",
                DEFAULT_COUNTY_ID,
            ),
            "county": halifax.get(
                "name",
                "Halifax County",
            ),
            "level": normalize_level(
                halifax.get("level")
            ),
            "status": halifax.get("status", ""),
            "source": halifax.get(
                "source",
                "https://novascotia.ca/burnsafe/",
            ),
            "official_updated_text": counties_data.get(
                "updated_text",
                "",
            ),
        }

    else:
        latest = latest_halifax_record(
            county_history,
            previous_latest,
        ) or {
            "date": today,
            "updated_at": now.isoformat(timespec="seconds"),
            "timezone": "America/Halifax",
            "site_mode": "active",
            "county_id": DEFAULT_COUNTY_ID,
            "county": "Halifax County",
            "level": "red",
            "status": "Burning is not allowed.",
            "source": "https://novascotia.ca/burnsafe/",
            "pre_2pm_display": True,
        }

        latest["site_mode"] = "active"

    # Always run evaluation after the possible history update.
    #
    # This allows the script to:
    # - evaluate today's records after 2 p.m.;
    # - repair missed evaluations from previous dates;
    # - remain safe when the workflow runs more than once.
    county_archive, county_learning = evaluate_county_predictions(
        county_archive=county_archive,
        county_learning=county_learning,
        county_history=county_history,
        now=now,
    )

    county_metrics = build_county_metrics(
        county_learning,
        counties,
    )

    save_json_to_both("latest.json", latest)

    save_json_to_both(
        "history.json",
        county_history.get(DEFAULT_COUNTY_ID, []),
    )

    save_json_to_both(
        "weather.json",
        weather_forecast,
    )

    save_json_to_both(
        "prediction.json",
        predictions_by_county.get(
            DEFAULT_COUNTY_ID,
            [],
        ),
    )

    save_json_to_both(
        "predictions_archive.json",
        county_archive.get(
            DEFAULT_COUNTY_ID,
            [],
        ),
    )

    save_json_to_both(
        "learning.json",
        county_learning.get(
            DEFAULT_COUNTY_ID,
            [],
        ),
    )

    save_json_to_both(
        "metrics.json",
        county_metrics.get(
            DEFAULT_COUNTY_ID,
            build_one_metrics([]),
        ),
    )

    save_json_to_both(
        "counties.json",
        counties_data,
    )

    save_json_to_both(
        "county_weather.json",
        county_weather,
    )

    save_json_to_both(
        "county_history.json",
        county_history,
    )

    save_json_to_both(
        "county_prediction.json",
        predictions_by_county,
    )

    save_json_to_both(
        "county_predictions_archive.json",
        county_archive,
    )

    save_json_to_both(
        "county_learning.json",
        county_learning,
    )

    save_json_to_both(
        "county_metrics.json",
        county_metrics,
    )

    write_sitemap(today)

    print("Updated.")
    print(f"Halifax time: {now.isoformat(timespec='seconds')}")
    print(f"Burn season active: {in_burn_season}")
    print(f"After 2 p.m. posting time: {now.hour >= POSTING_HOUR}")
    print(f"Parsed {len(counties)} counties.")
    print(f"Generated county weather for {len(county_weather)} counties.")
    print(f"Generated county predictions for {len(predictions_by_county)} counties.")
    print(f"Fire weather forecast stations: {len(fire_weather_forecast.get('stations', {}))}")
    print(f"Fire weather actuals stations: {len(fire_weather_actuals.get('stations', {}))}")
if __name__ == "__main__":
    main()