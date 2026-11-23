"""Cleans the ratings, splits them into train and test sets and builds the user-item matrix."""
import time

import numpy as np

from cf_data import load_from_postgres, load_from_mongo

TEST_FRACTION = 0.2
SEED = 42


def check_data(df):
    """Counts missing values and duplicate (user, movie) pairs."""
    missing = int(df.isna().sum().sum())
    duplicates = int(df.duplicated(["user_id", "movie_id"]).sum())
    return missing, duplicates


def split_ratings(df):
    """Puts 20% of every user's ratings into the test set, so each user appears in both sets."""
    # Sorting first makes the split identical no matter which database the rows came from.
    df = df.sort_values(["user_id", "movie_id"]).reset_index(drop=True)
    test = df.groupby("user_id").sample(frac=TEST_FRACTION, random_state=SEED)
    train = df.drop(test.index)
    return train.reset_index(drop=True), test.reset_index(drop=True)


def build_matrix(train):
    """Builds the user-item matrix (rows = users, columns = movies, NaN = not rated)
    and a mean-centered copy of it (each user's average rating is subtracted)."""
    matrix = train.pivot(index="user_id", columns="movie_id", values="rating")
    user_means = matrix.mean(axis=1)
    centered = matrix.sub(user_means, axis=0)
    return matrix, user_means, centered


def rmse(actual, predicted):
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def mae(actual, predicted):
    return float(np.mean(np.abs(actual - predicted)))


def baseline_scores(train, test, user_means):
    """Scores two very simple predictors that the real model has to beat."""
    actual = test["rating"].to_numpy()
    global_pred = np.full(len(test), train["rating"].mean())
    user_pred = test["user_id"].map(user_means).to_numpy()
    return {
        "Baseline (global mean)": (rmse(actual, global_pred), mae(actual, global_pred)),
        "Baseline (user mean)  ": (rmse(actual, user_pred), mae(actual, user_pred)),
    }


if __name__ == "__main__":
    for name, loader in [("PostgreSQL", load_from_postgres), ("MongoDB", load_from_mongo)]:
        df, read_time = loader()
        missing, duplicates = check_data(df)

        start = time.perf_counter()
        train, test = split_ratings(df)
        matrix, user_means, centered = build_matrix(train)
        prep_time = time.perf_counter() - start

        density = matrix.notna().sum().sum() / matrix.size * 100
        print(f"=== {name} ===")
        print(f"Missing values: {missing} | duplicate (user, movie) pairs: {duplicates}")
        print(f"Train: {len(train)} ratings | Test: {len(test)} ratings")
        print(f"User-item matrix: {matrix.shape[0]} users x {matrix.shape[1]} movies ({density:.2f}% filled)")
        print(f"Preparation time (split + matrix): {prep_time:.3f} s")
        for label, (r, m) in baseline_scores(train, test, user_means).items():
            print(f"{label}: RMSE {r:.3f}, MAE {m:.3f}")
        print()