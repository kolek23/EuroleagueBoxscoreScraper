import requests
import json
import sqlite3
import time
import random
import os
from tqdm import tqdm

# ---------------- Config ----------------
gamecodes = list(range(1, 381))
seasoncode = 'E2025'
DB_PATH = "data/euroleague2026draft.db"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Fixed, low pacing between requests. Testing suggests live.euroleague.net
# tolerates roughly one request every ~300-500ms if kept steady (no bursts).
BASE_DELAY = 0.4          # seconds between requests
MAX_RETRIES = 5
INITIAL_BACKOFF = 5       # seconds, doubles each retry, capped below
MAX_BACKOFF = 90

columns = ["Player_ID", "Team", "Player", "Minutes", "Points",
           "FieldGoalsMade2", "FieldGoalsAttempted2",
           "FieldGoalsMade3", "FieldGoalsAttempted3",
           "FreeThrowsMade", "FreeThrowsAttempted",
           "OffensiveRebounds", "DefensiveRebounds", "Assistances",
           "Steals", "Turnovers", "BlocksFavour", "BlocksAgainst",
           "FoulsCommited", "FoulsReceived", "Valuation"]

# ---------------- DB setup ----------------
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute(f"""
    CREATE TABLE IF NOT EXISTS euroleague_stats (
        gamecode INTEGER,
        {', '.join(columns)}
    )
""")

# Track which gamecodes we already have, so a rerun resumes instead of
# re-fetching (and re-hammering the API) from scratch.
c.execute("CREATE TABLE IF NOT EXISTS scraped_games (gamecode INTEGER PRIMARY KEY)")
conn.commit()

c.execute("SELECT gamecode FROM scraped_games")
already_done = {row[0] for row in c.fetchall()}
gamecodes_to_fetch = [g for g in gamecodes if g not in already_done]

print(f"{len(already_done)} games already scraped, {len(gamecodes_to_fetch)} remaining.")

# ---------------- Session ----------------
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
})


def fetch_boxscore(gamecode):
    """Fetch a single boxscore with retry/backoff on rate limiting or errors.
    Returns parsed JSON dict, or None if it fails permanently."""
    url = f"https://live.euroleague.net/api/Boxscore?gamecode={gamecode}&seasoncode={seasoncode}"
    backoff = INITIAL_BACKOFF

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=15)
        except requests.RequestException as e:
            tqdm.write(f"[gamecode {gamecode}] network error ({e}), retrying in {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
            continue

        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError:
                tqdm.write(f"[gamecode {gamecode}] bad JSON, treating as no data")
                return None

        if response.status_code in (429, 1015) or "rate limited" in response.text.lower():
            retry_after = response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else backoff
            tqdm.write(f"[gamecode {gamecode}] rate limited (attempt {attempt}), "
                       f"waiting {wait:.0f}s")
            time.sleep(wait)
            backoff = min(backoff * 2, MAX_BACKOFF)
            continue

        # Other HTTP errors (404 for a game that doesn't exist, etc.)
        tqdm.write(f"[gamecode {gamecode}] HTTP {response.status_code}, skipping")
        return None

    tqdm.write(f"[gamecode {gamecode}] gave up after {MAX_RETRIES} attempts")
    return None


# ---------------- Main loop ----------------
for gamecode in tqdm(gamecodes_to_fetch, desc="Scraping Games", unit="game"):
    data = fetch_boxscore(gamecode)

    if data is not None:
        stats_table = []
        for stats_dict in data.get("Stats", []):
            players_stats = stats_dict.get("PlayersStats")
            if players_stats:
                for player in players_stats:
                    row = [gamecode] + [player.get(col, "") for col in columns]
                    stats_table.append(row)

        if stats_table:
            placeholders = ", ".join(["?"] * (len(columns) + 1))
            c.executemany(
                f"INSERT INTO euroleague_stats VALUES ({placeholders})",
                stats_table
            )

    # Mark as done regardless of whether it had player data, so we don't
    # keep retrying games that legitimately have none (postponed, etc.)
    c.execute("INSERT OR IGNORE INTO scraped_games (gamecode) VALUES (?)", (gamecode,))
    conn.commit()

    # Fixed, low, steady pacing -- no long random jitter.
    time.sleep(BASE_DELAY + random.uniform(0, 0.1))

conn.close()
print("Done.")
