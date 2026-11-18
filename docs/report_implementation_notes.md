# Implementation and Setup (draft notes for the report)

## Software used

| Software | Version |
|---|---|
| macOS | 26.6.2 |
| Docker | 29.8.0 |
| Docker Compose | 5.5.1 |
| Python | 3.12.7 |
| pandas | 2.2.2 |
| psycopg2 | 2.9.13 |
| pymongo | 4.19.0 |
| PostgreSQL (Docker image postgres:16) | 16.15 |
| MongoDB (Docker image mongo:7) | 7.0.48 |

## Environment

I did everything on a single MacBook. PostgreSQL and MongoDB run in two Docker containers, and the Python scripts run directly on my Mac. The scripts connect to the containers through localhost (PostgreSQL on port 5432, MongoDB on port 27017). So the system is a single-machine setup, not distributed.

## Configuration

All connection settings (user, password, database name, host, port) are kept in a `.env` file. This file is not uploaded to GitHub, only the template `.env.example` is. `docker-compose.yml` reads the values from `.env` to start the containers, and `src/config.py` reads the same file for the Python scripts. This way the passwords are written in only one place. The data is stored in two Docker volumes (`postgres_data` and `mongo_data`), so it is not lost when the containers are stopped.

## Setup steps

    cp .env.example .env
    docker compose up -d
    pip install pandas psycopg2-binary pymongo
    python src/load_postgres.py
    python src/load_mongo.py
    python src/check_data.py

The CSV files (`movies.csv` and `ratings.csv`) must be downloaded from Kaggle and copied into the `data/` folder first. Both load scripts delete and rebuild their tables or collections, so they can be run again without any problem.

## How the data is loaded

Both scripts read the CSV files with pandas and convert the Unix timestamps to normal dates.

- PostgreSQL: `load_postgres.py` first runs `sql/schema.sql`, which creates the tables `movies`, `users` and `ratings` with their constraints and indexes. Then it inserts the data in batches in this order: movies, users, ratings (because of the foreign keys).
- MongoDB: `load_mongo.py` creates the collections `movies` and `ratings`. The genres of each movie are stored as a list instead of one text. The indexes are created before the data is inserted, and then the documents are inserted with `insert_many`.

## Choices to make the comparison fair

- Both databases have the same rules: a unique (user_id, movie_id) pair and an index on movie_id.
- The indexes exist before the insertion in both cases, and only the insertion time is measured.
- Query B groups by movie_id in both databases, and I checked that both return the same top 5 movies in the same order.
- Each query is run once as a warm-up and then 10 times, and the average is reported. Load times are the mean of 3 runs.

## Week 1 results

| Metric | PostgreSQL | MongoDB |
|---|---|---|
| Load time, mean of 3 runs (s) | 1.27 | 0.66 |
| Query A: one user's ratings (ms) | 0.32 | 0.86 |
| Query B: top 5 movies by average rating (ms) | 18.19 | 40.13 |

MongoDB loaded the data about twice as fast. A possible reason is that PostgreSQL also checks the foreign keys and the rating limits for every row, but I did not test this. PostgreSQL was 2 to 3 times faster in both queries. For Query B, I think the main cost in MongoDB is grouping all 100,836 ratings, but I did not test this either.
