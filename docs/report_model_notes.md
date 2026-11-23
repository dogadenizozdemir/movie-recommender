# Notes for the report: how the data structure affects the model

These notes use the numbers in `docs/week2_results.md`. All timings were measured on one laptop with both databases running in Docker, so they only show how the two databases behave on this small dataset.

## What the model needs

The model needs one flat list of (user, movie, rating) triples, which it turns into a user-item matrix. Both databases can deliver this. In PostgreSQL I read it with one SQL query (`SELECT user_id, movie_id, rating FROM ratings`). In MongoDB I use a `find` query on the `ratings` collection and keep only the three fields I need. After this step the data is in the same pandas DataFrame, and I checked that the two DataFrames are identical.

## Effect on model performance

There is no effect on the quality of the model. RMSE, MAE, Precision@10 and Recall@10 are exactly the same for PostgreSQL and MongoDB, and the final top-10 lists are the same too. This is expected: the algorithm only sees the DataFrame, and the DataFrame is the same. The data structure decides how the data is stored and read, not what the model learns.

## Effect on data processing time

| Step | PostgreSQL | MongoDB |
|---|---|---|
| Read all 100,836 ratings (s) | 0.084 | 0.125 |
| Split and build the matrix (s) | 0.045 | 0.047 |
| Write 6,100 recommendations (s) | 0.113 | 0.055 |
| Read back one user's top-10 list (ms) | 0.163 | 0.209 |

- **Reading the ratings:** PostgreSQL was faster. A possible reason is that the ratings are already one flat table in PostgreSQL, while MongoDB returns 100,836 separate documents that Python has to unpack first. I did not test this.
- **Preparing the data:** the times are almost the same, because this step runs in pandas and does not depend on the database.
- **Writing the recommendations:** MongoDB was faster. A possible reason is that PostgreSQL checks the primary key and two foreign keys for every row, while MongoDB only checks one unique index. I did not test this either. The MongoDB time also includes reading the movie titles.
- **Reading one list back:** I expected MongoDB to win because the titles are stored inside the user's document, so no JOIN is needed. PostgreSQL was still slightly faster (0.163 ms against 0.209 ms). Both are far below one millisecond, so a user would not notice the difference.

## Design differences

In PostgreSQL the recommendations are stored as one row per movie, and each title is stored only once in the `movies` table. The database checks that every user and movie exists, and a movie title can be changed in one place. In MongoDB one document holds the whole list of a user, which matches how the list is shown on screen. The price is that each title is copied into every document that recommends it, so a changed title would have to be updated in many documents.

## Limits of these results

The dataset is small (about 100 thousand ratings), the databases run in Docker on one machine, and the differences are fractions of a second. I cannot say from these results which database would be better for a much larger system.