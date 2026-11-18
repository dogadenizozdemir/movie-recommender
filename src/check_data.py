import time

import psycopg2
from pymongo import MongoClient

from config import PG_PARAMS, MONGO_URI, MONGO_DB

RUNS = 10  # each query is repeated and averaged

# Connect to both databases
pg = psycopg2.connect(**PG_PARAMS)
cur = pg.cursor()
mongo = MongoClient(MONGO_URI)[MONGO_DB]


def timed(func):
    """Run a query once as warm-up, then RUNS times; return the average in milliseconds."""
    func()
    start = time.perf_counter()
    for _ in range(RUNS):
        func()
    return (time.perf_counter() - start) / RUNS * 1000


# 1) Row counts
cur.execute("SELECT COUNT(*) FROM movies")
pg_movies = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM ratings")
pg_ratings = cur.fetchone()[0]
print(f"PostgreSQL: {pg_movies} movies, {pg_ratings} ratings")
print(f"MongoDB:    {mongo.movies.count_documents({})} movies, {mongo.ratings.count_documents({})} ratings")


# 2) Query A: all ratings of one user
def pg_query_a():
    cur.execute("SELECT movie_id, rating FROM ratings WHERE user_id = 1")
    return cur.fetchall()


def mongo_query_a():
    return list(mongo.ratings.find({"user_id": 1}, {"movie_id": 1, "rating": 1}))


# 3) Query B: top 5 movies by average rating (at least 50 ratings), grouped by movie_id in both
def pg_query_b():
    cur.execute("""
        SELECT m.title, AVG(r.rating) AS avg_rating, COUNT(*) AS n
        FROM ratings r JOIN movies m ON m.movie_id = r.movie_id
        GROUP BY m.movie_id, m.title
        HAVING COUNT(*) >= 50
        ORDER BY avg_rating DESC, m.movie_id
        LIMIT 5
    """)
    return cur.fetchall()


def mongo_query_b():
    return list(mongo.ratings.aggregate([
        {"$group": {"_id": "$movie_id", "avg_rating": {"$avg": "$rating"}, "n": {"$sum": 1}}},
        {"$match": {"n": {"$gte": 50}}},
        {"$sort": {"avg_rating": -1, "_id": 1}},
        {"$limit": 5},
        {"$lookup": {"from": "movies", "localField": "_id",
                     "foreignField": "movie_id", "as": "movie"}},
        {"$unwind": "$movie"},
    ]))


print("\nTop 5 movies (PostgreSQL):")
for title, avg, n in pg_query_b():
    print(f"  {title} - {float(avg):.2f} ({n} ratings)")

print("\nTop 5 movies (MongoDB):")
for doc in mongo_query_b():
    print(f"  {doc['movie']['title']} - {doc['avg_rating']:.2f} ({doc['n']} ratings)")

print(f"\nAverage query time over {RUNS} runs:")
print(f"  Query A (one user's ratings): PostgreSQL {timed(pg_query_a):.2f} ms | MongoDB {timed(mongo_query_a):.2f} ms")
print(f"  Query B (top 5 movies):       PostgreSQL {timed(pg_query_b):.2f} ms | MongoDB {timed(mongo_query_b):.2f} ms")

cur.close()
pg.close()
