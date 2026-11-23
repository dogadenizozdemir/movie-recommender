# Week 2 results: user-based kNN collaborative filtering

All numbers come from the scripts in `src/`. The model results are identical for PostgreSQL and MongoDB because both databases give the model exactly the same data. Only the timings differ.

## Data and split
- 100,836 ratings, 610 users, 9,724 rated movies (9,742 movies in total)
- 20% of every user's ratings form the test set (seed 42): 80,672 train and 20,164 test ratings
- Train user-item matrix: 610 users x 8,995 movies, 1.47% filled
- No missing values and no duplicate (user, movie) pairs

## Rating prediction on the test set
| Method | RMSE | MAE |
|---|---|---|
| Global mean | 1.050 | 0.831 |
| User mean | 0.952 | 0.740 |
| User-based kNN, k=10 | 0.953 | 0.724 |
| User-based kNN, k=20 | 0.934 | 0.708 |
| User-based kNN, k=50 (chosen before testing) | 0.910 | 0.688 |
| User-based kNN, k=100 | 0.900 | 0.680 |

## Top-10 recommendations on the test set
597 users have at least one liked test movie. "Liked" means a rating of 4.0 or higher.

| Ranking | Precision@10 | Recall@10 |
|---|---|---|
| kNN k=50, ranked by predicted rating | 0.010 | 0.009 |
| kNN k=50, ranked by neighbour votes (used) | 0.182 | 0.172 |
| Popularity baseline | 0.113 | 0.092 |

The first ranking (by predicted rating) performed badly, so we switched to neighbour votes. This change was made after seeing the first test result. The new ranking was chosen on simulated data and tried only once on the real test set.

## Timings (seconds)
| Step | PostgreSQL | MongoDB |
|---|---|---|
| Read all ratings (average of 3 runs) | 0.084 | 0.125 |
| Split + user-item matrix (one run) | 0.045 | 0.047 |
| Write recommendations (average of 3 runs) | 0.113 | 0.055 |

The model code is the same for both databases, so small differences in model time (0.377 s vs 0.356 s) are noise. The MongoDB write time includes reading the movie titles, because titles are stored inside each document.

## Recommendations written back
- PostgreSQL table `recommendations`: one row per recommended movie (6,100 rows)
- MongoDB collection `recommendations`: one document per user with the 10 movies in an embedded array (610 documents)
- The `ratings` data was not touched (100,836 rows)
- User 53 had no similar neighbours, so this user got the most popular unseen movies, marked `popularity-fallback`. The reason was not tested.

## Reading a saved top-10 list back
`src/check_recommendations.py` reads the top-10 list of one user 1,000 times per round (cycling through all 610 users). The connection is opened once, 50 warm-up queries are not counted, and the average of 3 rounds is reported.

| Database | How the list is stored | Average time per query (ms) | Rounds (ms) |
|---|---|---|---|
| PostgreSQL | 10 rows in `recommendations`, titles from `movies` with a JOIN | 0.163 | 0.166, 0.164, 0.160 |
| MongoDB | one document per user, titles stored inside | 0.209 | 0.207, 0.209, 0.211 |

Both are far below one millisecond. PostgreSQL was about 0.05 ms faster per query, so storing the titles inside the document did not make MongoDB faster here. We did not test why. The dataset is small and both databases run in Docker on the same laptop, so this result should not be generalised to larger systems.

## Limitations
- Precision and recall look low in absolute terms because the test set only holds 20% of each user's ratings, and movies a user never rated count as not relevant.
- k=50 was chosen before looking at test results. k=100 is slightly better.
- The final recommendations are trained on all ratings. The metrics come from the train/test split.
- The dataset is small and the timing differences are milliseconds, so no claims about scalability are made.