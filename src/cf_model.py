"""User-based kNN collaborative filtering: trains on the train set and scores the test set."""
import time

import numpy as np

from cf_data import load_from_postgres, load_from_mongo
from cf_preprocess import split_ratings, build_matrix, rmse, mae, baseline_scores

SHRINK = 10          # similarities based on few shared movies are weakened
K_VALUES = [10, 20, 50, 100]
MAIN_K = 50          # the neighbourhood size we use for the final recommendations


def build_similarity(matrix, centered):
    """Cosine similarity between users, computed on mean-centered ratings."""
    C = centered.fillna(0).to_numpy()              # mean-centered ratings, 0 = not rated
    R = matrix.notna().to_numpy().astype(float)    # 1 = rated, 0 = not rated
    norms = np.sqrt((C ** 2).sum(axis=1))
    norms[norms == 0] = 1.0
    S = (C @ C.T) / np.outer(norms, norms)
    common = R @ R.T                               # number of movies two users both rated
    S = S * common / (common + SHRINK)
    np.fill_diagonal(S, 0.0)                       # a user is not their own neighbour
    return S, C, R


def keep_top_k(S, k):
    """Keeps only the k most similar neighbours of every user (positive similarities only)."""
    Sk = np.zeros_like(S)
    top = np.argsort(-S, axis=1)[:, :k]
    rows = np.arange(S.shape[0])[:, None]
    Sk[rows, top] = S[rows, top]
    Sk[Sk < 0] = 0.0
    return Sk


def predict_all(Sk, C, R, user_means):
    """Predicts a rating for every user and movie.
    prediction = user's own mean + weighted average of the neighbours' deviations from their means."""
    numerator = Sk @ C
    support = Sk @ R                               # total similarity of the neighbours who rated the movie
    with np.errstate(divide="ignore", invalid="ignore"):
        offset = np.where(support > 0, numerator / support, 0.0)
    pred = user_means.to_numpy()[:, None] + offset
    return np.clip(pred, 0.5, 5.0)


def score_on_test(pred, matrix, user_means, test):
    """RMSE and MAE on the test ratings. Movies never seen in training fall back to the user's mean."""
    u = matrix.index.get_indexer(test["user_id"])
    i = matrix.columns.get_indexer(test["movie_id"])
    fallback = user_means.to_numpy()[u]
    predicted = np.where(i >= 0, pred[u, np.maximum(i, 0)], fallback)
    actual = test["rating"].to_numpy()
    return rmse(actual, predicted), mae(actual, predicted)


if __name__ == "__main__":
    for name, loader in [("PostgreSQL", load_from_postgres), ("MongoDB", load_from_mongo)]:
        df, read_time = loader()
        train, test = split_ratings(df)
        matrix, user_means, centered = build_matrix(train)

        start = time.perf_counter()
        S, C, R = build_similarity(matrix, centered)
        sim_time = time.perf_counter() - start

        print(f"=== {name} === (read {read_time:.3f} s, similarity matrix {sim_time:.3f} s)")
        for label, (r, m) in baseline_scores(train, test, user_means).items():
            print(f"{label}: RMSE {r:.3f}, MAE {m:.3f}")
        for k in K_VALUES:
            start = time.perf_counter()
            pred = predict_all(keep_top_k(S, k), C, R, user_means)
            pred_time = time.perf_counter() - start
            r, m = score_on_test(pred, matrix, user_means, test)
            star = "  <- our choice" if k == MAIN_K else ""
            print(f"User-based kNN, k={k:<3}: RMSE {r:.3f}, MAE {m:.3f} ({pred_time:.2f} s){star}")
        print()