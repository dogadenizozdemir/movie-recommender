import time

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# Connection settings (same as in docker-compose.yml)
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="movie_db",
    user="movie_user",
    password="movie_pass",
)
cur = conn.cursor()

# Read the CSV files
movies = pd.read_csv("data/movies.csv")
ratings = pd.read_csv("data/ratings.csv")
movies.columns = movies.columns.str.lower()
ratings.columns = ratings.columns.str.lower()

# Prepare data
ratings["rated_at"] = pd.to_datetime(ratings["timestamp"], unit="s")
users = ratings[["userid"]].drop_duplicates()

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
