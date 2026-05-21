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


def lambda_handler(event, context):
    s3 = boto3.client("s3")
    timestamp = datetime.now(ZoneInfo("Asia/Singapore")).isoformat()

    # 1. Scrape the data
    response = requests.get(URL)
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

    return {"statusCode": 200, "body": f"Successfully appended {len(gyms)} rows to S3."}
