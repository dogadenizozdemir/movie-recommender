"""Top-10 recommendation quality: Precision@10 and Recall@10 for two kNN rankings and a popularity baseline."""
import numpy as np

from cf_data import load_from_postgres, load_from_mongo
from cf_preprocess import split_ratings, build_matrix
from cf_model import build_similarity, keep_top_k, MAIN_K

TOP_N = 10
RELEVANT = 4.0        # a rating of 4.0 or more counts as "the user liked this movie"
MIN_NEIGHBOURS = 3    # used only by the rating-based ranking: at least 3 neighbours must have rated the movie


def relevant_matrix(matrix, test):
    """Marks the movies each user liked in the test set (movies never seen in training are skipped)."""
    u = matrix.index.get_indexer(test["user_id"])
    i = matrix.columns.get_indexer(test["movie_id"])
    keep = (i >= 0) & (test["rating"].to_numpy() >= RELEVANT)
    rel = np.zeros(matrix.shape, dtype=bool)
    rel[u[keep], i[keep]] = True
    return rel


def top_n(scores, seen, n=TOP_N):
    """Picks the n highest-scoring movies per user, ignoring movies the user already rated."""
    s = np.where(seen, -np.inf, scores)
    top = np.argpartition(-s, n, axis=1)[:, :n]
    order = np.argsort(-np.take_along_axis(s, top, axis=1), axis=1)
    top = np.take_along_axis(top, order, axis=1)
    valid = np.take_along_axis(s, top, axis=1) > -np.inf
    return top, valid


def precision_recall(top, valid, rel):
    """Average Precision@10 and Recall@10 over the users who have at least one liked test movie."""
    hits = (np.take_along_axis(rel, top, axis=1) & valid).sum(axis=1)
    n_rel = rel.sum(axis=1)
    has_rel = n_rel > 0
    precision = float(np.mean(hits[has_rel] / TOP_N))
    recall = float(np.mean(hits[has_rel] / n_rel[has_rel]))
    return precision, recall


def knn_rating_scores(S, C, R, user_means, k=MAIN_K):
    """Ranking by the predicted rating, only for movies that enough neighbours have rated.
    The predictions are not cut off at 5.0 here, otherwise many movies would tie at exactly 5.0."""
    Sk = keep_top_k(S, k)
    support = Sk @ R
    with np.errstate(divide="ignore", invalid="ignore"):
        offset = np.where(support > 0, (Sk @ C) / support, 0.0)
    pred = user_means.to_numpy()[:, None] + offset
    n_neighbours = (Sk > 0).astype(float) @ R
    return np.where(n_neighbours >= MIN_NEIGHBOURS, pred, -np.inf)


def knn_vote_scores(S, matrix, k=MAIN_K):
    """Ranking by neighbour votes: every neighbour who liked a movie votes for it,
    and the vote counts more when the neighbour is more similar to the user."""
    liked = (matrix.fillna(0).to_numpy() >= RELEVANT).astype(float)
    votes = keep_top_k(S, k) @ liked
    return np.where(votes > 0, votes, -np.inf)


def popularity_scores(R):
    """Baseline: every user gets the movies with the most ratings in the train set."""
    return np.tile(R.sum(axis=0), (R.shape[0], 1))


if __name__ == "__main__":
    for name, loader in [("PostgreSQL", load_from_postgres), ("MongoDB", load_from_mongo)]:
        df, _ = loader()
        train, test = split_ratings(df)
        matrix, user_means, centered = build_matrix(train)
        S, C, R = build_similarity(matrix, centered)
        seen = R > 0
        rel = relevant_matrix(matrix, test)

        print(f"=== {name} === (users with at least one liked test movie: {int((rel.sum(axis=1) > 0).sum())})")
        for label, scores in [
            (f"kNN k={MAIN_K}, ranked by predicted rating", knn_rating_scores(S, C, R, user_means)),
            (f"kNN k={MAIN_K}, ranked by neighbour votes ", knn_vote_scores(S, matrix)),
            ("Popularity baseline                ", popularity_scores(R)),
        ]:
            top, valid = top_n(scores, seen)
            p, r = precision_recall(top, valid, rel)
            print(f"{label}: Precision@{TOP_N} {p:.3f}, Recall@{TOP_N} {r:.3f}")
        print()