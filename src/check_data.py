import time

import psycopg2
from pymongo import MongoClient

RUNS = 10  # each query is repeated and averaged

# Connect to both databases
pg = psycopg2.connect(host="localhost", port=5432, dbname="movie_db",
                      user="movie_user", password="movie_pass")
cur = pg.cursor()
mongo = MongoClient("mongodb://movie_user:movie_pass@localhost:27017/?authSource=admin")["movie_db"]


def timed(func):
    """Run a query RUNS times and return the average time in milliseconds."""
    start = time.time()
    for _ in range(RUNS):
        func()
    return (time.time() - start) / RUNS * 1000


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

# 3) Query B: top 5 movies by average rating (at least 50 ratings)
def pg_query_b():
    cur.execute("""
        SELECT m.title, AVG(r.rating) AS avg_rating, COUNT(*) AS n
        FROM ratings r JOIN movies m ON m.movie_id = r.movie_id
        GROUP BY m.title
        HAVING COUNT(*) >= 50
        ORDER BY avg_rating DESC
        LIMIT 5
    """)
    return cur.fetchall()

def mongo_query_b():
    return list(mongo.ratings.aggregate([
        {"$group": {"_id": "$movie_id", "avg_rating": {"$avg": "$rating"}, "n": {"$sum": 1}}},
        {"$match": {"n": {"$gte": 50}}},
        {"$sort": {"avg_rating": -1}},
        {"$limit": 5},
        {"$lookup": {"from": "movies", "localField": "_id",
                     "foreignField": "movie_id", "as": "movie"}},
    ]))

print("\nSample result (PostgreSQL, top 5 movies):")
for title, avg, n in pg_query_b():
    print(f"  {title} - {float(avg):.2f} ({n} ratings)")

print(f"\nAverage query time over {RUNS} runs:")
print(f"  Query A (one user's ratings): PostgreSQL {timed(pg_query_a):.2f} ms | MongoDB {timed(mongo_query_a):.2f} ms")
print(f"  Query B (top 5 movies):       PostgreSQL {timed(pg_query_b):.2f} ms | MongoDB {timed(mongo_query_b):.2f} ms")

cur.close()
pg.close()
