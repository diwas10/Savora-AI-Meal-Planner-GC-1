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

## Results, v1 (18 Oct 2026, `docs/eval/v1/ranking_evaluation.json`)

Test (2013+), 9,200 users, full ranking: popularity HR@10 1.91%, Markov 0.90%, item-kNN
0.15%, SASRec + content 1.52%, hybrid (model + 8 log(1 + count), weight chosen on
validation only) 1.96%. The model alone does not beat popularity; the hybrid ties it
(standard error about 0.14 points) with slightly better MRR. Popularity wins in every
history-length bucket. On cold targets the content tower gives median rank 85k versus
popularity's 220k. **Decision:** the ranking API uses the hybrid (`TorchScorer` with
training counts); without the model it falls back to popularity, explicitly.

**Confirmed with 3 seeds and a paired bootstrap (19 Oct 2026,
`docs/eval/v1/model_experiments.json`):** model alone 1.56% +/- 0.03 HR@10, significantly
below popularity (difference -0.39 points, 95% interval [-0.62, -0.16]); hybrid 1.94% +/-
0.06, tied with popularity (+0.04 points, interval [-0.02, +0.11]). Within the 164-dish
catalogue (the product's task): hybrid 69.7% vs popularity 70.6% HR@10, tied. Ablations:
removing ID embeddings changes nothing measurable (1.58%), removing content features
worsens cold placement (median rank 95k vs 85k). Meal scoring: ANCHOR, MEAN and
popularity-anchor give the same proxy HR@10 (about 51%), so ANCHOR stays. Full write-up:
`docs/reports/ranking_evaluation_report_v1.md`.

## Revision v2: faster training and a better model alone (19 Oct 2026)

`sasrec-content-v2` replaces v1 (report `docs/reports/ranking_evaluation_report_v2.md`, raw
results `docs/eval/v2/`; v1's are kept in `docs/eval/v1/`). The architecture, data, split, objective and ranking API
are unchanged; v1 checkpoints are refused on load (retrain with the one command).

**Accuracy.** v1 trained at lr 1e-3 and stopped early on a 3,000-case validation sample.
Its validation peaked at epoch 1 or 2 while training loss kept falling: the per-recipe
ID embeddings memorised training sequences. Changes, each measured on the whole
validation period (6,883 cases) before test was scored once:

| Change | Why |
|---|---|
| lr 1e-4 (was 1e-3) | validation climbs for several epochs to a higher peak instead of decaying after one; v1's code at 1e-4 alone gets the same gain, so this is the main cause |
| tag/ingredient tables at lr 3e-4 | at 1e-4 the shared content tables barely learn: Indian dishes' nearest neighbours fall to chance (1.6x base rate). 3e-4 gives 15.6x (v1: 6x) at equal validation accuracy |
| early stopping on every validation case, by the model alone (NDCG@10) | a 3,000-case sample is noisy, and the hybrid's validation curve is too flat to choose an epoch; the model alone is what ranks recipes without counts (curated dishes) |
| hybrid weight chosen for that epoch on validation, stored in the checkpoint | `TorchScorer` no longer hard-codes w = 8 |

Test (2013+, shipped seed 7): model alone HR@10 1.52% -> 1.91%, NDCG@10 0.0070 ->
0.0093, MRR 0.0065 -> 0.0089, now equal to popularity (1.91%, 0.0091, 0.0085). The
hybrid is unchanged within noise (1.96% -> 1.93% HR@10). Over 3 seeds the model alone
gives 1.95% +/- 0.06 HR@10 (v1: 1.56% +/- 0.03); the paired bootstrap against
popularity, [-0.19, +0.20] points, is now a tie where v1 was significantly below. The
v1 learning rate in the v2 pipeline gives 1.74%. Trade-off: the model alone's top-10
lists cover 0.03% of recipes (v1: 0.22%).

**Tried and not adopted** (no validation gain, so not kept): training on every window of
long sequences (2x targets), a recipe-author embedding (also no better for cold
recipes), down-weighting same-day targets (a third of training targets are same-day bulk
reviews, while 83% of validation cases follow a gap of over 90 days), a popularity prior
inside the training logits (the model alone becomes useless for recipes without counts),
dropout 0.5, weight decay 0.1, 4,096 negatives and 128 dimensions.

**Speed.** Batches are trimmed to their longest sequence (positions count from the end,
so trimming never changes a state) and grouped by length; tag/ingredient means use
`EmbeddingBag`; evaluation ranks a whole batch at once on the device. One epoch is 15 s
on a laptop CPU (v1: 22 s), the full experiment suite (7 runs) 20 minutes (v1: 91 minutes
for 6), and `TorchScorer` precomputes item vectors once at load: 0.5 ms median per
request (v1: 1.1 ms).

## Consequences

- Metrics measure Food.com next-review prediction, not meal satisfaction; reported so.
- With median history 1, gains over Markov or popularity may be small; the report must
  show the baselines next to the model.
- The backend needs the `ml` extra to use the trained model; without it the ranking
  falls back, explicitly.

## Open items

0. ~~A content-only model plus popularity matches the full model (ID embeddings add
   nothing on this data).~~ True for v1 only, whose ID embeddings were overfitted. For v2
   they matter: without them the model alone falls from 1.91% to 0.24% HR@10 (Revision
   v2, ablations). A content-only model is no longer a smaller equivalent.

1. Onboarding seed dishes (Member 3, team): proposed in ADR 0005 D1.
2. Whether the trained model file is shipped with the backend or loaded from storage:
   proposed in ADR 0005 D2.
3. Final cutoff dates, shared with the popularity cutoff.
