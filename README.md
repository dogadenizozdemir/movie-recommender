# Movie Recommender: PostgreSQL vs MongoDB

This is my project for the Database course. I am building a movie recommendation system and comparing PostgreSQL and MongoDB. The machine learning model reads its data directly from the database, and the model results are written back to the database.

## Dataset

I use the MovieLens latest-small data from Kaggle ("Popular Movies Datasets - 9742 Movies"). It has 9,742 movies and 100,836 ratings. The CSV files are not stored in this repository (see .gitignore). To run the project, download the dataset from Kaggle and put links.csv, movies.csv, ratings.csv and tags.csv into the data/ folder.

## Project structure

- docker-compose.yml: PostgreSQL 16 and MongoDB 7 containers
- sql/schema.sql: PostgreSQL tables and indexes
- src/load_postgres.py: loads the CSV data into PostgreSQL
- src/load_mongo.py: loads the CSV data into MongoDB
- src/check_data.py: checks the row counts and compares query times
- data/: dataset files (not uploaded)
- docs/: report notes and diagrams

## Quick start

Python packages needed: pandas, psycopg2-binary, pymongo.

    docker compose up -d
    docker exec -i movie_postgres psql -U movie_user -d movie_db < sql/schema.sql
    python src/load_postgres.py
    python src/load_mongo.py
    python src/check_data.py

## Status

Work in progress. The databases are set up and the data is loaded. The recommendation model and the evaluation will be added next.
