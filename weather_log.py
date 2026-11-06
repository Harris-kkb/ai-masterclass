
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

# ---------- 5. The weather agent: the AI decides what to check and whether to alert ----------
from time import sleep
 
MAX_STEPS = 6   # the agent must finish within this many steps
 
 
def tool_get_weather(city):
    if city not in CITIES:
        return {"error": "city not allowed"}
    data = get_weather(city)
    summary = {k: v for k, v in data.items() if k != "days"}
    summary["daily_highs"] = [x["high"] for x in data["days"]]
    return summary
 
 
def tool_get_history(n=5):
    # Reads the agent's own recent decisions from your Google Sheet (Agent tab)
    r = requests.get(os.environ["SHEET_URL"], params={"action": "history", "n": n}, timeout=30)
    try:
        return r.json()
    except ValueError:
        return {"error": "could not read history: " + r.text[:100]}
 
 
REAL_TOOLS = {"get_weather": tool_get_weather, "get_history": tool_get_history}
 
AGENT_TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "Get the last 5 days of weather for a city: average high, average low, peak wind and the daily highs",
        "parameters": {"type": "object",
                       "properties": {"city": {"type": "string", "enum": list(CITIES)}},
                       "required": ["city"]}}},
    {"type": "function", "function": {
        "name": "get_history",
        "description": "Get your own most recent decisions from previous runs: time, city, advice, whether an alert was sent, and the alert message",
        "parameters": {"type": "object",
                       "properties": {"n": {"type": "integer", "description": "how many past runs, 1 to 10"}}}}},
]
 
 
def parse_decision(text):
    text = (text or "").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        d = json.loads(text)
    except json.JSONDecodeError:
        return None
    ok = (isinstance(d, dict) and isinstance(d.get("advice"), str) and isinstance(d.get("reasoning"), str)
          and isinstance(d.get("send_alert"), bool) and isinstance(d.get("alert_message"), str))
    return d if ok else None
 
 
def apply_guardrails(d):
    # The AI recommends. Your code decides what is allowed.
    message = d["alert_message"].strip()[:300]            # a short alert only
    send = d["send_alert"] is True and message != ""      # no alert without a message
    return {"advice": d["advice"].strip(), "reasoning": d["reasoning"].strip(),
            "send_alert": send, "alert_message": message if send else ""}
 
 
def run_weather_agent(tools=REAL_TOOLS, max_steps=MAX_STEPS):
    system = (
        f"You are a weather agent for {CITY}. Use your tools to check the weather and your own recent decisions. "
        "Compare today with the recent days and with your past alerts. "
        "Send an alert only if something unusual or dangerous needs attention, such as extreme heat, "
        "strong wind or a big change, and only if the history does not show you already alerted about the same thing. "
        "Never invent numbers. If a tool returns an error, do not guess: say the data is unavailable and do not alert. "
        "When you are done, reply with JSON only, with exactly these keys: "
        "advice (one or two sentences for a general reader), "
        "reasoning (two or three sentences explaining your decision with numbers), "
        "send_alert (true or false), "
        "alert_message (a short message, or an empty string if there is no alert)."
    )
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"Check the weather for {CITY} and decide what to do."}]
    used = []
    for step in range(1, max_steps + 1):
        msg = ask_groq(messages, tools=AGENT_TOOLS, temperature=0.2)
        calls = msg.get("tool_calls")
        if not calls:
            decision = parse_decision(msg.get("content"))
            if decision:
                return decision, used
            messages.append({"role": "assistant", "content": msg.get("content") or ""})
            messages.append({"role": "user", "content": "Reply with the JSON object only, with the 4 keys."})
            continue
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for call in calls:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"] or "{}")
            print("STEP", step, "->", name, args)
            fn = tools.get(name)
            if fn is None:
                result = {"error": "tool not allowed"}
            else:
                try:
                    result = fn(**args)
                except TypeError:
                    result = {"error": "bad arguments"}
            used.append(name)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
    raise SystemExit("The agent did not finish in time")
 
 
def run_agent_job(dry=False):
    decision, used = run_weather_agent()
    decision = apply_guardrails(decision)
    print("\nADVICE:", decision["advice"])
    print("REASONING:", decision["reasoning"])
    print("ALERT:", decision["send_alert"], decision["alert_message"])
 
    payload = {"type": "agent", "city": CITY, "tools_used": ", ".join(used), **decision}
    if dry:
        print("\nDry run. Nothing was sent to the sheet or email.")
        return
    response = requests.post(os.environ["SHEET_URL"], json=payload, timeout=30)
    print(response.status_code, response.text)
    if response.text != "OK":
        raise SystemExit("The sheet script said: " + response.text)
 
 
# ---------- 6. Tests: does the agent make the right decision? ----------
SCENARIOS = [
    {"name": "Normal day",
     "weather": {"city": CITY, "avg_high": 31.0, "avg_low": 21.0, "peak_wind": 12.0,
                 "daily_highs": [30, 31, 31, 32, 31]},
     "history": [], "expect_alert": False},
    {"name": "Heatwave",
     "weather": {"city": CITY, "avg_high": 43.0, "avg_low": 30.0, "peak_wind": 14.0,
                 "daily_highs": [38, 41, 43, 45, 48]},
     "history": [], "expect_alert": True},
    {"name": "Storm winds",
     "weather": {"city": CITY, "avg_high": 29.0, "avg_low": 22.0, "peak_wind": 75.0,
                 "daily_highs": [29, 28, 29, 30, 29]},
     "history": [], "expect_alert": True},
    {"name": "Same heatwave, already alerted",
     "weather": {"city": CITY, "avg_high": 44.0, "avg_low": 31.0, "peak_wind": 14.0,
                 "daily_highs": [44, 45, 44, 45, 46]},
     "history": [{"time": "yesterday", "city": CITY, "advice": "Extreme heat", "alert_sent": True,
                  "alert_message": "Heatwave: highs above 44 C. Stay indoors at midday."}],
     "expect_alert": False},
    {"name": "Weather service down",
     "weather": {"error": "service unavailable"},
     "history": [], "expect_alert": False},
]
 
 
def run_tests():
    passed = 0
    for s in SCENARIOS:
        tools = {"get_weather": lambda city, s=s: s["weather"],
                 "get_history": lambda n=5, s=s: s["history"]}
        decision = apply_guardrails(run_weather_agent(tools)[0])
        ok = decision["send_alert"] == s["expect_alert"]
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'} | {s['name']} | expected alert {s['expect_alert']}, "
              f"got {decision['send_alert']}")
        print("     ", decision["reasoning"])
        sleep(2)   # be gentle with the free limits
    print(f"\n{passed} of {len(SCENARIOS)} passed")
 
 
Now the new start section, at the very bottom of the file:
# ---------- Start here ----------
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "job"
    if mode == "ask":
        print(run_agent(" ".join(sys.argv[2:])))
    elif mode == "dry":
        run_job(dry=True)
    elif mode == "agent":
        run_agent_job()
    elif mode == "agent-dry":
        run_agent_job(dry=True)
    elif mode == "test":
        run_tests()
    else:
        run_job()


