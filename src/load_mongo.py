import time

import pandas as pd
from pymongo import MongoClient

# Connection settings (same as in docker-compose.yml)
client = MongoClient("mongodb://movie_user:movie_pass@localhost:27017/?authSource=admin")
db = client["movie_db"]

# Read the CSV files
movies = pd.read_csv("data/movies.csv")
ratings = pd.read_csv("data/ratings.csv")
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

start = time.time()
db.movies.insert_many(movie_docs)
db.ratings.insert_many(rating_docs)
db.ratings.create_index("user_id")
db.ratings.create_index("movie_id")
elapsed = time.time() - start

print(f"Loaded {db.movies.count_documents({})} movies, {db.ratings.count_documents({})} ratings")
print(f"MongoDB load time: {elapsed:.2f} seconds")

client.close()
