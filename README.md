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
- `src/cf_data.py`: reads the ratings from the databases for the model
- `src/cf_preprocess.py`: data checks, train/test split and user-item matrix
- `src/cf_model.py`: user-based kNN model, RMSE and MAE
- `src/cf_topn.py`: Precision@10 and Recall@10 of the top-10 lists
- `src/cf_recommend.py`: creates the final recommendations and writes them back to the databases
- `data/`: dataset files (not uploaded)
- `docs/`: report notes and result files

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

## Week 2: collaborative filtering

I used user-based k-nearest-neighbours collaborative filtering. Users are compared with cosine similarity on their mean-centered ratings. Each user then gets the 10 movies they have not rated yet that their 50 most similar users liked (rating 4.0 or higher), where more similar users count more. If a user has no similar users, the most popular unseen movies are used instead. The model only needs `pandas` and `numpy`, and it reads everything straight from the databases, so no CSV files are used.

How the scripts fit together:

- `cf_data.py` reads the ratings with a SQL query (PostgreSQL) and a find query (MongoDB).
- `cf_preprocess.py` checks the data, puts 20% of every user's ratings into a test set and builds the user-item matrix.
- `cf_model.py` predicts ratings and reports RMSE and MAE for k = 10, 20, 50 and 100.
- `cf_topn.py` measures how many of the recommended movies the user really liked, and compares this with a "most popular movies" baseline.
- `cf_recommend.py` trains on all ratings and writes the top-10 lists back to both databases, then reads them back. PostgreSQL gets a `recommendations` table with one row per recommended movie. MongoDB gets a `recommendations` collection with one document per user. The `ratings` data is not touched.

To run it (with both databases running and loaded):

        python src/cf_preprocess.py
        python src/cf_model.py
        python src/cf_topn.py
        python src/cf_recommend.py

Test set results (they are the same for PostgreSQL and MongoDB because the model gets exactly the same data; only the read and write times differ):

| Rating prediction | RMSE | MAE |
|---|---|---|
| Global mean | 1.050 | 0.831 |
| User mean | 0.952 | 0.740 |
| User-based kNN (k=50) | 0.910 | 0.688 |

| Top-10 list | Precision@10 | Recall@10 |
|---|---|---|
| Most popular movies | 0.113 | 0.092 |
| kNN, ranked by neighbour votes | 0.182 | 0.172 |

My first version ranked the movies by predicted rating and only reached a Precision@10 of 0.010, so I changed to neighbour votes. More numbers, timings and limitations are in `docs/week2_results.md`.

## Status

Work in progress. Both databases are set up and loaded with the same data, the collaborative filtering model is finished, and its recommendations are saved in both databases. Next steps are the discussion of the two data structures, the architecture diagram, a small demo page and the report.