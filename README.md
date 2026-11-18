# Movie Recommender: PostgreSQL vs MongoDB

This is my project for the Database course. I am building a movie recommendation system and comparing PostgreSQL and MongoDB. The machine learning model reads its data directly from the database, and the model results are written back to the database.

## Dataset

I use the MovieLens latest-small data from Kaggle ("Popular Movies Datasets - 9742 Movies"). It has 9,742 movies and 100,836 ratings from 610 users. The CSV files are not stored in this repository (see `.gitignore`). The scripts only use `movies.csv` and `ratings.csv`.

## Project structure

- `docker-compose.yml`: PostgreSQL 16 and MongoDB 7 containers
- `.env.example`: template for the settings file (the real `.env` is not uploaded)
- `sql/schema.sql`: PostgreSQL tables, constraints and indexes
- `src/config.py`: reads the connection settings from `.env`
- `src/load_postgres.py`: creates the tables and loads the data into PostgreSQL
- `src/load_mongo.py`: creates the indexes and loads the data into MongoDB
- `src/check_data.py`: checks the row counts and compares query times
- `data/`: dataset files (not uploaded)
- `docs/`: report notes and timing results

## Setup

Requirements: Docker, Python 3 and the packages `pandas`, `psycopg2-binary` and `pymongo`.

1. Create the settings file from the example (the same file is used by Docker and by the Python scripts):

        cp .env.example .env

2. Start PostgreSQL 16 and MongoDB 7:

        docker compose up -d

3. Download the Kaggle dataset "Popular Movies Datasets - 9742 Movies" (MovieLens latest-small) and copy `movies.csv` and `ratings.csv` into the `data/` folder.

4. Install the Python packages:

        pip install pandas psycopg2-binary pymongo

5. Load the data into both databases. `load_postgres.py` runs `sql/schema.sql` itself, and each script rebuilds its tables or collections, so it is safe to run again:

        python src/load_postgres.py
        python src/load_mongo.py

6. Check the row counts and compare the query times:

        python src/check_data.py

## Week 1 results

Both databases hold 9,742 movies and 100,836 ratings. Both have the same constraints: a unique (user_id, movie_id) pair and an index on movie_id. Values below are from `docs/week1_timings.txt`.

| Metric | PostgreSQL | MongoDB |
|---|---|---|
| Load time, mean of 3 runs (s) | 1.27 | 0.66 |
| Query A: one user's ratings (ms) | 0.32 | 0.86 |
| Query B: top 5 movies by average rating (ms) | 18.19 | 40.13 |

## Status

Work in progress. Both databases are set up and loaded with the same data. Next steps are the collaborative filtering model, its evaluation, and writing the recommendations back to the database.
