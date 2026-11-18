import time

import pandas as pd
from pymongo import ASCENDING, MongoClient

from config import DATA_DIR, MONGO_URI, MONGO_DB

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# Read the CSV files
movies = pd.read_csv(DATA_DIR / "movies.csv")
ratings = pd.read_csv(DATA_DIR / "ratings.csv")
movies.columns = movies.columns.str.lower()
ratings.columns = ratings.columns.str.lower()

# Prepare movie documents: genres become a list instead of one text
movie_docs = []
for row in movies.itertuples(index=False):
    genres = [] if row.genres == "(no genres listed)" else row.genres.split("|")
    movie_docs.append({
        "movie_id": int(row.movieid),
        "title": row.title,
        "genres": genres,
    })

# Prepare rating documents
ratings["rated_at"] = pd.to_datetime(ratings["timestamp"], unit="s")
rating_docs = [
    {
        "user_id": int(r.userid),
        "movie_id": int(r.movieid),
        "rating": float(r.rating),
        "rated_at": r.rated_at.to_pydatetime(),
    }
    for r in ratings.itertuples(index=False)
]

# Start fresh so the script can be run again safely
db.movies.drop()
db.ratings.drop()

# Indexes are created before loading, same as the PostgreSQL schema:
# unique movie_id, unique (user_id, movie_id) and a separate movie_id index
db.movies.create_index("movie_id", unique=True)
db.ratings.create_index([("user_id", ASCENDING), ("movie_id", ASCENDING)], unique=True)
db.ratings.create_index("movie_id")

# Only the data insertion is timed, like in load_postgres.py
start = time.time()
db.movies.insert_many(movie_docs)
db.ratings.insert_many(rating_docs)
elapsed = time.time() - start

print(f"Loaded {db.movies.count_documents({})} movies, {db.ratings.count_documents({})} ratings")
print(f"MongoDB load time: {elapsed:.2f} seconds")

client.close()
