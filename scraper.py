import csv
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

url = "https://reboks.nus.edu.sg/nus_public_web/public/index.php/facilities/capacity"

CROWD_PATTERN = re.compile(r"^\s*(\d+)/(\d+)\s*$")
CSV_PATH = Path("gym_crowd.csv")
CSV_FIELDS = ["timestamp", "name", "current", "capacity"]


def parse_gym_crowdness(html: str, timestamp: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    gyms = []

    for box in soup.select("div.gymbox"):
        name = box.find("span")
        crowd = box.find("b")
        if not name or not crowd:
            continue

        match = CROWD_PATTERN.match(crowd.get_text())
        if not match:
            continue

        current, capacity = int(match.group(1)), int(match.group(2))
        gyms.append(
            {
                "timestamp": timestamp,
                "name": name.get_text(strip=True),
                "current": current,
                "capacity": capacity,
            }
        )

    return gyms


def append_gyms_to_csv(gyms: list[dict], path: Path = CSV_PATH) -> None:
    if not gyms:
        return

    file_exists = path.exists()
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(gyms)


if __name__ == "__main__":
    timestamp = datetime.now().isoformat()
    response = requests.get(url)
    gyms = parse_gym_crowdness(response.text, timestamp)
    append_gyms_to_csv(gyms)
    for gym in gyms:
        print(f"{gym['name']}: {gym['current']}/{gym['capacity']}")
