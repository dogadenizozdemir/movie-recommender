"""Streamlit demo page: shows the saved top-10 recommendations of a user with movie posters."""
import html
import time

import psycopg2
import streamlit as st
from pymongo import MongoClient

from config import PG_PARAMS, MONGO_URI, MONGO_DB

POSTER_URL = "https://image.tmdb.org/t/p/w342"
FALLBACK_MODEL = "popularity-fallback"

PG_RECOMMENDATIONS_SQL = (
    "SELECT r.rec_rank, m.title, m.poster_path, r.model_name "
    "FROM recommendations r JOIN movies m ON m.movie_id = r.movie_id "
    "WHERE r.user_id = %s ORDER BY r.rec_rank"
)
PG_LIKED_SQL = (
    "SELECT m.title, r.rating FROM ratings r JOIN movies m ON m.movie_id = r.movie_id "
    "WHERE r.user_id = %s ORDER BY r.rating DESC, r.movie_id LIMIT 5"
)

CSS = """<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.block-container {padding-top: 2rem; max-width: 1250px;}
.hero h1 {font-size: 2.6rem; font-weight: 800; margin: 0; background: linear-gradient(90deg, #ffb347, #ff5e62); -webkit-background-clip: text; background-clip: text; color: transparent; display: inline-block;}
.hero p {color: #9aa3bd; margin: 0.2rem 0 1.2rem 0; font-size: 1.02rem;}
.chip {display: inline-block; background: #1d2540; color: #c4cbe3; border-radius: 999px; padding: 4px 14px; margin: 0 8px 10px 0; font-size: 0.85rem;}
.chip b {color: #ffb347;}
.grid {display: grid; grid-template-columns: repeat(5, 1fr); gap: 18px; margin-top: 6px;}
@media (max-width: 1100px) {.grid {grid-template-columns: repeat(3, 1fr);}}
@media (max-width: 700px) {.grid {grid-template-columns: repeat(2, 1fr);}}
.card {position: relative; background: #151b2b; border-radius: 14px; overflow: hidden; transition: transform 0.2s ease, box-shadow 0.2s ease;}
.card:hover {transform: translateY(-5px); box-shadow: 0 12px 30px rgba(0, 0, 0, 0.55);}
.poster {width: 100%; aspect-ratio: 2 / 3; object-fit: cover; display: block; background: #1d2540;}
.noposter {width: 100%; aspect-ratio: 2 / 3; display: flex; align-items: center; justify-content: center; text-align: center; padding: 14px; box-sizing: border-box; background: linear-gradient(160deg, #1d2540, #2a1f3d); color: #9aa3bd; font-size: 0.9rem;}
.rank {position: absolute; top: 10px; left: 10px; background: rgba(0, 0, 0, 0.75); color: #fff; font-weight: 700; border-radius: 999px; padding: 2px 11px; font-size: 0.9rem;}
.pick {position: absolute; top: 10px; right: 10px; background: #ffb347; color: #1a1a1a; font-weight: 700; border-radius: 6px; padding: 2px 8px; font-size: 0.7rem;}
.title {padding: 10px 12px 13px 12px; font-size: 0.92rem; line-height: 1.3; color: #e8eaf0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.6em;}
.liked {background: #151b2b; border-radius: 10px; padding: 9px 14px; margin-bottom: 8px; color: #e8eaf0; font-size: 0.95rem;}
.liked .stars {color: #ffb347; font-weight: 700; margin-right: 10px;}
.note {color: #9aa3bd; font-size: 0.85rem; margin-top: 4px;}
.footer {color: #7c86a6; font-size: 0.8rem; margin-top: 2.4rem; padding-top: 1rem; border-top: 1px solid #232b45;}
</style>"""


@st.cache_resource
def pg_connection():
    conn = psycopg2.connect(**PG_PARAMS)
    conn.autocommit = True
    return conn


@st.cache_resource
def mongo_database():
    return MongoClient(MONGO_URI)[MONGO_DB]


@st.cache_data
def load_user_ids():
    with pg_connection().cursor() as cur:
        cur.execute("SELECT DISTINCT user_id FROM recommendations ORDER BY user_id")
        return [row[0] for row in cur.fetchall()]


def recommendations_postgres(user_id):
    """One SQL query with a JOIN. Returns the list and the query time in milliseconds."""
    with pg_connection().cursor() as cur:
        start = time.perf_counter()
        cur.execute(PG_RECOMMENDATIONS_SQL, (user_id,))
        rows = cur.fetchall()
        ms = (time.perf_counter() - start) * 1000
    return [{"rank": r[0], "title": r[1], "poster": r[2], "model": r[3]} for r in rows], ms


def recommendations_mongo(user_id):
    """One find on the user's document. Returns the list and the query time in milliseconds."""
    start = time.perf_counter()
    doc = mongo_database()["recommendations"].find_one({"user_id": user_id})
    ms = (time.perf_counter() - start) * 1000
    items = doc["recommendations"] if doc else []
    return [
        {"rank": i["rank"], "title": i.get("title"), "poster": i.get("poster_path"), "model": i.get("model")}
        for i in items
    ], ms


def liked_postgres(user_id):
    with pg_connection().cursor() as cur:
        cur.execute(PG_LIKED_SQL, (user_id,))
        return [(title, float(rating)) for title, rating in cur.fetchall()]


def liked_mongo(user_id):
    db = mongo_database()
    top = list(
        db["ratings"].find({"user_id": user_id}, {"_id": 0, "movie_id": 1, "rating": 1})
        .sort([("rating", -1), ("movie_id", 1)]).limit(5)
    )
    titles = {
        d["movie_id"]: d["title"]
        for d in db["movies"].find({"movie_id": {"$in": [t["movie_id"] for t in top]}}, {"_id": 0, "movie_id": 1, "title": 1})
    }
    return [(titles.get(t["movie_id"], "Unknown title"), float(t["rating"])) for t in top]


def card_html(item):
    title = html.escape(item["title"] or "Unknown title", quote=True)
    if item["poster"]:
        picture = f'<img class="poster" src="{POSTER_URL}{item["poster"]}" alt="{title}" loading="lazy">'
    else:
        picture = f'<div class="noposter">{title}</div>'
    pick = '<div class="pick">POPULAR PICK</div>' if item["model"] == FALLBACK_MODEL else ""
    return (
        f'<div class="card">{picture}<div class="rank">#{item["rank"]}</div>{pick}'
        f'<div class="title">{title}</div></div>'
    )


def main():
    st.set_page_config(page_title="Movie Recommender", page_icon="🎬", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="hero"><h1>Movie Recommender</h1>'
        "<p>User-based collaborative filtering on MovieLens, stored in PostgreSQL and MongoDB</p></div>",
        unsafe_allow_html=True,
    )

    try:
        user_ids = load_user_ids()
    except Exception:
        st.error("Could not reach the databases. Is Docker running? Start it with: docker compose up -d")
        st.stop()

    st.sidebar.header("Settings")
    database = st.sidebar.radio("Read the recommendations from", ["PostgreSQL", "MongoDB"])
    user_id = st.sidebar.selectbox("User", user_ids)
    st.sidebar.markdown(
        '<div class="note">Both databases hold the same recommendations. '
        "Switch between them to see how each one returns the list.</div>",
        unsafe_allow_html=True,
    )

    try:
        if database == "PostgreSQL":
            items, ms = recommendations_postgres(user_id)
            liked = liked_postgres(user_id)
        else:
            items, ms = recommendations_mongo(user_id)
            liked = liked_mongo(user_id)
    except Exception:
        st.error("The query failed. Please check that both databases are running.")
        st.stop()

    st.markdown(
        f'<span class="chip">Database: <b>{database}</b></span>'
        f'<span class="chip">Top-10 list read in <b>{ms:.2f} ms</b></span>'
        f'<span class="chip">Model: <b>user-based kNN</b></span>',
        unsafe_allow_html=True,
    )

    st.subheader(f"Top 10 for user {user_id}")
    if items:
        st.markdown('<div class="grid">' + "".join(card_html(i) for i in items) + "</div>", unsafe_allow_html=True)
        if any(i["model"] == FALLBACK_MODEL for i in items):
            st.markdown(
                '<div class="note">This user has no similar users, so some picks are simply the most popular movies.</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No recommendations saved for this user.")

    st.subheader("What this user rated highest")
    st.markdown(
        "".join(f'<div class="liked"><span class="stars">★ {r:.1f}</span>{html.escape(t, quote=True)}</div>' for t, r in liked),
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="footer">This product uses the TMDB API but is not endorsed or certified by TMDB. '
        "Ratings come from the MovieLens latest-small dataset.</div>",
        unsafe_allow_html=True,
    )


main()