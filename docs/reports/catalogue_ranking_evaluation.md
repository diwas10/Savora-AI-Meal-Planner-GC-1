# Transformer ranking on the product catalogue (21 October 2026)

Results: `docs/eval/v2/catalogue_evaluation.json`. Code:
`core/recommendation/catalogue_eval.py`. This uses the shipped v2 model
(`sasrec_content.pt`, hybrid weight 8.0) with no retraining, and the same split and
metrics as `ranking_evaluation_report_v2.md`.

The product ranks catalogue dishes, not all 231k Food.com recipes. This report keeps the
held-out TEST cases whose next recipe is one of the 675 Food.com dishes in catalogue
`20261020T230903Z`. There are **223 cases**, and each is scored three ways:

- **all**: ranked among all 675 catalogue dishes
- **within cuisine**: ranked only among dishes of the target's cuisine, which is what a
  strict single-cuisine profile sees, because the product filters before it ranks
- **meals**: the best meal containing the dish, ranked among all 1,673 meals

## Results

| Ranking | Ranker | HR@10 | NDCG@10 | MRR |
|---|---|---|---|---|
| all dishes | model alone | 0.444 | 0.258 | 0.214 |
| all dishes | hybrid (shipped) | 0.444 | 0.253 | 0.207 |
| all dishes | popularity | 0.448 | 0.255 | 0.208 |
| within cuisine | model alone | 0.852 | 0.614 | 0.549 |
| within cuisine | hybrid (shipped) | 0.852 | 0.617 | 0.553 |
| within cuisine | popularity | 0.852 | 0.617 | 0.553 |

Paired bootstrap, hybrid − popularity:

| Ranking | Metric | Difference | 95% interval |
|---|---|---|---|
| all dishes | NDCG@10 | −0.002 | [−0.005, 0.000] |
| within cuisine | NDCG@10 | −0.000 | [−0.006, +0.005] |
| within cuisine | HR@10 | 0.000 | [−0.018, +0.018] |

Meals, ranked among all 1,673 meals:

| Aggregation | HR@10 | NDCG@10 | MRR |
|---|---|---|---|
| MEAN | 0.432 | **0.237** | **0.188** |
| ANCHOR | 0.432 | 0.223 | 0.171 |
| popularity of the anchor | 0.432 | 0.224 | 0.173 |

The previous 186-dish catalogue gave hybrid NDCG@10 0.339 against 0.338 for popularity.

## What this means

1. **The shipped hybrid ties popularity on the catalogue.** This holds across all
   dishes, within one cuisine, and on meals. It matches the full-corpus v2 result. With a
   weight of 8.0 the popularity term decides almost every ordering, so the hybrid
   behaves like popularity with a tie-breaker.
2. **The model alone is not worse than popularity** (NDCG@10 0.258 against 0.255 on all
   dishes). The Transformer is therefore a safe, defensible ranker, but this data does
   not show a gain over popularity.
3. **MEAN aggregation is better than ANCHOR for meals** (+0.014 NDCG@10). Taking the mean
   of component scores is the better default for ranking meal combinations.
4. **The test set is thin and skewed.** Mexican has 63 cases, Italian 41, American 25 and
   Japanese 18, while most of the new cuisines have 1 to 11. Ranked among all dishes,
   small cuisines never reach the top 10 for either ranker. Food.com users rarely cook
   these recipes, so the dataset cannot show a per-cuisine difference.

## Options (Member 1 decision; none is needed for GC1 to work)

- Keep the shipped hybrid. It is honest and safe, and the report can state that it ties
  popularity.
- Use the model alone (weight 0) for catalogue ranking. It ties popularity statistically
  and gives more personalised orderings, which the explanations can describe.
- Retrain with catalogue-aware validation, choosing the weight on catalogue cases. With
  223 test cases (and fewer validation cases) the interval would stay wide, so this is
  unlikely to change the conclusion.

## Decision (2026-10-23)

**Keep the shipped hybrid (weight 8.0) and ANCHOR aggregation for GC1.** The hybrid is
safe and the report states that it ties popularity. MEAN aggregation has a higher point
estimate on meals (NDCG@10 0.237 against 0.223) but no interval was computed, and
switching would change every plan and explanation the day before the demo. Retraining is
not expected to change the conclusion (223 test cases). Both are post-GC1 options.
