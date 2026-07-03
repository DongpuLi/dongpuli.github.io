from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup

URL = "https://novascotia.ca/burnsafe/"
DEFAULT_COUNTY_ID = "Halifax-County"


def classify_level(class_name: str, text: str) -> str:
    c = (class_name or "").lower()
    t = (text or "").lower()

    # Yellow must be checked before red because the phrase contains "allowed".
    if "status-restricted" in c:
        return "yellow"

    if "burning is only allowed" in t:
        return "yellow"

    if "7:00 pm" in t or "7 p.m." in t:
        return "yellow"

    if "status-burn" in c and "status-no-burn" not in c:
        return "green"

    if "burning is allowed" in t and "only allowed" not in t:
        return "green"

    if "status-no-burn" in c:
        return "red"

    if "burning is not allowed" in t:
        return "red"

    return "unknown"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def fetch_all_counties() -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 HalifaxBurnTracker/2.5",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-CA,en;q=0.9",
    }

    response = requests.get(URL, headers=headers, timeout=60)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    updated_text = ""
    updated_match = soup.get_text(" ", strip=True)
    match = re.search(r"Last updated:\s*([0-9]{2} [A-Za-z]+ [0-9]{4} at [0-9]{1,2}:[0-9]{2} [ap]m)", updated_match)
    if match:
        updated_text = match.group(1)

    counties = []

    table = soup.find("table", id="restriction-table")
    if not table:
        raise RuntimeError("Unable to find restriction-table on BurnSafe page.")

    for row in table.find_all("tr"):
        county_id = row.get("id")
        cells = row.find_all(["th", "td"])

        if not county_id or len(cells) < 2:
            continue

        county_name = clean_text(cells[0].get_text(" ", strip=True))
        status_cell = cells[1]
        status_text = clean_text(status_cell.get_text(" ", strip=True))
        status_class = " ".join(status_cell.get("class", []))

        level = classify_level(status_class, status_text)

        counties.append({
            "id": county_id,
            "name": county_name,
            "level": level,
            "status": status_text,
            "source": URL,
        })

    if not counties:
        raise RuntimeError("No counties parsed from BurnSafe page.")

    return {
        "source": URL,
        "updated_text": updated_text,
        "counties": counties,
    }


def fetch_status(county_id: str = DEFAULT_COUNTY_ID) -> dict:
    data = fetch_all_counties()

    for county in data["counties"]:
        if county["id"] == county_id:
            return {
                "county_id": county["id"],
                "county": county["name"],
                "level": county["level"],
                "status": county["status"],
                "source": data["source"],
                "updated_text": data["updated_text"],
            }

    raise RuntimeError(f"County not found: {county_id}")


if __name__ == "__main__":
    data = fetch_all_counties()
    for county in data["counties"]:
        print(county)