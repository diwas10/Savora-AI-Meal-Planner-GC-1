# Ranking evaluation report v1 (Member 1): Transformer vs baselines

> **Superseded** by `ranking_evaluation_report_v2.md` (`sasrec-content-v2`, 19 Oct 2026).
> Kept unchanged as the record of v1 for the final report.

- **Date:** 19 Oct 2026
- **Raw results:** `docs/eval/v1/model_experiments.json` (seeds, ablations, bootstrap, catalogue
  and meal analyses) and `docs/eval/v1/ranking_evaluation.json` (baselines and shipped model)
- **Reproduce** (from `apps/ai_system`, needs the `ml` extra; about 90 minutes on a laptop CPU):
  `uv run --extra ml python -m savora_ai.core.recommendation.experiments --interactions
  ../../Data/Food.com/RAW_interactions.csv --recipes ../../Data/Food.com/RAW_recipes.csv
  --catalogue-dir ../../Data/catalogue --output ../../docs/eval/v1/model_experiments.json`
- **Design:** ADR 0004. Model card: `model_card_v1.md`.

## 1. Bottom line

1. **The Transformer alone is significantly worse than popularity** at predicting a
   user's next Food.com review: HR@10 1.56% +/- 0.03 (3 seeds) vs 1.91%. The paired
   bootstrap interval for the difference, [-0.62, -0.16] points, excludes zero.
2. **The hybrid** (model + w x log popularity, w chosen on validation) **ties popularity**:
   1.94% +/- 0.06 vs 1.91%; difference +0.04 points, 95% interval [-0.02, +0.11]. NDCG
   and MRR lean positive, but not significantly (13.7%, 5.3% and 8.3% of resamples at or
   below zero for HR@10, NDCG@10 and MRR).
3. **In the product's real task**, ranking the 164 catalogue dishes, popularity and the
   hybrid are again tied (70.6% vs 69.7% HR@10, interval [-2.6, +0.9] points). The
   hybrid's MRR is marginally higher (+0.21 points, interval [0.00, +0.46]).
4. **What the model does add:** personal ordering from a user's seed dishes, 22 times more
   distinct recipes shown than popularity, and a content-based placement for new recipes
   (median rank 85k vs popularity's 220k).
5. **Decision:** ship the hybrid (ADR 0004). The reported accuracy claim is "matches a
   strong popularity baseline", not "beats it".

## 2. Protocol (why the numbers are honest)

| Choice | Why |
|---|---|
| One global time split: train < 2012, validation 2012, test 2013+ | no future interaction can reach training; popularity uses the same cutoff |
| One case per user: the first interaction in the period; history = everything before | realistic next-item prediction |
| **Full ranking** over all 231,637 recipes, history excluded | ranking against 100 sampled items inflates HR@10 several-fold and can reorder models |
| Ties broken by training popularity, then ID (baselines); strict count (model) | a model that knows nothing degrades to popularity, not to an arbitrary order |
| Hybrid weight from {0, 0.5, 1, 2, 4, 8, 16} on **validation** HR@10 only | test is scored once per run |
| 3 seeds for the main model; paired bootstrap (1,000 resamples) on test | separates real differences from noise |

Data: 906,736 training interactions from 125,871 users, with a **median history of 1**.
Validation has 6,883 cases and test 9,200; 1,284 test targets (14%) are recipes never seen
in training.

## 3. Full-catalogue results (test, 9,200 users)

| Model | HR@10 | NDCG@10 | MRR | Coverage@10 |
|---|---|---|---|---|
| Popularity | 1.91% | 0.0091 | 0.0085 | 0.01% |
| Markov (last item to next) | 0.90% | 0.0042 | 0.0050 | 2.41% |
| Item-kNN (co-occurrence cosine) | 0.15% | 0.0009 | 0.0016 | 6.47% |
| SASRec + content, 3 seeds | 1.56% +/- 0.03 | 0.0074 +/- 0.0006 | 0.0070 +/- 0.0008 | 0.22% |
| **Hybrid, 3 seeds** | **1.94% +/- 0.06** | **0.0094 +/- 0.0002** | **0.0089 +/- 0.0001** | 0.01% |

Per seed, the hybrid weight chosen on validation was 8 (seed 7), 4 (seed 11) and 1
(seed 13). The flat validation curve (seed 7: 2.18% at w=2, 2.22% at w=4, 2.24% at w=8,
2.19% at w=16) explains why seeds pick different weights.

### Paired bootstrap, shipped seed (7)

| Comparison | Metric | Difference | 95% interval | Resamples at or below 0 |
|---|---|---|---|---|
| model - popularity | HR@10 | -0.39 pts | [-0.62, -0.16] | 100% |
| model - popularity | MRR | -0.0020 | [-0.0031, -0.0010] | 100% |
| hybrid - popularity | HR@10 | +0.04 pts | [-0.02, +0.11] | 13.7% |
| hybrid - popularity | NDCG@10 | +0.0004 | [-0.0001, +0.0008] | 5.3% |
| hybrid - popularity | MRR | +0.0004 | [-0.0001, +0.0009] | 8.3% |

## 4. By history length (test HR@10, seed 7)

| History length | Cases | Popularity | Model | Hybrid |
|---|---|---|---|---|
| 1 | 2,177 | 1.88% | 1.84% | 1.93% |
| 2-4 | 2,098 | 2.14% | 1.57% | 2.14% |
| 5-19 | 2,515 | 2.27% | 1.91% | 2.31% |
| 20+ | 2,410 | 1.37% | 0.79% | 1.45% |

Popularity beats the model in every bucket, and the gap is widest for heavy users, whose
long histories pull the model toward niche recipes. The hybrid is at or slightly above
popularity in every bucket.

## 5. Ablations (seed 7, test)

| Variant | HR@10 | Hybrid HR@10 | Cold median rank | Catalogue HR@10 |
|---|---|---|---|---|
| full model | 1.52% | 1.96% | 85,260 | 63.2% |
| no content features | 1.49% | 1.89% | 94,665 | 68.4% |
| no ID embeddings | 1.58% | 1.78% | 83,737 | 68.4% |
| no popularity bias | 1.40% | 2.02% | 91,882 | 61.8% |

What the ablations show:

- **ID embeddings add nothing measurable** on full ranking (1.58% without vs 1.52% with).
  With a median history of 1, per-recipe IDs cannot be learned well. A content-only model
  plus popularity is a valid, simpler alternative (open item for ADR 0004).
- **Content features place cold recipes better** (median rank 85k vs 95k without them).
- **The learned bias** helps the pure model (1.52% vs 1.40%); once popularity is added
  explicitly, it no longer matters.
- All single-run differences are within about 0.1-0.2 points; only the model-vs-popularity
  gap is clearly significant.

## 6. The product's task: ranking within the catalogue

When ranking only the 164 Food.com catalogue dishes, for the 228 test cases whose target
is one of them:

| Model | HR@10 | NDCG@10 | MRR |
|---|---|---|---|
| Popularity | 70.6% | 0.338 | 0.243 |
| Model (3 seeds) | 59.2-63.2% | 0.30-0.31 | 0.21-0.24 |
| Hybrid (3 seeds) | 68.9-69.7% | 0.335-0.341 | 0.245-0.252 |

The catalogue was chosen partly by popularity, so a popularity ranking is naturally
strong inside it. The hybrid matches it, within the interval [-2.6, +0.9] points.

## 7. Meal scoring (ADR 0004 D6)

Proxy: the rank, among all 465 meals, of the best meal that contains the user's actual
next recipe (227 cases; recomputed on the 465-meal export after the preset-intent check).

| Aggregation | HR@10 | NDCG@10 | MRR |
|---|---|---|---|
| ANCHOR (shipped) | 51.5% | 0.278 | 0.222 |
| MEAN of dishes | 51.5% | 0.275 | 0.224 |
| popularity of anchor | 52.0% | 0.276 | 0.219 |

There is no practical difference, so the simpler, explainable ANCHOR rule stays. No
combination-level ground truth exists, so this is a sanity check, not a validation.

## 8. Reproducibility

- Seed 7 training and evaluation reproduced exactly across two separate runs (identical
  losses, validation HR and test metrics).
- Seed spread: model HR@10 sd 0.03 points; hybrid sd 0.06 points.
- Training stopped early: 8, 6 and 4 epochs for the three seeds (patience 3).

## 9. Limitations

- The metric is "which recipe a Food.com user reviews next", not satisfaction with a
  planned Savora meal; no such data exists in GC1.
- In the product, history is 3 to 5 onboarding seed dishes (ADR 0004 D7), which is
  shorter and different from Food.com review histories.
- A single time split; results could shift with another cutoff.
- The meal-scoring proxy is weak because there is no meal-level ground truth.
