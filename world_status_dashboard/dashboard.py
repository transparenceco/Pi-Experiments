#!/usr/bin/env python3
import curses
import datetime as dt
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from zoneinfo import ZoneInfo


LAT = 43.65107
LON = -79.347015
TIMEZONE = "America/Toronto"

BASE_DIR = os.path.dirname(__file__)
CACHE_DIR = os.path.join(BASE_DIR, ".cache")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
WEATHER_TTL_SECONDS = 1800
NEWS_TTL_SECONDS = 1800

XAI_API_KEY = os.environ.get("XAI_API_KEY", "").strip()
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4-1-fast").strip()
X_SEARCH_QUERY = os.environ.get(
    "X_SEARCH_QUERY", "Toronto news OR Canada news"
).strip()
X_MAX_RESULTS = int(os.environ.get("X_MAX_RESULTS", "6"))


WEATHER_CODES = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm w/ slight hail",
    99: "Thunderstorm w/ heavy hail",
}


def fetch_json(url, headers=None, timeout=6):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            pass
        detail = f"{exc} {body}".strip()
        raise RuntimeError(detail) from exc


def cache_path(name):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)


def read_cache(name, ttl_seconds):
    path = cache_path(name)
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    age = time.time() - st.st_mtime
    if age > ttl_seconds:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def write_cache(name, data):
    path = cache_path(name)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(data):
    tmp = f"{CONFIG_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, CONFIG_PATH)


def ensure_xai_api_key():
    global XAI_API_KEY
    if XAI_API_KEY:
        return

    config = load_config()
    token = str(config.get("xai_api_key", "")).strip()
    if token:
        XAI_API_KEY = token
        return

    print("xAI API key not found.")
    token = input("Enter XAI API key (will be saved to config.json): ").strip()
    if not token:
        return

    config["xai_api_key"] = token
    save_config(config)
    XAI_API_KEY = token


def get_weather():
    cached = read_cache("weather.json", WEATHER_TTL_SECONDS)
    if cached:
        return cached

    params = {
        "latitude": LAT,
        "longitude": LON,
        "current_weather": "true",
        "hourly": "apparent_temperature,relativehumidity_2m",
        "timezone": TIMEZONE,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    data = fetch_json(url)
    write_cache("weather.json", data)
    return data


def get_news():
    cached = read_cache("news.json", NEWS_TTL_SECONDS)
    if cached:
        return cached

    if not XAI_API_KEY:
        return {"error": "Missing XAI_API_KEY"}

    try:
        from xai_sdk import Client
        from xai_sdk.chat import user
        from xai_sdk.tools import x_search
    except Exception:
        return {"error": "Missing dependency: xai-sdk (pip install xai-sdk==1.3.1)"}

    prompt = (
        "Search X for recent posts about: "
        f"{X_SEARCH_QUERY}. Return a JSON array with up to {X_MAX_RESULTS} items. "
        "Each item must include: text, author_handle, created_at, url. "
        "If a field is unknown, use an empty string. Return only JSON."
    )

    try:
        client = Client(api_key=XAI_API_KEY)
        chat = client.chat.create(model=XAI_MODEL, tools=[x_search()])
        chat.append(user(prompt))
        response = chat.sample()
        content = response.content or ""
    except Exception as exc:
        return {"error": str(exc)}

    try:
        items = json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Invalid response from xAI search", "raw": content}

    data = {"items": items}
    write_cache("news.json", data)
    return data


def parse_weather(data):
    current = data.get("current_weather", {})
    temp = current.get("temperature")
    wind = current.get("windspeed")
    wind_dir = current.get("winddirection")
    code = current.get("weathercode")
    desc = WEATHER_CODES.get(code, "Unknown")

    hourly = data.get("hourly", {})
    apparent = None
    humidity = None
    times = hourly.get("time", [])
    if times:
        now = current.get("time")
        if now in times:
            idx = times.index(now)
            app = hourly.get("apparent_temperature", [])
            rh = hourly.get("relativehumidity_2m", [])
            if idx < len(app):
                apparent = app[idx]
            if idx < len(rh):
                humidity = rh[idx]

    return {
        "temp": temp,
        "apparent": apparent,
        "humidity": humidity,
        "wind": wind,
        "wind_dir": wind_dir,
        "desc": desc,
    }


def parse_news(data):
    if "error" in data:
        return {"error": data["error"], "items": [], "raw": data.get("raw", "")}

    items = []
    for item in data.get("items", []) or []:
        items.append(
            {
                "text": str(item.get("text", "")),
                "time": str(item.get("created_at", "")),
                "user": str(item.get("author_handle", "unknown")),
                "url": str(item.get("url", "")),
            }
        )
    return {"error": None, "items": items, "raw": ""}


def fmt_temp(value):
    return f"{value:.1f}C" if value is not None else "N/A"


def fmt_wind_dir(deg):
    if deg is None:
        return "N/A"
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((deg + 22.5) / 45.0) % 8
    return f"{deg:.0f}deg {dirs[idx]}"


def fmt_time(ts):
    if not ts:
        return ""
    try:
        t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return t.astimezone(ZoneInfo(TIMEZONE)).strftime("%H:%M")
    except ValueError:
        return ts


def safe_addstr(stdscr, y, x, text):
    try:
        stdscr.addstr(y, x, text)
    except curses.error:
        pass


def draw(stdscr, weather, news, now):
    stdscr.erase()
    height, width = stdscr.getmaxyx()

    title = "World Status - Toronto"
    clock = now.strftime("%A, %B %d %Y %H:%M:%S")
    safe_addstr(stdscr, 0, 0, title[: width - 1])
    safe_addstr(stdscr, 1, 0, clock[: width - 1])

    safe_addstr(stdscr, 3, 0, "Weather")
    if weather.get("error"):
        safe_addstr(stdscr, 4, 0, f"  Error: {weather['error']}")
    else:
        w = parse_weather(weather)
        safe_addstr(
            stdscr,
            4,
            0,
            f"  {w['desc']}  Temp {fmt_temp(w['temp'])} (Feels {fmt_temp(w['apparent'])})",
        )
        safe_addstr(
            stdscr,
            5,
            0,
            f"  Humidity {w['humidity'] if w['humidity'] is not None else 'N/A'}%  "
            f"Wind {w['wind'] if w['wind'] is not None else 'N/A'} km/h {fmt_wind_dir(w['wind_dir'])}",
        )

    safe_addstr(stdscr, 7, 0, f"News - X search: {X_SEARCH_QUERY}"[: width - 1])
    n = parse_news(news)
    if n["error"]:
        safe_addstr(stdscr, 8, 0, f"  Error: {n['error']}"[: width - 1])
        if n.get("raw"):
            safe_addstr(stdscr, 9, 0, f"  Raw: {n['raw']}"[: width - 1])
    elif not n["items"]:
        safe_addstr(stdscr, 8, 0, "  No results")
    else:
        y = 8
        for item in n["items"]:
            if y >= height - 1:
                break
            line = f"  @{item['user']} {fmt_time(item['time'])} - {item['text']}"
            safe_addstr(stdscr, y, 0, line[: width - 1])
            y += 1

    safe_addstr(stdscr, height - 1, 0, "Press q to quit")
    stdscr.refresh()


def dashboard(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)

    weather = {}
    news = {}
    last_weather_fetch = 0.0
    last_news_fetch = 0.0

    while True:
        now = dt.datetime.now(ZoneInfo(TIMEZONE))
        now_ts = time.time()

        if now_ts - last_weather_fetch > WEATHER_TTL_SECONDS or not weather:
            try:
                weather = get_weather()
            except Exception as exc:
                weather = {"error": str(exc)}
            last_weather_fetch = now_ts

        if now_ts - last_news_fetch > NEWS_TTL_SECONDS or not news:
            try:
                news = get_news()
            except Exception as exc:
                news = {"error": str(exc)}
            last_news_fetch = now_ts

        draw(stdscr, weather, news, now)

        try:
            key = stdscr.getkey()
        except curses.error:
            key = None
        if key in ("q", "Q"):
            break

        time.sleep(1)


def main():
    ensure_xai_api_key()
    curses.wrapper(dashboard)


if __name__ == "__main__":
    main()
