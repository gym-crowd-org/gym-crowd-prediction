import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

url = "https://reboks.nus.edu.sg/nus_public_web/public/index.php/facilities/capacity"

CROWD_PATTERN = re.compile(r"^\s*(\d+)/(\d+)\s*$")


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
                "id": box.get("id"),
                "timestamp": timestamp,
                "name": name.get_text(strip=True),
                "current": current,
                "capacity": capacity,
                "crowdness": f"{current}/{capacity}",
            }
        )

    return gyms


if __name__ == "__main__":
    timestamp = datetime.now().isoformat()
    response = requests.get(url)
    gyms = parse_gym_crowdness(response.text, timestamp)
    for gym in gyms:
        print(f"{gym['name']}: {gym['crowdness']}")
