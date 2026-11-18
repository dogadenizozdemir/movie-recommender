DROP TABLE IF EXISTS ratings;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS movies;

CREATE TABLE movies (
    movie_id INTEGER PRIMARY KEY,
    title    TEXT NOT NULL,
    genres   TEXT
);

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY
);

CREATE TABLE ratings (
    rating_id SERIAL PRIMARY KEY,
    user_id   INTEGER NOT NULL REFERENCES users(user_id),
    movie_id  INTEGER NOT NULL REFERENCES movies(movie_id),
    rating    NUMERIC(2,1) NOT NULL CHECK (rating >= 0.5 AND rating <= 5.0),
    rated_at  TIMESTAMP,
    CONSTRAINT uq_ratings_user_movie UNIQUE (user_id, movie_id)
);

-- The UNIQUE constraint above already creates an index that starts with user_id,
-- so a separate user_id index is not needed.
CREATE INDEX idx_ratings_movie ON ratings(movie_id);
