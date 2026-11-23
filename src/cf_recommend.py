"""Creates the final top-10 recommendations for every user and writes them back to the databases."""
import time
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values
from pymongo import MongoClient

from config import PG_PARAMS, MONGO_URI, MONGO_DB
from cf_data import load_from_postgres, load_from_mongo
from cf_preprocess import build_matrix
from cf_model import build_similarity, MAIN_K
from cf_topn import knn_vote_scores, popularity_scores, top_n, TOP_N

MODEL_NAME = f"user-knn-votes-k{MAIN_K}"
FALLBACK_NAME = "popularity-fallback"
WRITE_RUNS = 3

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS recommendations (
    user_id    INTEGER NOT NULL REFERENCES users(user_id),
    movie_id   INTEGER NOT NULL REFERENCES movies(movie_id),
    rec_rank   SMALLINT NOT NULL CHECK (rec_rank BETWEEN 1 AND 10),
    score      DOUBLE PRECISION NOT NULL,
    model_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, rec_rank)
)
"""


def compute_recommendations(df):
    """Trains the model on all ratings and returns (user_id, movie_id, rank, score, model) rows.
    If the kNN model cannot fill all 10 places for a user (for example because the user has no
    similar neighbours), the remaining places are filled with the most popular unseen movies."""
    matrix, user_means, centered = build_matrix(df)
    S, C, R = build_similarity(matrix, centered)
    seen = R > 0
    scores = knn_vote_scores(S, matrix)
    top, valid = top_n(scores, seen)
    pop_scores = popularity_scores(R)
    pop_top, _ = top_n(pop_scores, seen)
    users = matrix.index.to_numpy()
    movies = matrix.columns.to_numpy()

    rows = []
    for ui in range(len(users)):
        chosen = [(int(top[ui, p]), float(scores[ui, top[ui, p]]), MODEL_NAME)
                  for p in range(TOP_N) if valid[ui, p]]
        taken = {m for m, _, _ in chosen}
        for p in range(TOP_N):
            if len(chosen) >= TOP_N:
                break
            mi = int(pop_top[ui, p])
            if mi not in taken:
                chosen.append((mi, float(pop_scores[ui, mi]), FALLBACK_NAME))
                taken.add(mi)
        for pos, (mi, score, model) in enumerate(chosen, start=1):
            rows.append((int(users[ui]), int(movies[mi]), pos, score, model))
    return rows


def write_to_postgres(rows):
    """Relational design: one row per recommended movie. The ratings table is not touched."""
    conn = psycopg2.connect(**PG_PARAMS)
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    cur.execute("DELETE FROM recommendations")
    execute_values(
        cur,
        "INSERT INTO recommendations (user_id, movie_id, rec_rank, score, model_name) VALUES %s",
        [(u, m, r, s, model) for u, m, r, s, model in rows],
    )
    conn.commit()
    cur.close()
    conn.close()


def write_to_mongo(rows):
    """Document design: one document per user with the 10 recommendations embedded in an array.
    The movie title is stored inside the document, so showing the list needs no second query."""
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    titles = {
        d["movie_id"]: d["title"]
        for d in db["movies"].find({}, {"_id": 0, "movie_id": 1, "title": 1})
    }
    per_user = {}
    for u, m, r, s, model in rows:
        per_user.setdefault(u, []).append(
            {"rank": r, "movie_id": m, "title": titles.get(m), "score": s, "model": model}
        )
    now = datetime.now(timezone.utc)
    documents = [
        {"user_id": u, "created_at": now, "recommendations": items}
        for u, items in per_user.items()
    ]
    collection = db["recommendations"]
    collection.delete_many({})
    collection.create_index("user_id", unique=True)
    collection.insert_many(documents)
    client.close()


def show_postgres(user_id=1):
    """Reads the saved recommendations back from PostgreSQL."""
    conn = psycopg2.connect(**PG_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM recommendations")
    n_rec = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ratings")
    n_ratings = cur.fetchone()[0]
    cur.execute(
        "SELECT r.rec_rank, m.title FROM recommendations r "
        "JOIN movies m ON m.movie_id = r.movie_id WHERE r.user_id = %s ORDER BY r.rec_rank",
        (user_id,),
    )
    top = cur.fetchall()
    cur.close()
    conn.close()
    print(f"PostgreSQL check: {n_rec} rows in recommendations, ratings table still has {n_ratings} rows")
    print(f"Top {len(top)} for user {user_id} (read back from PostgreSQL):")
    for rank, title in top:
        print(f"  {rank}. {title}")


def show_mongo(user_id=1):
    """Reads the saved recommendations back from MongoDB."""
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    n_docs = db["recommendations"].count_documents({})
    n_ratings = db["ratings"].count_documents({})
    doc = db["recommendations"].find_one({"user_id": user_id})
    client.close()
    print(f"MongoDB check: {n_docs} documents in recommendations, ratings collection still has {n_ratings} documents")
    print(f"Top {len(doc['recommendations'])} for user {user_id} (read back from MongoDB):")
    for item in doc["recommendations"]:
        print(f"  {item['rank']}. {item['title']}")


def run(name, loader, writer, shower):
    """Full round trip for one database: read ratings, train, write recommendations, read them back."""
    df, read_time = loader()

    start = time.perf_counter()
    rows = compute_recommendations(df)
    model_time = time.perf_counter() - start

    times = []
    for _ in range(WRITE_RUNS):
        start = time.perf_counter()
        writer(rows)
        times.append(time.perf_counter() - start)
    write_time = sum(times) / len(times)

    fallback_users = sorted({u for u, m, r, s, model in rows if model == FALLBACK_NAME})
    print(f"=== {name} ===")
    print(f"Read {read_time:.3f} s | model {model_time:.3f} s | write (average of {WRITE_RUNS} runs) {write_time:.3f} s")
    print(f"Wrote {len(rows)} recommendations for {len({r[0] for r in rows})} users")
    print(f"Users who got popular movies as a fallback: {fallback_users}")
    shower()
    print()
    return {(u, m, r) for u, m, r, s, model in rows}


if __name__ == "__main__":
    pg_rows = run("PostgreSQL", load_from_postgres, write_to_postgres, show_postgres)
    mongo_rows = run("MongoDB", load_from_mongo, write_to_mongo, show_mongo)
    print("Same recommendations from both databases:", pg_rows == mongo_rows)