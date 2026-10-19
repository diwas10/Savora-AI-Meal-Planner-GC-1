# ADR 0004: Sequential Transformer ranking, splits, baselines and fallback

- **Status:** Proposed by Member 1 for team approval.
- **Date:** 2026-10-18
- **Owner:** Member 1 (sequential Transformer, ranking APIs, baselines)
- **Relates to:** ARCHITECTURE.md sections 7, 9.2, 13, 15; ADR 0001 D6 (popularity cutoff)

## Context

ARCHITECTURE.md section 7 asks for a compact sequential model trained on chronological
Food.com interactions with leakage-safe splits, compared with popularity, similarity and
Markov baselines on HR@K, NDCG@K, MRR and diversity. It ranks only supplied safe IDs and
falls back to content/popularity without history.

Measured on `RAW_interactions.csv` (1,132,367 interactions, 226,570 users, 2000-2018):

- Before 2012-01-01: 906,736 interactions from 125,871 users. **Median history length is
  1**; only 32,056 users have 3 or more. Sequences are short.
- 13.6% of test targets (1,255 of 9,200) are recipes never seen before the cutoff.
- 257,988 consecutive pairs share a date (bulk reviewing), so within-day order is unknown.
- Ratings: 5 is 72%; 0 (a review without a rating) is 5%.

## Decisions

### D1. One global time split, shared with popularity

| Period | Dates | Use |
|---|---|---|
| train | before 2012-01-01 | model fitting, popularity, baselines |
| validation | 2012 | early stopping and hyper-parameters |
| test | 2013 onward | reported metrics only |

An evaluation case is a user's FIRST interaction in the period; its history is every
earlier interaction (earlier periods are in the past, so using them is not leakage). The
model's weights only ever see training-period targets. The provided per-user
`interactions_train/test.csv` are not used (ADR 0001 D6). Within a day, file order is
kept; this is documented, not hidden.

### D2. Implicit feedback

Every interaction is a positive engagement signal, whatever its rating. Interactions are
not consumption: the model learns "what a Food.com user reviews next", not what anyone ate.

### D3. Model: SASRec with content features, sized for a laptop

A causal self-attention encoder over the last 50 items (2 layers, 64 dimensions, 2
heads). An item's vector = ID embedding (items with training interactions) + mean tag
embedding + mean ingredient embedding (top 3,000 ingredients). A never-seen item still
gets a content vector, which handles the 13.6% cold targets and the curated Nepali dishes.
USDA staples have no Food.com interactions or tags and are never ranked on their own.

**Training objective (found by experiment, 18 Oct 2026).** Next-item prediction at
every position, sampled softmax over the target and 1,024 shared negatives:

- *Initialisation.* With the default N(0, 1) embeddings, three summed tables give dot
  products near +/-100 and the softmax saturates (loss 23.5, validation HR@10 0 after one
  epoch). All tables start at std 0.02.
- *Negatives.* Uniform negatives are almost never popular recipes, so the model only
  learns "real target vs obscure recipe"; in full ranking, obscure recipes with matching
  tags then crowd the top 10 (validation HR@10 fell every epoch, and the model did not
  beat popularity even on its own training targets). Popularity-sampled negatives without
  correction push popular recipes down instead.
- *Fix: logQ correction* (Yi et al., 2019). Negatives come from
  q = 0.8 popularity^0.75 + 0.2 uniform and every logit is corrected by -log(K q(i)), so
  the sampled loss approximates the full-catalogue softmax that evaluation uses. In-sample
  median rank halved (5,862 vs popularity 11,095) and validation HR stopped decaying.
- A learned per-item bias (zero for unseen items) carries popularity explicitly.

### D4. Baselines and metrics

Popularity (train counts), item-kNN (co-occurrence cosine within training histories), and
first-order Markov (last item to next item). All are evaluated by **full ranking** over
every recipe (sampled-candidate metrics are known to mislead). Ties break by training
popularity, then recipe ID. Metrics: HR@10, NDCG@10, MRR, plus top-10 catalogue coverage
and intra-list tag diversity.

### D5. Ranking API and fallback

`rank_recipes(history, candidates, context)` and `rank_combinations(...)` score ONLY the
supplied safe IDs and return ranks and relative scores (ARCHITECTURE.md 9.2), never
nutrition. With no usable history, or without the model or the optional `ml` extra
(torch), they fall back to content/popularity and say so in `modelVersion`.

### D6. Combination score = anchor dish score

A meal is scored by its anchor dish (the main or breakfast base). Staples and plain sides
have no interaction data, so averaging them in would add noise. The mean over Food.com
components is reported as an ablation; no combination-level ground truth exists.

### D7. History in the product comes from onboarding seed dishes

GC1 stores no consumption or ratings, so a real user starts with no history. Onboarding
asks for 3 to 5 liked dishes (requires Member 3 and team approval); those are the only
history. Saved plans are never treated as history or positive feedback.

## Results (18 Oct 2026, `docs/eval/ranking_evaluation.json`)

Test (2013+), 9,200 users, full ranking: popularity HR@10 1.91%, Markov 0.90%, item-kNN
0.15%, SASRec + content 1.52%, hybrid (model + 8 log(1 + count), weight chosen on
validation only) 1.96%. The model alone does not beat popularity; the hybrid ties it
(standard error about 0.14 points) with slightly better MRR. Popularity wins in every
history-length bucket. On cold targets the content tower gives median rank 85k versus
popularity's 220k. **Decision:** the ranking API uses the hybrid (`TorchScorer` with
training counts); without the model it falls back to popularity, explicitly.

**Confirmed with 3 seeds and a paired bootstrap (19 Oct 2026,
`docs/eval/model_experiments.json`):** model alone 1.56% +/- 0.03 HR@10, significantly
below popularity (difference -0.39 points, 95% interval [-0.62, -0.16]); hybrid 1.94% +/-
0.06, tied with popularity (+0.04 points, interval [-0.02, +0.11]). Within the 164-dish
catalogue (the product's task): hybrid 69.7% vs popularity 70.6% HR@10, tied. Ablations:
removing ID embeddings changes nothing measurable (1.58%), removing content features
worsens cold placement (median rank 95k vs 85k). Meal scoring: ANCHOR, MEAN and
popularity-anchor give the same proxy HR@10 (about 51%), so ANCHOR stays. Full write-up:
`docs/reports/ranking_evaluation_report.md`.

## Consequences

- Metrics measure Food.com next-review prediction, not meal satisfaction; reported so.
- With median history 1, gains over Markov or popularity may be small; the report must
  show the baselines next to the model.
- The backend needs the `ml` extra to use the trained model; without it the ranking
  falls back, explicitly.

## Open items

0. A content-only model plus popularity matches the full model (ID embeddings add nothing
   on this data) and is smaller; consider it once real Savora seed-dish data exists.

1. Onboarding seed dishes (Member 3, team).
2. Whether the trained model file is shipped with the backend or loaded from storage.
3. Final cutoff dates, shared with the popularity cutoff.
