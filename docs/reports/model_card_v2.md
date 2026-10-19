# Model card: `sasrec-content-v1` (+ popularity hybrid)

| | |
|---|---|
| **Owner** | Member 1 (Savora GC1) |
| **Version** | `sasrec-content-v1`; served as the hybrid `sasrec-content-v1+pop8` |
| **Artifact** | `Data/models/sasrec_content.pt` (git-ignored, about 190 MB; rebuilt by one command) |
| **Code** | `apps/ai_system/src/savora_ai/core/recommendation/torch_model.py`, `ranking.py` |
| **Design** | `docs/adr/0004-transformer-ranking.md` |
| **Evaluation** | `docs/reports/ranking_evaluation_report.md` |

## Intended use

- **Task:** order candidate recipes or meals that Member 2's Rule Engine has **already
  found eligible**, for one user, from that user's liked seed dishes (onboarding).
- **Callers:** `rank_recipes` (standalone craving) and `rank_combinations` (weekly
  planning, before the CSP).
- **Output:** a rank and a relative score (a softmax within the candidate set).

## Not intended for

- Deciding whether a dish is safe, allowed or suitable. The model never sees rules,
  allergens or clinical facts.
- Estimating nutrition, portions or health effects. Scores are not calibrated.
- Users without seed dishes: there it is never used, and popularity is used, labelled
  `fallbackReason: NO_HISTORY`.
- Inventing or scoring IDs outside the supplied candidate list.

## Model

```
item vector  v(i) = [i seen in training] * E_id[i] + mean(E_tag[tags]) + mean(E_ingredient[ingredients])
user state   h    = 2-layer causal self-attention over the last 50 item vectors + positions
score(i)          = h . v(i) + b(i)              (b: learned bias, 0 for unseen items)
hybrid            = score(i) + 8 * log(1 + training interactions of i)
```

- Size: 64 dimensions, 2 heads, 2 layers, dropout 0.2. 231,637 items, of which 205,965
  have an ID vector; 551 tags; 3,000 ingredients.
- Training: next-item prediction at every position of training-period sequences;
  sampled softmax over 1,024 shared negatives drawn from 0.8 popularity^0.75 + 0.2
  uniform, with **logQ correction**; AdamW, lr 1e-3; early stopping on validation HR@10
  (best epoch 5 of 8). Seed 7, CPU, about 3 minutes.

## Data

- Food.com `RAW_interactions.csv`: 1,132,367 reviews from 2000 to 2018. Training uses
  interactions **before 2012-01-01** only (906,736 from 125,871 users).
- Every interaction counts as implicit positive engagement, whatever its rating. These
  are reviews, not meals eaten.
- Recipe features: Food.com tags and ingredient names (`RAW_recipes.csv`).

## Performance (test 2013+, full ranking over 231,637 recipes, 9,200 users)

| | HR@10 | NDCG@10 | MRR |
|---|---|---|---|
| Popularity baseline | 1.91% | 0.0091 | 0.0085 |
| Model alone (3 seeds) | 1.56% +/- 0.03 | 0.0074 | 0.0070 |
| **Hybrid, as served (3 seeds)** | **1.94% +/- 0.06** | **0.0094** | **0.0089** |

The hybrid ties popularity (paired bootstrap 95% interval for HR@10: [-0.02, +0.11]
points). Within the 164-dish catalogue: hybrid 69.7% vs popularity 70.6% HR@10, also a
tie. The model alone is significantly below popularity.

## Known limitations and risks

- **No accuracy gain over popularity** on this data. With a median history of one item,
  sequence learning has little to work with; ID embeddings add nothing measurable.
- **Popularity bias:** the hybrid strongly favours popular recipes, so long-tail and
  regional (for example Nepali) dishes rank lower unless the seed dishes pull them up.
  Their low interaction counts reflect Food.com's user base, not their quality.
- **Distribution shift:** Food.com users are mostly North American and active in
  2000-2011; Savora targets Asian cuisines and real meals.
- **Cold recipes** (never reviewed) are placed by content only and never reach the top 10
  in full ranking.
- **Seed history** in the product (3 to 5 chosen dishes) differs from review histories;
  this has not been evaluated, because no such data exists.

## Safety properties (tested)

- Only supplied candidate IDs are scored (`test_ranking_api.py`, `test_trained_model.py`).
- Missing model, missing torch or no usable history gives an explicit, labelled popularity
  fallback, never a silent switch.
- Checkpoints load with `weights_only=True` (no arbitrary code on load).
- Deterministic: the same inputs give the same scores; seed 7 reproduced exactly.
- Explanations never call a ranking a rating or a health estimate (`test_explanations.py`).

## How to retrain and re-evaluate

```
cd apps/ai_system
uv run --extra ml python -m savora_ai.core.recommendation.torch_model \
    --interactions ../../Data/Food.com/RAW_interactions.csv \
    --recipes ../../Data/Food.com/RAW_recipes.csv \
    --output ../../Data/models/sasrec_content.pt --device cpu
uv run --extra ml python -m savora_ai.core.recommendation.evaluate \
    --interactions ../../Data/Food.com/RAW_interactions.csv \
    --recipes ../../Data/Food.com/RAW_recipes.csv \
    --model ../../Data/models/sasrec_content.pt --output ../../docs/eval/ranking_evaluation.json
```
