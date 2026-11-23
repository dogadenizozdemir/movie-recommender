"""Compares how fast one user's saved top-10 list can be read back from PostgreSQL and MongoDB."""
import time

import psycopg2
from pymongo import MongoClient

from config import PG_PARAMS, MONGO_URI, MONGO_DB

WARMUP = 50      # queries that are run first and not counted
QUERIES = 1000   # queries per round (cycling through all users)
ROUNDS = 3

PG_SQL = (
    "SELECT r.rec_rank, m.title, r.score FROM recommendations r "
    "JOIN movies m ON m.movie_id = r.movie_id "
    "WHERE r.user_id = %s ORDER BY r.rec_rank"
)


def time_postgres(cur, user_ids):
    """Reads the list with a SQL JOIN (recommendations + movies). Returns milliseconds per query."""
    for uid in user_ids[:WARMUP]:
        cur.execute(PG_SQL, (uid,))
        cur.fetchall()
    start = time.perf_counter()
    for uid in user_ids:
        cur.execute(PG_SQL, (uid,))
        cur.fetchall()
    return (time.perf_counter() - start) / len(user_ids) * 1000


def time_mongo(collection, user_ids):
    """Reads the list with one find_one on the user's document. Returns milliseconds per query."""
    for uid in user_ids[:WARMUP]:
        collection.find_one({"user_id": uid})
    start = time.perf_counter()
    for uid in user_ids:
        doc = collection.find_one({"user_id": uid})
        _ = doc["recommendations"]
    return (time.perf_counter() - start) / len(user_ids) * 1000


if __name__ == "__main__":
    conn = psycopg2.connect(**PG_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT user_id FROM recommendations ORDER BY user_id")
    all_ids = [row[0] for row in cur.fetchall()]
    user_ids = [all_ids[i % len(all_ids)] for i in range(QUERIES)]

    client = MongoClient(MONGO_URI)
    collection = client[MONGO_DB]["recommendations"]

    pg_times, mongo_times = [], []
    for _ in range(ROUNDS):
        pg_times.append(time_postgres(cur, user_ids))
        mongo_times.append(time_mongo(collection, user_ids))

    cur.close()
    conn.close()
    client.close()

    print(f"Reading one user's top-10 list: {QUERIES} queries per round, {ROUNDS} rounds, all {len(all_ids)} users")
    print(f"PostgreSQL (JOIN recommendations + movies): {sum(pg_times) / ROUNDS:.3f} ms per query")
    print(f"MongoDB (one document, titles embedded):    {sum(mongo_times) / ROUNDS:.3f} ms per query")
    print("Rounds PostgreSQL:", ", ".join(f"{t:.3f}" for t in pg_times))
    print("Rounds MongoDB:   ", ", ".join(f"{t:.3f}" for t in mongo_times))