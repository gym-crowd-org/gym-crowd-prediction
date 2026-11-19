import csv
import io
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
import requests
from bs4 import BeautifulSoup

URL = "https://reboks.nus.edu.sg/nus_public_web/public/index.php/facilities/capacity"
CROWD_PATTERN = re.compile(r"^\s*(\d+)/(\d+)\s*$")

# Environment variables we will set in Lambda
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
S3_KEY = "gym_crowd.csv"

# Optional: when both are set, each run also writes its readings to Supabase
# (crowd_readings) so the app updates every run instead of waiting for the
# hourly CSV ingest. Failures here never fail the run; the CSV stays the source
# of truth and the hourly ingest fills any gaps.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


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
        gyms.append(
            {
                "timestamp": timestamp,
                "name": name.get_text(strip=True),
                "current": int(match.group(1)),
                "capacity": int(match.group(2)),
            }
        )
    return gyms


def write_readings_to_supabase(gyms: list[dict]) -> str:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return "Supabase not configured, skipped."

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/gyms",
            params={"select": "id,name", "is_active": "eq.true"},
            headers=headers,
            timeout=5,
        )
        resp.raise_for_status()
        gym_ids = {g["name"]: g["id"] for g in resp.json()}

        rows = [
            {
                "gym_id": gym_ids[g["name"]],
                "observed_at": g["timestamp"],
                "occupancy": g["current"],
                "capacity": g["capacity"],
            }
            for g in gyms
            if g["name"] in gym_ids and 0 <= g["current"] <= g["capacity"]
        ]
        if not rows:
            return "No matching gyms for Supabase."

        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/crowd_readings",
            params={"on_conflict": "gym_id,observed_at"},
            json=rows,
            headers={**headers, "Prefer": "resolution=ignore-duplicates,return=minimal"},
            timeout=5,
        )
        resp.raise_for_status()
        return f"Wrote {len(rows)} rows to Supabase."
    except Exception as exc:  # never fail the scrape because of Supabase
        print(f"Supabase write failed: {exc!r}")
        return "Supabase write failed."


def lambda_handler(event, context):
    s3 = boto3.client("s3")
    timestamp = datetime.now(ZoneInfo("Asia/Singapore")).isoformat()

    # 1. Scrape the data
    response = requests.get(URL, timeout=10)
    gyms = parse_gym_crowdness(response.text, timestamp)
    if not gyms:
        return {"statusCode": 200, "body": "No data scraped."}

    # 2. Check if CSV already exists in S3 to decide on headers
    existing_rows = []
    try:
        s3_obj = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        body = s3_obj["Body"].read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(body))
        existing_rows = list(reader)
    except s3.exceptions.NoSuchKey:
        pass  # File doesn't exist yet, we will write a new one

    # 3. Append new data in memory
    output = io.StringIO()
    fields = ["timestamp", "name", "current", "capacity"]
    writer = csv.DictWriter(output, fieldnames=fields)

    writer.writeheader()
    if existing_rows:
        writer.writerows(existing_rows)
    writer.writerows(gyms)

    # 4. Upload back to S3
    s3.put_object(Bucket=S3_BUCKET, Key=S3_KEY, Body=output.getvalue())

    # 5. Mirror the new readings into Supabase (best effort)
    supabase_result = write_readings_to_supabase(gyms)
    print(supabase_result)

    return {
        "statusCode": 200,
        "body": f"Successfully appended {len(gyms)} rows to S3. {supabase_result}",
    }
