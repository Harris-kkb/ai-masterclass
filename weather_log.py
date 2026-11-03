
import os
import sys
import json
import requests

# ---------- Settings ----------

CITY = "Karachi"

CITIES = {
    "Lahore": (31.52, 74.32),
    "Karachi": (24.86, 67.01),
    "Islamabad": (33.69, 73.05),
}

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"


# ---------- 1. Get weather data ----------

def get_weather(city):

    if city not in CITIES:
        raise ValueError(f"Unsupported city: {city}")

    lat, lon = CITIES[city]

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&daily=temperature_2m_max,temperature_2m_min,wind_speed_10m_max"
        "&timezone=auto&past_days=5&forecast_days=1"
    )

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    daily = response.json()["daily"]

    days = []

    for i in range(5):
        days.append({
            "date": daily["time"][i],
            "high": daily["temperature_2m_max"][i],
            "low": daily["temperature_2m_min"][i],
            "wind": daily["wind_speed_10m_max"][i],
        })

    if any(
        x["high"] is None or x["low"] is None or x["wind"] is None
        for x in days
    ):
        raise ValueError("Weather API returned incomplete data")

    return {
        "city": city,
        "days": days,
        "avg_high": round(sum(x["high"] for x in days) / 5, 1),
        "avg_low": round(sum(x["low"] for x in days) / 5, 1),
        "peak_wind": max(x["wind"] for x in days),
    }


# ---------- 2. Talk to Groq ----------

def ask_groq(messages, **extra):

    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise SystemExit("Missing GROQ_API_KEY in GitHub Secrets")

    response = requests.post(
        GROQ_URL,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": messages,
            **extra,
        },
        timeout=60,
    )

    if response.status_code != 200:
        raise SystemExit("Groq API error: " + response.text)

    return response.json()["choices"][0]["message"]


def get_json(prompt, keys):

    for attempt in range(2):

        result = ask_groq(
            [
                {
                    "role": "system",
                    "content": "Reply with valid JSON only. No markdown."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        text = result["content"].strip()

        try:
            data = json.loads(text)

        except json.JSONDecodeError:
            print("Invalid JSON returned by Groq. Retrying...")
            continue

        if (
            isinstance(data, dict)
            and all(k in data for k in keys)
            and data["trend"] in ["warming", "cooling", "steady"]
            and data["wind_risk"] in ["low", "medium", "high"]
            and isinstance(data["advice"], str)
            and isinstance(data["reason"], str)
            and isinstance(data["send_alert"], bool)
        ):
            return data

        print("Groq response missing required fields or has invalid values.")

    raise SystemExit("Groq did not return valid weather analysis")


# ---------- 3. Update Google Sheets ----------

def update_google_sheets(payload):

    sheet_1 = os.environ.get("SHEET_URL")
    sheet_2 = os.environ.get("SHEET_URL_2")
    sheet_key = os.environ.get("SHEET_KEY")

    if not sheet_key:
        raise SystemExit("Missing SHEET_KEY in GitHub Secrets")

    active_urls = [
        url.strip()
        for url in [sheet_1, sheet_2]
        if url and url.strip()
    ]

    if not active_urls:
        raise SystemExit("No Google Sheet URLs configured")

    successful_updates = 0

    for index, sheet_url in enumerate(active_urls, start=1):

        try:
            response = requests.post(
                sheet_url,
                params={"key": sheet_key},
                json=payload,
                timeout=60,
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


# ---------- 4. Daily weather job ----------

def run_job(dry=False):

    print(f"Starting weather job for {CITY}...")

    data = get_weather(CITY)

    table = "\n".join(
        f"{x['date']}: high {x['high']}C, "
        f"low {x['low']}C, max wind {x['wind']} km/h"
        for x in data["days"]
    )

    prompt = (
        f"Weather for {CITY}, last 5 completed days:\n"
        f"{table}\n\n"
        "Return JSON with exactly these keys: "
        "trend (warming, cooling or steady), "
        "wind_risk (low, medium or high), "
        "advice (one sentence), "
        "send_alert (true only if something unusual needs attention, "
        "otherwise false), "
        "reason (one sentence). "
        "Use only the numbers above. Do not invent anything. "
        "Base the trend on the temperature data and wind risk "
        "on the maximum wind data."
    )

    result = get_json(
        prompt,
        [
            "trend",
            "wind_risk",
            "advice",
            "send_alert",
            "reason",
        ],
    )

    print("AI Analysis:", json.dumps(result, indent=2))

    payload = {
        "city": CITY,
        "period": (
            data["days"][0]["date"]
            + " to "
            + data["days"][-1]["date"]
        ),
        "avg_max": data["avg_high"],
        "avg_min": data["avg_low"],
        "peak_wind": data["peak_wind"],
        "trend": result["trend"],
        "wind_risk": result["wind_risk"],
        "advice": result["advice"],
        "send_alert": result["send_alert"],
        "reason": result["reason"],
    }

    print("\nFinal Payload:")
    print(json.dumps(payload, indent=2))

    if dry:
        print("\nDry run completed. No Google Sheets updated.")
        return

    update_google_sheets(payload)

    print("\nWeather job completed successfully.")
    print("Google Apps Script handles the email delivery.")


# ---------- Start here ----------

if __name__ == "__main__":

    mode = sys.argv[1] if len(sys.argv) > 1 else "job"

    try:
        if mode == "dry":
            run_job(dry=True)
        else:
            run_job()

    except Exception as error:
        print(f"\nJOB FAILED: {error}")
        sys.exit(1)
