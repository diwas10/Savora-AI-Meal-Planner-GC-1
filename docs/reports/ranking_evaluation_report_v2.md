# Ranking evaluation report v2 (Member 1): Transformer vs baselines

- **Version:** `sasrec-content-v2` (supersedes v1: `ranking_evaluation_report_v1.md`)
- **Date:** 19 Oct 2026
- **Raw results:** `docs/eval/v2/model_experiments.json` (seeds, ablations, bootstrap,
  catalogue and meal analyses), `docs/eval/v2/ranking_evaluation.json` (baselines and
  shipped model) and `docs/eval/v2/training_report.json` (shipped model's epochs). v1's
  raw results are kept unchanged in `docs/eval/v1/`.
- **Reproduce** (from `apps/ai_system`, needs the `ml` extra; about 20 minutes on a laptop
  CPU, v1: 91 minutes): `uv run --extra ml python -m
  savora_ai.core.recommendation.experiments --interactions
  ../../Data/Food.com/RAW_interactions.csv --recipes ../../Data/Food.com/RAW_recipes.csv
  --catalogue-dir ../../Data/catalogue --output ../../docs/eval/v2/model_experiments.json`
- **Design:** ADR 0004 ("Revision v2"). Model card: `model_card_v2.md`.

## 1. Bottom line

1. **The Transformer alone now ties popularity** at predicting a user's next Food.com
   review: HR@10 1.95% +/- 0.06 (3 seeds) vs 1.91%; paired bootstrap interval for the
   difference [-0.19, +0.20] points. v1 alone was significantly worse (1.56% +/- 0.03,
   interval [-0.62, -0.16]). NDCG@10 and MRR improve by about a quarter over v1.
2. **The hybrid** (model + w x log popularity, w chosen on validation) **still ties
   popularity**: 1.99% +/- 0.07 vs 1.91%, interval [-0.04, +0.09] points.
3. **In the catalogue** (the product's task), all three tie on HR@10 (70.2-71.1% model,
   67.5-70.6% hybrid, 70.6% popularity); the hybrid's NDCG@10 is marginally higher than
   popularity's (+0.0004, interval [+0.0001, +0.0008]).
4. **Why it matters:** recipes without training counts (curated dishes, new recipes) are
   ranked by the model alone, which v1 did worse than popularity and v2 does as well.
5. **Cost:** v2's model alone is less diverse: its top-10 lists cover 0.03% of recipes
   (v1: 0.22%).

## 2. What changed from v1

Architecture, data, split, objective, metrics and baselines are identical to v1
(section 2 of the v1 report). v1 trained at lr 1e-3 and stopped on a 3,000-case
validation sample; its validation peaked at epoch 1-2 while training loss kept falling
(ID embeddings memorised training sequences).

| Change | Evidence (validation only) |
|---|---|
| lr 1e-4 | v1's own code at 1e-4: model-alone validation HR@10 2.21% vs 1.54% |
| tag/ingredient tables at lr 3e-4 | at 1e-4, Indian dishes' 20 nearest neighbours are Indian at 1.6x chance; at 3e-4, 15.6x (v1: 6x), same validation accuracy |
| early stopping on all 6,883 validation cases, by the model alone (NDCG@10) | the hybrid curve is flat within noise across epochs; the model alone has a clear peak |
| hybrid weight chosen for that epoch on validation and stored in the checkpoint | v1 hard-coded w = 8 |

Tried and not adopted (no validation gain): every window of long sequences (2x training
targets), a recipe-author embedding, down-weighting same-day bulk-review targets, a
popularity prior inside the training logits, dropout 0.5, weight decay 0.1, 4,096
negatives, 128 dimensions.

## 3. Full-catalogue results (test, 9,200 users)

| Model | HR@10 | NDCG@10 | MRR | Coverage@10 |
|---|---|---|---|---|
| Popularity | 1.91% | 0.0091 | 0.0085 | 0.01% |
| Markov (last item to next) | 0.90% | 0.0042 | 0.0050 | 2.41% |
| Item-kNN (co-occurrence cosine) | 0.15% | 0.0009 | 0.0016 | 6.47% |
| SASRec + content v1, 3 seeds | 1.56% +/- 0.03 | 0.0074 +/- 0.0006 | 0.0070 +/- 0.0008 | 0.22% |
| **SASRec + content v2, 3 seeds** | **1.95% +/- 0.06** | **0.0094 +/- 0.0002** | **0.0089 +/- 0.0001** | 0.03% |
| Hybrid v1, 3 seeds | 1.94% +/- 0.06 | 0.0094 +/- 0.0002 | 0.0089 +/- 0.0001 | 0.01% |
| Hybrid v2, 3 seeds | 1.99% +/- 0.07 | 0.0093 +/- 0.0004 | 0.0086 +/- 0.0003 | 0.01% |

Hybrid weights chosen on validation: 8 (seed 7, shipped), 0.5 (seed 11), 2 (seed 13).

### Paired bootstrap, shipped seed (7), 1,000 resamples

| Comparison | Metric | Difference | 95% interval | Resamples at or below 0 |
|---|---|---|---|---|
| model - popularity | HR@10 | 0.00 pts | [-0.19, +0.20] | 51% |
| model - popularity | NDCG@10 | +0.0002 | [-0.0007, +0.0012] | 28% |
| model - popularity | MRR | +0.0004 | [-0.0005, +0.0013] | 22% |
| hybrid - popularity | HR@10 | +0.02 pts | [-0.04, +0.09] | 32% |
| hybrid - popularity | NDCG@10 | -0.0001 | [-0.0004, +0.0003] | 64% |
| hybrid - popularity | MRR | -0.0001 | [-0.0005, +0.0003] | 71% |

## 4. By history length (test HR@10, seed 7)

| History length | Cases | Popularity | Model v1 | Model v2 | Hybrid v2 |
|---|---|---|---|---|---|
| 1 | 2,177 | 1.88% | 1.84% | 2.07% | 1.93% |
| 2-4 | 2,098 | 2.14% | 1.57% | 2.14% | 2.05% |
| 5-19 | 2,515 | 2.27% | 1.91% | 2.19% | 2.35% |
| 20+ | 2,410 | 1.37% | 0.79% | 1.29% | 1.41% |

v1's widest gap, heavy users (20+), shrinks from 0.58 to 0.08 points.

## 5. Ablations (seed 7, test)

| Variant | Model HR@10 | Hybrid HR@10 | Cold median rank | Catalogue HR@10 (model) |
|---|---|---|---|---|
| full v2 model | 1.91% | 1.93% | 88,924 | 70.2% |
| v1 learning rate (1e-3) | 1.74% | 1.91% | 117,839 | 71.5% |
| no ID embeddings | 0.24% | 1.87% | 108,340 | 57.9% |
| no content features | 1.89% | 1.90% | 50,173 * | 69.7% |
| no popularity bias | 1.90% | 1.93% | 89,360 | 70.2% |

- The **learning rate** is the main cause of v2's gain (1.74% at v1's rate).
- **ID embeddings now matter** (0.24% without them); in v1 they added nothing, because
  they were overfitted.
- **Content features** do not change top-10 accuracy but separate cuisines and place
  curated and cold recipes. *Without content every unseen recipe scores exactly 0, and
  ties favour the target, so that cold median rank is a tie artefact, not an improvement.
- The **learned bias** no longer matters (1.90% without it).

## 6. The product's task: ranking within the catalogue

164 Food.com catalogue dishes; 228 test cases whose target is one of them.

| Model | HR@10 | NDCG@10 | MRR |
|---|---|---|---|
| Popularity | 70.6% | 0.338 | 0.243 |
| Model v1 (3 seeds) | 59.2-63.2% | 0.30-0.31 | 0.21-0.24 |
| Model v2 (3 seeds) | 67.1-71.1% | 0.342-0.347 | 0.249-0.260 |
| Hybrid v2 (3 seeds) | 67.5-70.6% | 0.331-0.345 | 0.243-0.254 |

## 7. Meal scoring (ADR 0004 D6)

Proxy: the rank, among all 465 meals, of the best meal containing the user's actual next
recipe (227 cases).

| Aggregation | HR@10 | NDCG@10 | MRR |
|---|---|---|---|
| ANCHOR (shipped) | 52.0% | 0.276 | 0.219 |
| MEAN of dishes | 51.1% | 0.273 | 0.222 |
| popularity of anchor | 52.0% | 0.276 | 0.219 |

No practical difference; ANCHOR stays.

## 8. Speed (laptop CPU, Apple M3 Pro)

| | v1 | v2 |
|---|---|---|
| Training epoch | 22 s | 15 s |
| Shipped model, train to early stop | about 3 min (8 epochs) | about 3 min (11 epochs) |
| Whole experiment suite | 91 min (6 runs) | 20 min (7 runs) |
| Ranking request (4 seed dishes, 164 candidates), median / p95 | 1.1 / 3.1 ms | 0.5 / 1.3 ms |

How: batches are trimmed to their longest sequence (positions count from the end, so
trimming never changes a state; tested) and grouped by length; tag/ingredient means use
`EmbeddingBag`; evaluation ranks a whole batch at once; `TorchScorer` computes item
vectors once at load (about +0.3 s and 59 MB).

## 9. Reproducibility

- Seed 7 in the experiment suite reproduces the separately trained shipped model exactly
  (CPU).
- Seed spread: model HR@10 sd 0.06 points; hybrid sd 0.07 points.
- Early stopping (patience 3) chose epochs 8, 9 and 6 of 11, 12 and 9.

## 10. Limitations

- Unchanged from v1: the metric is "which recipe a Food.com user reviews next", not
  satisfaction with a planned meal; product histories are 3 to 5 onboarding seed dishes;
  one time split; the meal-scoring proxy has no meal-level ground truth.
- v2's model alone recommends a narrower set of recipes than v1 (coverage 0.03% vs
  0.22% of recipes; intra-list diversity 0.69 vs 0.72).
