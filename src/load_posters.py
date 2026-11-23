"""Fetches poster paths from TMDB for the recommended movies and saves them in both databases."""
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import psycopg2
from pymongo import MongoClient, UpdateOne

from config import ENV, DATA_DIR, PG_PARAMS, MONGO_URI, MONGO_DB

API_URL = "https://api.themoviedb.org/3/movie/{}?api_key={}"
WORKERS = 5


def fetch_poster(tmdb_id):
    """Asks TMDB about one movie. Returns (poster_path, ok). A movie without a poster is ok with None."""
    url = API_URL.format(tmdb_id, ENV["TMDB_API_KEY"])
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                return json.load(response).get("poster_path"), True
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None, True
        except Exception:
            pass
        time.sleep(1 + attempt)
    return None, False


def main():
    links = pd.read_csv(DATA_DIR / "links.csv")
    tmdb_ids = {int(m): int(t) for m, t in zip(links["movieId"], links["tmdbId"]) if pd.notna(t)}

    conn = psycopg2.connect(**PG_PARAMS)
    cur = conn.cursor()
    cur.execute("ALTER TABLE movies ADD COLUMN IF NOT EXISTS tmdb_id INTEGER")
    cur.execute("ALTER TABLE movies ADD COLUMN IF NOT EXISTS poster_path TEXT")
    conn.commit()
    cur.execute("SELECT DISTINCT movie_id FROM recommendations ORDER BY movie_id")
    needed = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT movie_id, poster_path FROM movies WHERE poster_path IS NOT NULL")
    posters = dict(cur.fetchall())          # posters we already have from an earlier run

    no_link = [m for m in needed if m not in tmdb_ids]
    todo = [m for m in needed if m in tmdb_ids and m not in posters]
    print(f"Recommended movies: {len(needed)} | already have a poster: {len(posters.keys() & set(needed))} "
          f"| to fetch now: {len(todo)} | no TMDB id: {len(no_link)}")

    failed = 0
    if todo:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            results = list(pool.map(fetch_poster, [tmdb_ids[m] for m in todo]))
        for movie_id, (path, ok) in zip(todo, results):
            if not ok:
                failed += 1
            elif path:
                posters[movie_id] = path
    print(f"Fetched from TMDB: {len(todo) - failed} | failed: {failed}")
    if failed == len(todo) and todo:
        print("Every request failed. Please check the TMDB_API_KEY line in .env.")

    rows = [(tmdb_ids.get(m), posters.get(m), m) for m in needed]

    # PostgreSQL: two new columns in the movies table
    cur.executemany("UPDATE movies SET tmdb_id = %s, poster_path = %s WHERE movie_id = %s", rows)
    conn.commit()
    cur.close()
    conn.close()

    # MongoDB: the same two fields in the movies collection, and the poster inside every recommendation
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    db["movies"].bulk_write(
        [UpdateOne({"movie_id": m}, {"$set": {"tmdb_id": t, "poster_path": p}}) for t, p, m in rows]
    )
    updates = []
    for doc in db["recommendations"].find({}):
        for item in doc["recommendations"]:
            item["poster_path"] = posters.get(item["movie_id"])
        updates.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"recommendations": doc["recommendations"]}}))
    if updates:
        db["recommendations"].bulk_write(updates)
    client.close()

    with_poster = sum(1 for m in needed if m in posters)
    print(f"Recommended movies with a poster saved in both databases: {with_poster} of {len(needed)}")


if __name__ == "__main__":
    main()