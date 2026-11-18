import time

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from config import DATA_DIR, SQL_DIR, PG_PARAMS

conn = psycopg2.connect(**PG_PARAMS)
cur = conn.cursor()

# Read the CSV files
movies = pd.read_csv(DATA_DIR / "movies.csv")
ratings = pd.read_csv(DATA_DIR / "ratings.csv")
movies.columns = movies.columns.str.lower()
ratings.columns = ratings.columns.str.lower()

# Prepare data
ratings["rated_at"] = pd.to_datetime(ratings["timestamp"], unit="s")
users = ratings[["userid"]].drop_duplicates()

# Create the tables and indexes from schema.sql (drops old ones, so re-running is safe)
cur.execute((SQL_DIR / "schema.sql").read_text())
conn.commit()

# Only the data insertion is timed; indexes already exist, like in the MongoDB script
start = time.time()

# Insert movies, users, ratings (in this order because of foreign keys)
execute_values(
    cur,
    "INSERT INTO movies (movie_id, title, genres) VALUES %s",
    list(movies[["movieid", "title", "genres"]].itertuples(index=False, name=None)),
)
execute_values(
    cur,
    "INSERT INTO users (user_id) VALUES %s",
    list(users.itertuples(index=False, name=None)),
)
execute_values(
    cur,
    "INSERT INTO ratings (user_id, movie_id, rating, rated_at) VALUES %s",
    list(ratings[["userid", "movieid", "rating", "rated_at"]]
         .astype(object).itertuples(index=False, name=None)),
    page_size=5000,
)

conn.commit()
elapsed = time.time() - start

print(f"Loaded {len(movies)} movies, {len(users)} users, {len(ratings)} ratings")
print(f"PostgreSQL load time: {elapsed:.2f} seconds")

cur.close()
conn.close()
