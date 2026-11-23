"""Loads the ratings straight from PostgreSQL and MongoDB into pandas DataFrames."""
import time

import pandas as pd
import psycopg2
from pymongo import MongoClient

from config import PG_PARAMS, MONGO_URI, MONGO_DB


def clean_types(df):
    """Makes sure both databases give the same column types."""
    df = df[["user_id", "movie_id", "rating"]].copy()
    df["user_id"] = df["user_id"].astype("int64")
    df["movie_id"] = df["movie_id"].astype("int64")
    df["rating"] = df["rating"].astype("float64")
    return df


def load_from_postgres():
    """Reads all ratings with a SQL query. Returns the DataFrame and the time taken."""
    start = time.perf_counter()
    conn = psycopg2.connect(**PG_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT user_id, movie_id, rating FROM ratings")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    df = pd.DataFrame(rows, columns=["user_id", "movie_id", "rating"])
    df = clean_types(df)
    return df, time.perf_counter() - start


def load_from_mongo():
    """Reads all ratings with a MongoDB find query. Returns the DataFrame and the time taken."""
    start = time.perf_counter()
    client = MongoClient(MONGO_URI)
    cursor = client[MONGO_DB]["ratings"].find(
        {}, {"_id": 0, "user_id": 1, "movie_id": 1, "rating": 1}
    )
    df = pd.DataFrame(list(cursor))
    client.close()
    df = clean_types(df)
    return df, time.perf_counter() - start


def average_time(loader, runs=3):
    """Runs a loader several times and returns the last DataFrame and the average time."""
    times = []
    for _ in range(runs):
        df, elapsed = loader()
        times.append(elapsed)
    return df, sum(times) / len(times)


if __name__ == "__main__":
    pg_df, pg_time = average_time(load_from_postgres)
    mongo_df, mongo_time = average_time(load_from_mongo)

    for name, df, t in [("PostgreSQL", pg_df, pg_time), ("MongoDB", mongo_df, mongo_time)]:
        print(
            f"{name}: {len(df)} ratings, {df['user_id'].nunique()} users, "
            f"{df['movie_id'].nunique()} rated movies, average read time {t:.3f} s"
        )

    sort_cols = ["user_id", "movie_id"]
    a = pg_df.sort_values(sort_cols).reset_index(drop=True)
    b = mongo_df.sort_values(sort_cols).reset_index(drop=True)
    print("Both sources give identical data:", a.equals(b))