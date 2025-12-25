#!/usr/bin/env python3
import curses
import datetime as dt
import csv
import json
import os
import time
import textwrap
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
STOCKS_TTL_SECONDS = 1800

DEFAULT_QUERY = "Toronto news OR Canada news"
DEFAULT_NEWS_SCHEDULE = ["06:00", "12:00", "20:00"]
DEFAULT_SHOW_LINKS = True
DEFAULT_STOCK_SYMBOLS = ["TSLA.US"]
DEFAULT_LOOKBACK_HOURS = ""

XAI_API_KEY = os.environ.get("XAI_API_KEY", "").strip()
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4-1-fast").strip()
X_MAX_RESULTS = int(os.environ.get("X_MAX_RESULTS", "6"))
SUMMARY_PROMPT = (
    "Summarize the following X posts in 1-2 sentences. "
    "Be concise and neutral."
)

X_SEARCH_QUERY = ""
NEWS_SCHEDULE = []
SHOW_LINKS = True
STOCK_SYMBOLS = []
ALLOWED_HANDLES = []
EXCLUDED_HANDLES = []
KEYWORDS_INCLUDE = []
KEYWORDS_EXCLUDE = []
NEWS_LOOKBACK_HOURS = ""


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
    if ttl_seconds is not None:
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


def parse_schedule(value):
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = [s.strip() for s in value.split(",") if s.strip()]
    else:
        items = []
    parsed = []
    for item in items:
        parts = item.split(":")
        if len(parts) != 2:
            continue
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            continue
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            continue
        parsed.append(f"{hour:02d}:{minute:02d}")
    return parsed


def parse_csv_list(value):
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = [s.strip() for s in value.split(",") if s.strip()]
    else:
        items = []
    return [item for item in items if item]


def load_settings():
    global X_SEARCH_QUERY, NEWS_SCHEDULE, SHOW_LINKS, STOCK_SYMBOLS, X_MAX_RESULTS, SUMMARY_PROMPT
    global ALLOWED_HANDLES, EXCLUDED_HANDLES, KEYWORDS_INCLUDE, KEYWORDS_EXCLUDE, NEWS_LOOKBACK_HOURS
    config = load_config()
    env_query = os.environ.get("X_SEARCH_QUERY", "").strip()
    X_SEARCH_QUERY = env_query or str(config.get("x_search_query", "")).strip() or DEFAULT_QUERY
    schedule = config.get("news_schedule", DEFAULT_NEWS_SCHEDULE)
    NEWS_SCHEDULE = parse_schedule(schedule) or DEFAULT_NEWS_SCHEDULE
    show_links = config.get("show_links", DEFAULT_SHOW_LINKS)
    SHOW_LINKS = bool(show_links)
    symbols = config.get("stock_symbols", DEFAULT_STOCK_SYMBOLS)
    if isinstance(symbols, str):
        symbols = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    STOCK_SYMBOLS = [s.strip().upper() for s in symbols] or DEFAULT_STOCK_SYMBOLS
    ALLOWED_HANDLES = parse_csv_list(config.get("allowed_handles", []))
    EXCLUDED_HANDLES = parse_csv_list(config.get("excluded_handles", []))
    KEYWORDS_INCLUDE = parse_csv_list(config.get("keywords_include", []))
    KEYWORDS_EXCLUDE = parse_csv_list(config.get("keywords_exclude", []))
    NEWS_LOOKBACK_HOURS = str(config.get("news_lookback_hours", DEFAULT_LOOKBACK_HOURS)).strip()
    max_results = config.get("x_max_results")
    if max_results is not None:
        try:
            X_MAX_RESULTS = max(1, int(max_results))
        except (TypeError, ValueError):
            pass
    prompt = str(config.get("summary_prompt", "")).strip()
    if prompt:
        SUMMARY_PROMPT = prompt


def save_settings(
    query,
    schedule,
    show_links,
    symbols,
    max_results,
    summary_prompt,
    allowed_handles,
    excluded_handles,
    keywords_include,
    keywords_exclude,
    lookback_hours,
):
    config = load_config()
    config["x_search_query"] = query
    config["news_schedule"] = schedule
    config["show_links"] = bool(show_links)
    config["stock_symbols"] = symbols
    config["x_max_results"] = max_results
    config["summary_prompt"] = summary_prompt
    config["allowed_handles"] = allowed_handles
    config["excluded_handles"] = excluded_handles
    config["keywords_include"] = keywords_include
    config["keywords_exclude"] = keywords_exclude
    config["news_lookback_hours"] = lookback_hours
    save_config(config)


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


def get_stocks():
    cached = read_cache("stocks.json", STOCKS_TTL_SECONDS)
    if cached:
        return cached

    symbols = [s.lower() for s in STOCK_SYMBOLS]
    if not symbols:
        return {"items": []}
    url = "https://stooq.com/q/l/?s=" + ",".join(symbols) + "&f=sd2t2ohlcv&h&e=csv"
    try:
        with urllib.request.urlopen(url, timeout=6) as resp:
            body = resp.read().decode("utf-8")
    except Exception as exc:
        return {"error": str(exc)}

    items = []
    reader = csv.DictReader(body.splitlines())
    for row in reader:
        if not row:
            continue
        items.append(
            {
                "symbol": row.get("Symbol", ""),
                "date": row.get("Date", ""),
                "time": row.get("Time", ""),
                "open": row.get("Open", ""),
                "high": row.get("High", ""),
                "low": row.get("Low", ""),
                "close": row.get("Close", ""),
                "volume": row.get("Volume", ""),
            }
        )
    data = {"items": items}
    write_cache("stocks.json", data)
    return data


def refresh_stocks_cache():
    try:
        os.remove(cache_path("stocks.json"))
    except FileNotFoundError:
        pass


def schedule_due(now, last_fetch_dt):
    if not NEWS_SCHEDULE:
        return True
    if last_fetch_dt and last_fetch_dt.tzinfo is None:
        last_fetch_dt = last_fetch_dt.replace(tzinfo=now.tzinfo)
    schedule_times = []
    for item in NEWS_SCHEDULE:
        hour, minute = [int(p) for p in item.split(":")]
        schedule_times.append(now.replace(hour=hour, minute=minute, second=0, microsecond=0))
    due_times = [t for t in schedule_times if now >= t]
    if not due_times:
        return False
    latest_due = max(due_times)
    if last_fetch_dt is None:
        return True
    return last_fetch_dt < latest_due


def get_news(now, force=False):
    cached = read_cache("news.json", None)
    last_fetch_dt = None
    if cached and cached.get("fetched_at"):
        try:
            last_fetch_dt = dt.datetime.fromisoformat(cached["fetched_at"])
        except ValueError:
            last_fetch_dt = None
    if cached and not force and not schedule_due(now, last_fetch_dt):
        return cached

    if not XAI_API_KEY:
        return {"error": "Missing XAI_API_KEY"}

    try:
        from xai_sdk import Client
        from xai_sdk.chat import user
        from xai_sdk.tools import x_search
    except Exception:
        return {"error": "Missing dependency: xai-sdk (pip install xai-sdk==1.3.1)"}

    include_terms = " ".join(KEYWORDS_INCLUDE)
    exclude_terms = " ".join(f"-{term}" for term in KEYWORDS_EXCLUDE)
    query = " ".join(part for part in [X_SEARCH_QUERY, include_terms, exclude_terms] if part).strip()
    prompt = (
        "Search X for recent posts about: "
        f"{query}. Return a JSON array with up to {X_MAX_RESULTS} items. "
        "Each item must include: text, author_handle, created_at, url. "
        "If a field is unknown, use an empty string. Return only JSON."
    )

    try:
        client = Client(api_key=XAI_API_KEY)
        tool_args = {}
        if ALLOWED_HANDLES and not EXCLUDED_HANDLES:
            tool_args["allowed_x_handles"] = ALLOWED_HANDLES
        if EXCLUDED_HANDLES and not ALLOWED_HANDLES:
            tool_args["excluded_x_handles"] = EXCLUDED_HANDLES
        if NEWS_LOOKBACK_HOURS:
            try:
                hours = float(NEWS_LOOKBACK_HOURS)
                tool_args["from_date"] = now - dt.timedelta(hours=hours)
            except (TypeError, ValueError):
                pass
        chat = client.chat.create(model=XAI_MODEL, tools=[x_search(**tool_args)])
        chat.append(user(prompt))
        response = chat.sample()
        content = response.content or ""
    except Exception as exc:
        return {"error": str(exc)}

    try:
        items = json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Invalid response from xAI search", "raw": content}

    summary = ""
    if items:
        try:
            summary_prompt = (
                SUMMARY_PROMPT
                + " Posts:\n"
                + "\n".join(f"- {i.get('text','')}" for i in items)
            )
            sum_chat = client.chat.create(model=XAI_MODEL)
            sum_chat.append(user(summary_prompt))
            sum_resp = sum_chat.sample()
            summary = (sum_resp.content or "").strip()
        except Exception:
            summary = ""

    data = {"items": items, "summary": summary, "fetched_at": now.isoformat()}
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
    return {
        "error": None,
        "items": items,
        "raw": "",
        "summary": str(data.get("summary", "")).strip(),
    }


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


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_num(value, digits=2):
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


def fmt_volume(value):
    num = to_float(value)
    if num is None:
        return "N/A"
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return f"{num:.0f}"


def safe_addstr(stdscr, y, x, text):
    try:
        stdscr.addstr(y, x, text)
    except curses.error:
        pass


def init_colors():
    if not curses.has_colors():
        return
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)    # title
    curses.init_pair(2, curses.COLOR_YELLOW, -1)  # weather
    curses.init_pair(3, curses.COLOR_GREEN, -1)   # news
    curses.init_pair(4, curses.COLOR_MAGENTA, -1) # meta
    curses.init_pair(5, curses.COLOR_RED, -1)     # errors
    curses.init_pair(6, curses.COLOR_BLUE, -1)    # links
    curses.init_pair(7, curses.COLOR_GREEN, -1)   # up
    curses.init_pair(8, curses.COLOR_RED, -1)     # down


def osc8_link(url, label):
    if not url:
        return label
    esc = "\x1b]8;;"
    bel = "\x1b\\"
    return f"{esc}{url}{bel}{label}{esc}{bel}"


def wrap_line(prefix, text, width):
    if width <= 0:
        return []
    first_width = max(1, width)
    lines = textwrap.wrap(text, width=first_width) if text else [""]
    if not lines:
        lines = [""]
    wrapped = []
    first = lines[0]
    wrapped.append(f"{prefix}{first}"[:width])
    indent = " " * len(prefix)
    for line in lines[1:]:
        wrapped.append(f"{indent}{line}"[:width])
    return wrapped


def prompt_input(stdscr, y, prompt, current, width):
    line = f"{prompt} [{current}]: "
    safe_addstr(stdscr, y, 0, line[: width - 1])
    try:
        value = stdscr.getstr(y, min(len(line), width - 1)).decode("utf-8").strip()
    except Exception:
        value = ""
    return value or current


def settings_screen(stdscr):
    global X_SEARCH_QUERY, NEWS_SCHEDULE, SHOW_LINKS, STOCK_SYMBOLS, X_MAX_RESULTS, SUMMARY_PROMPT
    global ALLOWED_HANDLES, EXCLUDED_HANDLES, KEYWORDS_INCLUDE, KEYWORDS_EXCLUDE, NEWS_LOOKBACK_HOURS
    curses.echo()
    stdscr.nodelay(False)
    stdscr.timeout(-1)

    height, width = stdscr.getmaxyx()
    stdscr.erase()
    safe_addstr(stdscr, 0, 0, "Settings (leave blank to keep current, Enter to save)")
    safe_addstr(
        stdscr,
        1,
        0,
        "News schedule format: HH:MM, comma-separated (24h).",
    )
    safe_addstr(
        stdscr,
        2,
        0,
        "Show in-post links? enter y/n.",
    )
    safe_addstr(
        stdscr,
        3,
        0,
        "Stock symbols format: TSLA.US, AAPL.US, MSFT.US",
    )
    safe_addstr(
        stdscr,
        4,
        0,
        "Max results is a number; summary prompt is free text.",
    )
    safe_addstr(
        stdscr,
        5,
        0,
        "Filters: handles and keywords are comma-separated lists.",
    )

    current_query = X_SEARCH_QUERY
    current_schedule = ", ".join(NEWS_SCHEDULE)
    current_links = "y" if SHOW_LINKS else "n"
    current_symbols = ", ".join(STOCK_SYMBOLS)
    current_max_results = str(X_MAX_RESULTS)
    current_summary = SUMMARY_PROMPT
    current_allowed = ", ".join(ALLOWED_HANDLES)
    current_excluded = ", ".join(EXCLUDED_HANDLES)
    current_keywords_include = ", ".join(KEYWORDS_INCLUDE)
    current_keywords_exclude = ", ".join(KEYWORDS_EXCLUDE)
    current_lookback = str(NEWS_LOOKBACK_HOURS)

    new_query = prompt_input(stdscr, 7, "X search query", current_query, width)
    new_schedule_input = prompt_input(
        stdscr, 8, "News schedule", current_schedule, width
    )
    new_links_input = prompt_input(
        stdscr, 9, "Show links", current_links, width
    ).lower()
    new_symbols_input = prompt_input(
        stdscr, 10, "Stock symbols", current_symbols, width
    )
    new_max_results = prompt_input(
        stdscr, 11, "Max results", current_max_results, width
    )
    new_summary_prompt = prompt_input(
        stdscr, 12, "Summary prompt", current_summary, width
    )
    new_allowed = prompt_input(
        stdscr, 13, "Allowed handles", current_allowed, width
    )
    new_excluded = prompt_input(
        stdscr, 14, "Excluded handles", current_excluded, width
    )
    new_keywords_include = prompt_input(
        stdscr, 15, "Include keywords", current_keywords_include, width
    )
    new_keywords_exclude = prompt_input(
        stdscr, 16, "Exclude keywords", current_keywords_exclude, width
    )
    new_lookback = prompt_input(
        stdscr, 17, "Lookback hours", current_lookback, width
    )
    new_schedule = parse_schedule(new_schedule_input)
    if not new_schedule:
        new_schedule = NEWS_SCHEDULE
    show_links = SHOW_LINKS
    if new_links_input in ("y", "yes", "true", "1"):
        show_links = True
    elif new_links_input in ("n", "no", "false", "0"):
        show_links = False

    symbols = [s.strip().upper() for s in new_symbols_input.split(",") if s.strip()]
    if not symbols:
        symbols = STOCK_SYMBOLS

    try:
        max_results = max(1, int(new_max_results))
    except (TypeError, ValueError):
        max_results = X_MAX_RESULTS
    if not new_summary_prompt.strip():
        new_summary_prompt = SUMMARY_PROMPT

    allowed_handles = parse_csv_list(new_allowed)
    excluded_handles = parse_csv_list(new_excluded)
    keywords_include = parse_csv_list(new_keywords_include)
    keywords_exclude = parse_csv_list(new_keywords_exclude)

    save_settings(
        new_query,
        new_schedule,
        show_links,
        symbols,
        max_results,
        new_summary_prompt,
        allowed_handles,
        excluded_handles,
        keywords_include,
        keywords_exclude,
        new_lookback.strip(),
    )
    X_SEARCH_QUERY = new_query
    NEWS_SCHEDULE = new_schedule
    SHOW_LINKS = show_links
    STOCK_SYMBOLS = symbols
    X_MAX_RESULTS = max_results
    SUMMARY_PROMPT = new_summary_prompt
    ALLOWED_HANDLES = allowed_handles
    EXCLUDED_HANDLES = excluded_handles
    KEYWORDS_INCLUDE = keywords_include
    KEYWORDS_EXCLUDE = keywords_exclude
    NEWS_LOOKBACK_HOURS = new_lookback.strip()

    stdscr.erase()
    safe_addstr(stdscr, 0, 0, "Settings saved. Press any key to return.")
    stdscr.getkey()

    curses.noecho()
    stdscr.nodelay(True)
    stdscr.timeout(0)


def draw(stdscr, weather, news, now, status=""):
    stdscr.erase()
    height, width = stdscr.getmaxyx()

    title = "World Status - Toronto"
    clock = now.strftime("%A, %B %d %Y %H:%M:%S")
    if curses.has_colors():
        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
    safe_addstr(stdscr, 0, 0, title[: width - 1])
    if curses.has_colors():
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
        stdscr.attron(curses.color_pair(1))
    safe_addstr(stdscr, 1, 0, clock[: width - 1])
    if curses.has_colors():
        stdscr.attroff(curses.color_pair(1))

    if curses.has_colors():
        stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
    safe_addstr(stdscr, 3, 0, "Weather")
    if curses.has_colors():
        stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
    if weather.get("error"):
        if curses.has_colors():
            stdscr.attron(curses.color_pair(5))
        safe_addstr(stdscr, 4, 0, f"  Error: {weather['error']}")
        if curses.has_colors():
            stdscr.attroff(curses.color_pair(5))
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

    stocks = get_stocks()
    if curses.has_colors():
        stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
    safe_addstr(stdscr, 7, 0, "Stocks")
    if curses.has_colors():
        stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
    stock_y = 8
    if stocks.get("error"):
        if curses.has_colors():
            stdscr.attron(curses.color_pair(5))
        safe_addstr(stdscr, stock_y, 0, f"  Error: {stocks['error']}"[: width - 1])
        if curses.has_colors():
            stdscr.attroff(curses.color_pair(5))
        stock_y += 1
    else:
        for item in stocks.get("items", [])[:5]:
            if stock_y >= height - 1:
                break
            symbol = item.get("symbol", "")
            open_p = to_float(item.get("open"))
            high_p = to_float(item.get("high"))
            low_p = to_float(item.get("low"))
            close_p = to_float(item.get("close"))
            change = None
            pct = None
            arrow = "•"
            color = None
            if open_p is not None and close_p is not None:
                change = close_p - open_p
                if open_p != 0:
                    pct = change / open_p * 100.0
                if change > 0:
                    arrow = "▲"
                    color = 7
                elif change < 0:
                    arrow = "▼"
                    color = 8
            line = (
                f"  {symbol:<8} {arrow} {fmt_num(close_p)} "
                f"{fmt_num(change)} ({fmt_num(pct, 1)}%) "
                f"R {fmt_num(low_p)}-{fmt_num(high_p)} "
                f"V {fmt_volume(item.get('volume'))}"
            )
            if color and curses.has_colors():
                stdscr.attron(curses.color_pair(color))
            safe_addstr(stdscr, stock_y, 0, line[: width - 1])
            if color and curses.has_colors():
                stdscr.attroff(curses.color_pair(color))
            stock_y += 1

    schedule_text = ", ".join(NEWS_SCHEDULE) if NEWS_SCHEDULE else "manual"
    if curses.has_colors():
        stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
    safe_addstr(
        stdscr,
        stock_y + 1,
        0,
        f"News - X search: {X_SEARCH_QUERY} (schedule {schedule_text})"[: width - 1],
    )
    if curses.has_colors():
        stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
    n = parse_news(news)
    if n["error"]:
        if curses.has_colors():
            stdscr.attron(curses.color_pair(5))
        safe_addstr(stdscr, stock_y + 2, 0, f"  Error: {n['error']}"[: width - 1])
        if n.get("raw"):
            safe_addstr(stdscr, stock_y + 3, 0, f"  Raw: {n['raw']}"[: width - 1])
        if curses.has_colors():
            stdscr.attroff(curses.color_pair(5))
    elif not n["items"]:
        safe_addstr(stdscr, stock_y + 2, 0, "  No results")
    else:
        y = stock_y + 2
        if n.get("summary"):
            summary_lines = wrap_line("  Summary: ", n["summary"], width - 1)
            for line in summary_lines:
                if y >= height - 1:
                    break
                safe_addstr(stdscr, y, 0, line)
                y += 1
            if y < height - 1:
                y += 1
        for item in n["items"]:
            if y >= height - 1:
                break
            lines = wrap_line("  ", item["text"], width - 1)
            for line in lines:
                if y >= height - 1:
                    break
                safe_addstr(stdscr, y, 0, line)
                y += 1
            if y >= height - 1:
                break
            meta_label = f"@{item['user']} {fmt_time(item['time'])}"
            meta = f"  {meta_label}"
            if curses.has_colors():
                stdscr.attron(curses.color_pair(4))
            safe_addstr(stdscr, y, 0, meta[: width - 1])
            if curses.has_colors():
                stdscr.attroff(curses.color_pair(4))
            y += 1
            if y >= height - 1:
                break
            if SHOW_LINKS:
                url = item.get("url", "")
                if url:
                    url_lines = wrap_line("  ", url, width - 1)
                    for line in url_lines:
                        if y >= height - 1:
                            break
                        if curses.has_colors():
                            stdscr.attron(curses.color_pair(6))
                        safe_addstr(stdscr, y, 0, line)
                        if curses.has_colors():
                            stdscr.attroff(curses.color_pair(6))
                        y += 1
            if y >= height - 1:
                break
            y += 1

    footer = "Press q to quit | s settings | r refresh"
    if status:
        footer = f"{footer} | {status}"
    safe_addstr(stdscr, height - 1, 0, footer[: width - 1])
    stdscr.refresh()


def dashboard(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)
    init_colors()

    weather = {}
    news = {}
    last_weather_fetch = 0.0

    status = ""
    while True:
        now = dt.datetime.now(ZoneInfo(TIMEZONE))
        now_ts = time.time()

        if now_ts - last_weather_fetch > WEATHER_TTL_SECONDS or not weather:
            try:
                weather = get_weather()
            except Exception as exc:
                weather = {"error": str(exc)}
            last_weather_fetch = now_ts

        try:
            news = get_news(now, force=False)
        except Exception as exc:
            news = {"error": str(exc)}

        draw(stdscr, weather, news, now, status)
        status = ""

        try:
            key = stdscr.getkey()
        except curses.error:
            key = None
        if key in ("q", "Q"):
            break
        if key in ("r", "R"):
            status = "Refreshing..."
            draw(stdscr, weather, news, now, status)
            try:
                refresh_stocks_cache()
                news = get_news(now, force=True)
            except Exception as exc:
                news = {"error": str(exc)}
        if key in ("s", "S"):
            settings_screen(stdscr)

        time.sleep(1)


def main():
    try:
        ensure_xai_api_key()
        load_settings()
        curses.wrapper(dashboard)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
