"""Quick test: does the TMDB key work, and can MovieLens movie ids be matched to TMDB ids?"""
import json
import urllib.request

import pandas as pd

from config import ENV, DATA_DIR

links = pd.read_csv(DATA_DIR / "links.csv")
print("links.csv rows:", len(links), "| rows without a TMDB id:", int(links["tmdbId"].isna().sum()))

movie_id = 1
tmdb_id = int(links.loc[links["movieId"] == movie_id, "tmdbId"].iloc[0])
url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={ENV['TMDB_API_KEY']}"
with urllib.request.urlopen(url, timeout=15) as response:
    data = json.load(response)

print("MovieLens movie", movie_id, "-> TMDB id", tmdb_id, "->", data["title"])
print("poster_path:", data["poster_path"])