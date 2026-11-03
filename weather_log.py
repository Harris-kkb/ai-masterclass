
import os
import json
import requests

from datetime import datetime
from zoneinfo import ZoneInfo


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

CITY = "Karachi"
TIMEZONE = "Asia/Karachi"

GROQ_MODEL = "openai/gpt-oss-20b"

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


# --------------------------------------------------
# FETCH WEATHER DATA
# --------------------------------------------------

def get_weather():

    print(f"Fetching weather data for {CITY}...")

    params = {
        "latitude": 24.8607,
        "longitude": 67.0011,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "wind_speed_10m_max"
        ],
        "past_days": 5,
        "forecast_days": 1,
        "timezone": TIMEZONE
    }

    response = requests.get(
        WEATHER_URL,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()
    daily = data["daily"]

    # Keep the last five completed days
    today = datetime.now(ZoneInfo(TIMEZONE)).date()

    records = []

    for i, date_string in enumerate(daily["time"]):

        date = datetime.fromisoformat(date_string).date()

        if date >= today:
            continue

        records.append({
            "date": date_string,
            "max_temp": daily["temperature_2m_max"][i],
            "min_temp": daily["temperature_2m_min"][i],
            "wind": daily["wind_speed_10m_max"][i]
        })

    records = records[-5:]

    if not records:
        raise RuntimeError("No completed weather records returned.")

    avg_max = round(
        sum(r["max_temp"] for r in records) / len(records), 1
    )

    avg_min = round(
        sum(r["min_temp"] for r in records) / len(records), 1
    )

    peak_wind = round(
        max(r["wind"] for r in records), 1
    )

    period = (
        f"{records[0]['date']} to {records[-1]['date']}"
    )

    weather_summary = {
        "city": CITY,
        "period": period,
        "daily_records": records,
        "avg_max": avg_max,
        "avg_min": avg_min,
        "peak_wind": peak_wind
    }

    print("Weather data fetched successfully.")
    print(json.dumps(weather_summary, indent=2))

    return weather_summary


# --------------------------------------------------
# GROQ AI ANALYSIS
# --------------------------------------------------

def ask_groq(weather):

    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise SystemExit("Missing GROQ_API_KEY in GitHub Secrets.")

    print("Sending weather data to Groq for analysis...")

    prompt = f"""
You are a weather analyst.

Analyse the following recent weather data for Karachi, Pakistan.

WEATHER DATA:
{json.dumps(weather, indent=2)}

Return ONLY a valid JSON object with these exact fields:

{{
    "trend": "warming, cooling, or stable",
    "wind_risk": "low, medium, or high",
    "advice": "Practical advice based on the weather",
    "send_alert": true or false,
    "reason": "Brief explanation for the assessment"
}}

Instructions:
- Identify the overall temperature trend.
- Assess wind risk using the peak wind speed.
- Give practical advice relevant to Karachi.
- Set send_alert to true only when there is a meaningful
  weather concern that warrants an alert.
- Do not include Markdown or text outside the JSON.
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "response_format": {
            "type": "json_object"
        }
    }

    response = requests.post(
        GROQ_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    result = response.json()

    content = result["choices"][0]["message"]["content"]

    print("AI Analysis:", content)

    return get_json(content)


# --------------------------------------------------
# VALIDATE AI JSON
# --------------------------------------------------

def get_json(content):

    try:
        result = json.loads(content)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Groq returned invalid JSON: {error}"
        )

    required_fields = [
        "trend",
        "wind_risk",
        "advice",
        "send_alert",
        "reason"
    ]

    for field in required_fields:

        if field not in result:
            raise RuntimeError(
                f"Missing AI response field: {field}"
            )

    if not isinstance(result["send_alert"], bool):
        raise RuntimeError(
            "send_alert must be true or false."
        )

    return result


# --------------------------------------------------
# UPDATE BOTH GOOGLE SHEETS
# --------------------------------------------------

def update_google_sheets(payload):

    sheet_1 = os.environ.get("SHEET_URL")
    sheet_2 = os.environ.get("SHEET_URL_2")

    active_urls = [
        url.strip()
        for url in [sheet_1, sheet_2]
        if url and url.strip()
    ]

    if not active_urls:
        raise SystemExit("No Google Sheet URLs configured.")

    successful_updates = 0

    for index, sheet_url in enumerate(active_urls, start=1):

        try:

            print(f"Updating Google Sheet {index}...")

            response = requests.post(
                sheet_url,
                json=payload,
                timeout=60
            )

            print(
                f"Sheet {index} response: "
                f"{response.status_code} - {response.text}"
            )

            response.raise_for_status()

            if response.text.strip() != "OK":
                raise RuntimeError(
                    f"Unexpected response from Sheet {index}: "
                    f"{response.text}"
                )

            successful_updates += 1

        except Exception as error:

            raise SystemExit(
                f"Google Sheet {index} update failed: {error}"
            )

    print(
        f"Successfully updated "
        f"{successful_updates} Google Sheet(s)."
    )


# --------------------------------------------------
# MAIN JOB
# --------------------------------------------------

def run_job(dry=False):

    print(f"Starting weather job for {CITY}...")

    weather = get_weather()

    analysis = ask_groq(weather)

    payload = {
        "city": CITY,
        "period": weather["period"],
        "avg_max": weather["avg_max"],
        "avg_min": weather["avg_min"],
        "peak_wind": weather["peak_wind"],
        "trend": analysis["trend"],
        "wind_risk": analysis["wind_risk"],
        "advice": analysis["advice"],
        "send_alert": analysis["send_alert"],
        "reason": analysis["reason"]
    }

    print(
        "Final Payload:",
        json.dumps(payload, indent=2)
    )

    if dry:
        print("Dry run enabled. Sheets will not be updated.")
        return

    update_google_sheets(payload)

    print("Google Apps Script handles the email delivery.")

    print("Weather job completed successfully.")


# --------------------------------------------------
# EXECUTION ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":

    print("Weather logger script started.")

    run_job()

