# Member 1 learning report: from raw Food.com rows to ranked meals

- **Author:** Member 1 work, 18 Oct 2026, built with Claude as pair programmer.
- **Branch:** `feat/m1-nutrition-targets` (local commits; not pushed).
- **Read with:** ADR 0001 to 0004 in `docs/adr/`, the contract note
  `docs/member1_catalogue_contract.md`, and the code paths cited below.

This report explains **what** was built, **why** each decision was made, **how** the code
works, and **what went wrong on the way**. The failures are the most useful part: each
is a lesson that transfers to other data and ML systems. Each stage ends with
"remember" points; section 14 has questions to test yourself.

---

## 1. The big picture

Savora builds a 7-day plan of 21 meals. Member 1 owns the *data* side and the *ranking*:

```
RAW_recipes.csv (231,637 rows)            RAW_interactions.csv (1.13 M reviews)
        |                                              |
  [1] quarantine defects                        [5] popularity < 2012
  [2] classify roles / meals                    [T1] chronological split
  [3] nutrition + USDA staples                  [T2] baselines
  [4] portions                                  [T3] SASRec + content
  [6] curation (Nepali, pairings)                      |
  [7] stratified selection  --> 182 dishes             |
  [8] compose 1-3 dish meals --> 446 meals             |
  [9] validate meal nutrition                          |
  [10] coverage per scenario                           |
  [11] export + --check                         [T4] rank_recipes / rank_combinations
        |                                              |
        +----------> Member 2: Rule Engine + CSP <-----+
```

The ownership line is the most important design idea in the whole project:

| Who decides | What |
|---|---|
| Member 1 (this work) | what a dish *is*, its nutrition, portions, which meals are *sensible*, ranking |
| Member 2 (Rule Engine, CSP) | whether a dish or meal is *allowed* for this user, and the final portions |
| Member 3 (backend) | storage, the user's profile, orchestration |

So Member 1's code never says "safe for a diabetic". It says "this meal has 545 kcal,
known sodium, sourced from Food.com", and the Rule Engine decides.

## 2. Principles that drove every decision

1. **Unknown is never zero.** A missing sodium value is `None`, not 0. Zero would make a
   salty dish look safe. Every sum propagates unknowns (`known + unknown = unknown`).
2. **Quarantine, don't delete.** Bad rows are kept with every reason, so a person can
   review them and nothing silently disappears.
3. **Evidence, then decision.** Tags are evidence. The classifier records *which rule
   fired*, so every label can be audited.
4. **Data as data.** Templates, pairings, staples and overrides are JSON files a reviewer
   can read, not logic hidden in code.
5. **Deterministic and reproducible.** Same inputs + seed = same output. The `--check`
   mode proves this on the real data.
6. **No leakage.** Anything used for ranking or selection comes from data *before* a
   time cutoff, so evaluation stays honest.
7. **Fail loudly.** A curation override that matches nothing, a stale USDA extract, or
   a combination cap exceeded is an *error*, never a silent no-op.

---

## 3. Stage 1: quarantine instead of rejection

**Problem.** The first builder rejected 113,693 recipes for "no meal tag". But a recipe
without a course tag is *unclassified*, not *defective*. Rejecting both kinds the same
way destroyed half the data and hid the difference.

**Decision.** Two outcomes: `CatalogueRecipe` (accepted) or `QuarantinedRow` (a data
defect, with **all** reasons). Reasons: malformed nutrition, malformed metadata,
nutrition out of range, energy inconsistent (`QuarantineReason` in `schemas/enums.py`).

**How.** `food_data/catalogue.py:69 build_recipe` collects every reason before deciding,
so one row can report both "malformed nutrition" and "malformed metadata".

**The energy-consistency check.** Food.com stores kcal and %DV. We convert %DV to grams
(Stage 3) and recompute energy with Atwater factors: `9*fat + 4*carbs + 4*protein`. If
implied / stated is outside 0.75 to 1.25, the row is suspicious. **Bug found:** for
light dishes this check is unfair. %DV is a whole number, so rounding fat, carbs and
protein by 0.5 %DV each moves implied energy by about 10 kcal (2.9 + 6.0 + 1.0). For
a 20 kcal side, 10 kcal is a 50% error. The fix (`catalogue.py:57 energy_consistent`)
also accepts any gap of 10 kcal or less.

**Remember.** Before trusting a ratio test, ask what measurement error does at small
values. Rounding noise dominates near zero.

## 4. Stage 2: roles, dish class and meal types

**Problem.** The planner needs four *separate* facts per dish:

| Attribute | Question | Example |
|---|---|---|
| cuisine | where is it from? | Indian |
| roles (several) | what does it do in a meal? | MAIN_DISH |
| dish class (one) | can it stand alone? | REQUIRES_ACCOMPANIMENT |
| meal types | which meals suit it? | LUNCH, DINNER |

The old code mapped `main-dish -> DINNER`, so dal could never be lunch.

**Data insight (the key one).** Food.com has two *kinds* of tag:

- **course** tags: what the dish is in a meal (`main-dish`, `side-dishes`, `breakfast`);
- **main-ingredient** tags: what it is made of (`vegetables`, `rice`, `pasta`).

"Vegetable soup" is tagged `vegetables` but is not a vegetable *side*. So roles come
from course tags, and ingredient tags only *qualify* a side: `side-dishes` + `rice` is
a STAPLE; `side-dishes` + `vegetables` is a VEGETABLE.

**How.** `food_data/classification.py:215 classify(name, tags, energy_kcal)` returns
roles, dish class, meal types, a status and the evidence list. Meal types are *derived
from roles* (a main suits lunch and dinner). The status is:

- `AUTO`: consistent evidence;
- `REQUIRES_REVIEW`: a conflict (`main-dish` next to `appetizers`), weak evidence
  (`soups-stews` only), no evidence, or implausible energy for the role;
- `CURATED`: a person (here: AI judgement, labelled as such) overrode it.

**Spot-checking caught three errors** in a 25-row random sample: muffins filed under
`breads` became STAPLE, a whole 1,200 kcal loaf counted as a side, and pasta salad
became VEGETABLE. Each was fixed with a rule *and* a test.

**Curated overrides.** `Data/curated/classification_overrides.json`. An override
replaces roles, class and meals together (or only cuisines) and keeps the auto evidence
for audit (`classification.py:314 apply_override`). An override for a recipe that is
not accepted fails the build.

**Result.** 213,696 accepted: 106,342 plannable, 52,151 for review, 55,213 not planning
dishes (desserts, drinks, sauces).

**Remember.** Understand what each field *means* before mapping it. A random sample
read by eye finds errors that statistics hide.

## 5. Stage 3: nutrition with provenance, and USDA staples

**Problem.** A meal mixes Food.com dishes (kcal + %DV per serving, mass unknown) with
staples like rice, which Food.com has no good record for. Two sources of different trust.

**Decisions** (ADR 0003):

- `NutritionRecord(source, basis, values, sourceReference, qualityFlags)`. Every value
  knows where it came from. `NutrientVector` fields are all optional: unknown = `None`.
- A USDA record is used **only when it is the same food** (an exact identity, chosen by a
  curated `fdcId`), never by fuzzy name matching. "Chicken curry, prepared" from USDA is
  *not* your Food.com curry.
- 22 curated staples: rice, brown rice, roti, naan, rice noodles, pasta, tortillas,
  bread, potato, 4 plain vegetables, 6 fruits, boiled egg (`Data/curated/usda_staples.json`).

**Engineering pattern: extract once, commit the small result.** The USDA nutrient file is
1.6 GB. `food_data/usda_staples.py:195 extract` streams it once and writes the 20 KB
`usda_staples_extract.json`. The extract stores a hash of the spec, so editing the spec
without re-extracting fails the build ("stale extract").

**Identity guard.** The spec stores the exact USDA description. If an `fdcId` points at a
different food, extraction fails. All 22 matched on the first run, which means the
guard worked; it was not luck.

**The salt finding.** USDA FNDDS "Rice, white, cooked, no added fat" has **245 mg sodium
per 100 g**, because FNDDS assumes rice is cooked in salted water (US practice). Asian
steamed rice is unsalted. With the FNDDS record, a hypertension rule would penalise
plain rice. The fix uses the SR Legacy "cooked without salt" identity (1 mg) for rice,
noodles, pasta, potato and vegetables. Breads, tortillas, fruit and egg keep FNDDS,
because their salt is part of the food.

**Remember.** "Same name" is not "same food". Check the preparation assumptions behind
reference data, especially for safety-relevant nutrients.

## 6. Stage 4: portions

**Problem.** The CSP needs discrete portion choices, and each choice needs nutrition. But
Food.com never says what a serving weighs.

**Decision** (ADR 0003 D2). Every `PortionOption` carries the **absolute nutrient vector
of exactly that quantity**:

- Food.com: 0.5, 0.75, 1, 1.25, 1.5 servings. `grams` stays `None`. 1.5 servings =
  1.5 x the serving vector.
- USDA: household units with real mass. 2 roti = 2 x 40 g = 80 g = 0.8 x per-100 g.

**Why this matters.** The CSP only adds vectors, so it never needs a mass we don't have.
Worked example: dal 1 serving (350 kcal) + rice 150 g (195 kcal) = 545 kcal, with no
curry mass anywhere.

**Two USDA portion formats.** FNDDS writes `1 medium chappatti or roti (7")` in the
description; SR Legacy writes amount `0.5` + modifier `cup, chopped`. Both reduce to
grams per one unit (`usda_staples.py parse_portion`). The spec pins the exact
`food_portion.csv` row ID, which is more robust than matching text.

**Small but real.** Floating point gave `239.20000000000002` kcal in exports. Portion
vectors are rounded to 3 decimals, far below nutrient precision, so exports diff cleanly.

## 7. Stage 5: popularity without leakage

**Problem.** Popularity breaks ties in selection and is the cold-start ranking. If it
counts interactions that the ranker is later *tested* on, the test leaks.

**Data insight.** The provided `interactions_train/test.csv` split each *user's* history:
"train" contains 2018 interactions, "test" contains 2000 ones. Counting "train" would
still include other users' future. **Fix:** one global date cutoff. Only interactions
before 2012-01-01 count: 906,736 used, 225,631 held out, about 80/20
(`food_data/popularity.py:55 count_interactions`).

**Remember.** A "train" file is only leakage-safe for the purpose it was built for. For
time-dependent signals, split by time.

## 8. Stage 6: curation (Nepali dishes, pairings)

**Nepali.** Food.com has no Nepali tag. A name search (momo, thukpa, sekuwa, tarkari, dal
bhat, aloo dum) found candidates. Review mattered: **false positives** included "bara
brith" (Welsh bread), "momo's famous crock pot ribs" (a person called Momo), nimki
crackers and spiced tea. 17 dishes were curated as Nepali; shared dishes kept their
Indian label too.

**Cuisine vocabulary.** Every curated cuisine name is checked against a known list, so a
typo ("Nepalese") fails validation instead of creating a new, empty cuisine.

**Pairings** (`Data/curated/pairings.json`): which verified staples a main may be served
with, per cuisine (Indian: rice, brown rice, roti, naan; Thai: rice, rice noodles; ...).
`validate_pairings` checks every staple exists, really is a STAPLE, and is used in that
cuisine.

**Honesty about curation.** These entries are marked `curatedBy: "ai-review:claude"`:
chosen by AI judgement at your request, **not** confirmed by a person. Provenance must
never claim a review that did not happen.

## 9. Stage 7: stratified selection

**Problem.** The old selection picked by hash and got 122 American dishes out of 191,
with 3 Indian ones. The catalogue's contents decide which plans are possible.

**Decision.** Quotas per stratum = (cuisine x slot kind), where the slot kinds are
breakfast base, complete main, main needing an accompaniment, and vegetable side. At
least half of each stratum is vegetarian where the data allows. Inside a stratum the
order is curated first, then training popularity, then a seeded hash. Near-duplicate
names are skipped ("Chicken Tikka Masala!" = "chicken tikka masala").

**Why quota 10.** A dish may repeat twice a week, so 7 breakfasts need 4 distinct dishes
and 14 lunches/dinners need 7. Diet and allergy rules then remove some. Stage 10
measured it: quota 8 left 3 of 8 scenarios short; 10 left 2; 12 added dishes but no
coverage. So 10 was chosen *from measurement*, not guessed.

**A short stratum is reported, never padded.** Nepali breakfast has 0 dishes because none
exist. Padding it with Indian breakfasts would hide the gap.

`food_data/selection.py:118 select_stratified`. Result: 160 Food.com dishes + 22 staples.

## 10. Stage 8: the Meal Composition Engine

**What it does.** It builds sensible meals of 1 to 3 *complete dishes* from **templates
as data** (`Data/curated/meal_templates.json`):

| Template | Example |
|---|---|
| ONE_DISH | biryani, momo |
| MAIN_STAPLE | dal + rice |
| MAIN_STAPLE_VEGETABLE | dal + rice + spinach |
| BREAKFAST / _FRUIT / _PROTEIN | poha (+ banana / + boiled egg) |

**Rules.** A main that REQUIRES_ACCOMPANIMENT is paired only with staples listed for its
cuisine. A vegetable side must share the main's cuisine or be cuisine-neutral, with
same-cuisine sides first. A breakfast add-on already in the base is skipped (no boiled
egg with an omelette: `composer.py:58 overlaps`).

**Why presets, not free portions.** Three components with 5 options each give 125
configurations per meal; across hundreds of meals and 21 slots the CSP would choke. And
scaling everything by one factor cannot trade rice for dal. So each preset moves each
slot a number of **steps** along that dish's own options (`presets.py:47 step_portion`):

| Preset | main | staple | vegetable |
|---|---|---|---|
| STANDARD | 0 | 0 | 0 |
| HIGHER_PROTEIN | +2 | -1 | 0 |
| LOWER_CARB | +1 | smallest | +1 |
| HIGHER_ENERGY | +1 | +1 | 0 |
| LOWER_ENERGY | -1 | -1 | +1 |

Presets that give identical portions are merged (STANDARD always survives), so a meal
has 1 to 5 configurations, about 4.5 on average.

**IDs.** `C_<templateId>__<dishId>__<dishId>`. The template is part of the ID because a
frittata as a lunch ONE_DISH and as a BREAKFAST are different meals; the first build
failed on exactly this duplicate. Configurations are `<combinationId>#<PRESET>`.

**Bounded by construction.** Caps apply *while generating* (2 staples per main, 1 side
per pair, 2 add-ons per base, picked by seeded hash). Exceeding the safety bound is an
error, never a silent cut.

**Result.** 446 meals: breakfast 149, lunch and dinner 300 each.

## 11. Stage 9: meal nutrition validation

For every configuration (`meal_composition/nutrition.py:92 check_configuration`):

1. **Sum per nutrient**, propagating unknowns.
2. **Weakest source wins.** A meal is as trustworthy as its least trusted dish.
3. **FULLY_KNOWN** only if every required nutrient (energy, fat, saturated fat,
   carbohydrate, protein, sodium) is known for every component.
4. **Sanity.** Energy is recomputed from each dish's *base* record (not the rounded
   portion vectors) and must agree within 1 kcal; it must lie in 150 to 2,000 kcal.

A failing configuration is dropped with a coded reason; a meal with none left is
rejected and listed. Result: 1,988 kept, 52 dropped, 3 meals rejected.

**The most important finding for the team.** Every kept meal has source tier
`FOODCOM_DERIVED`, because every meal has a Food.com anchor dish. If Venkat's rules
treat derived nutrition as unknown for hard clinical rules, *no current meal can pass
one*. A data property became a product question.

**Remember.** Independent recomputation is a cheap way to test a pipeline: if two paths
to the same number disagree, one of them has a bug.

## 12. Stages 10 and 11: coverage and export

**Coverage** (`meal_composition/coverage.py`). Eight synthetic profiles (cuisine policy,
diet, explicit exclusion) are checked with a clearly labelled **proxy**: unverified diet
tags, ingredient words, and a missing tag fails closed. It is not the Rule Engine; it
tells Member 1 where the catalogue is thin. 6 of 8 are sufficient. The two gaps are
data limits: no Nepali breakfast exists, and peanut-free Thai breakfasts number 3.

**Export** (`food_data/build_catalogue.py:131 build`). One command writes
`<version>_catalogue.json` (0.7 MB), `<version>_combinations.json` (2.4 MB) and
`<version>_build_report.json`. The version is the UTC build time, which sorts as text.
`--check` rebuilds and compares the content with the latest export: it passed on the
real data, which proves the whole pipeline is deterministic.

---

## 13. The Transformer ranking (T0 to T5)

### 13.1 Decisions (ADR 0004)

| Question | Decision | Why |
|---|---|---|
| split | global time: train < 2012, validation 2012, test 2013+ | no future leaks into training |
| eval case | a user's first interaction in the period; history = everything before | realistic next-item prediction |
| ranking | **full** ranking over all ~231k recipes | sampled-candidate metrics mislead |
| model | SASRec + content features | short histories, cold items |
| history in the product | onboarding seed dishes | GC1 stores no consumption |
| meal score | the anchor dish's score | staples have no interaction data |

### 13.2 What the data says (measure before modelling)

- The median user has **1** training interaction; only 32,056 have 3 or more.
- 13.6% of test targets were never seen in training (cold items).
- 258k consecutive pairs share a date (bulk reviewing): within-day order is unknown.

### 13.3 How the model works

```
item vector  v(i) = [seen in training] * E_id[i] + mean(E_tag[tags]) + mean(E_ingr[ingredients])
user state   h    = causal self-attention over the last 50 item vectors + positions
score(i)          = h . v(i) + b(i)        (b = learned popularity bias, 0 if unseen)
```

The content part lets a never-seen recipe (a curated Nepali dish) still be placed by its
tags and ingredients; its ID part is exactly zero, never random noise. A test proves
this: changing an unseen item's ID row does not change its vector.

### 13.4 Baselines and exact full ranking

Popularity, first-order Markov (last item to next), and item-kNN (co-occurrence cosine).
`recommendation/baselines.py:44 full_rank` counts the target's rank instead of sorting
231k items, using a shared tie-break (training popularity, then ID). A property test
compares it with brute-force sorting on 300 random cases.

### 13.5 Debugging the model: four lessons

1. **Script shadowing.** An unrelated `/tmp/profile.py` hid Python's standard `profile`
   module, because the experiment script lived in `/tmp`. Keep scripts in their own
   directory.
2. **Initialisation scale.** Default N(0, 1) embeddings, summed three times, gave dot
   products near +/-100: loss 23.5 and HR@10 = 0. Std 0.02 fixed it.
3. **A bug or a bad objective? Test in-sample.** The model did not beat popularity even
   on its *own training targets*. That rules out "fails to generalise to 2012" and points
   at the objective.
4. **Negative sampling decides what the model learns.** Uniform negatives are almost
   never popular recipes, so the model only learned "real target vs obscure recipe", and
   obscure recipes with the right tags crowded the full top 10. Popularity negatives
   without correction pushed popular recipes down. **logQ correction** (subtract
   log(K q(i)) from each logit) makes the sampled loss approximate the full softmax:
   in-sample median rank halved (5,862 vs 11,095).

### 13.6 Results

Test period (2013+), 9,200 users, full ranking over 231,637 recipes
(`docs/eval/ranking_evaluation.json`):

| Model | HR@10 | NDCG@10 | MRR | Coverage@10 |
|---|---|---|---|---|
| Popularity | 1.91% | 0.0091 | 0.0085 | 0.01% |
| Markov | 0.90% | 0.0042 | 0.0050 | 2.41% |
| Item-kNN | 0.15% | 0.0009 | 0.0016 | 6.47% |
| SASRec + content | 1.52% | 0.0070 | 0.0065 | 0.22% |
| **SASRec + content + popularity (hybrid)** | **1.96%** | **0.0095** | **0.0089** | 0.01% |

How to read this honestly:

- **The Transformer alone does not beat popularity** on Food.com next-review prediction.
  It does beat both personalised baselines, and it recommends 22 times more distinct
  recipes than popularity.
- Popularity wins in **every** history-length bucket (1, 2-4, 5-19, 20+); the gap is
  largest for heavy users. With a median history of 1, there is little sequence to learn.
- **Cold recipes** (never seen in training): no model gets them into the top 10, but
  content features give a median rank of 85k versus popularity's 220k, so the content
  tower places unseen dishes far better.
- **Hybrid** = model score + w x log(1 + training count). w = 8 was chosen on
  *validation* HR@10 only (tried 0, 0.5, 1, 2, 4, 8) and the test set was scored once.
  It ties popularity (1.96% vs 1.91%; the standard error is about 0.14 points) and is
  slightly better on MRR. The product uses the hybrid: popularity-level accuracy plus
  personal ordering from the seed dishes and a content fallback for new dishes.
- These numbers measure "which recipe a Food.com user reviews next", not whether a
  Savora user would enjoy a planned meal. No such data exists in GC1.

**Remember.** A strong popularity baseline is common on sparse data. Report it next to
the model, choose any blend weight on validation only, and never on test.

### 13.7 The ranking API

`recommendation/ranking.py:176 rank_recipes` and `:208 rank_combinations`:

- score **only** the supplied (already rule-safe) IDs;
- return a softmax *within* the candidate set: relative, never calibrated, never nutrition;
- fall back to popularity, saying so in `modelVersion` and `fallbackReason`, when there is
  no known history, no model file or no torch;
- score a meal by its anchor dish (`MEAN` over dishes is an ablation).

torch is an optional extra (`ml`), so the backend and CI run without it. The model
module is the only file that imports torch.

---

## 14. Check yourself

1. Why is a recipe without a course tag *unclassified* and not *defective*?
2. The energy check uses both a ratio band and a 10 kcal gap. What goes wrong with only
   the ratio?
3. Why can't the `vegetables` tag alone make a dish a VEGETABLE side?
4. Why does `steamed white rice` use an SR Legacy record and not FNDDS?
5. How does the CSP get nutrition for "1.5 servings of dal" without knowing its mass?
6. Why is `interactions_train.csv` not safe for popularity?
7. A stratum has 3 eligible dishes and a quota of 10. What does selection do, and why?
8. Why are portion presets *steps* along each dish's options, not one scale factor?
9. Why is the template ID part of the combination ID?
10. Every meal's source tier is FOODCOM_DERIVED. Why, and why does Venkat care?
11. What does `--check` prove about the pipeline?
12. Why is full ranking harder (lower numbers) than ranking against 100 sampled items?
13. Your model loses to popularity in-sample. What does that tell you?
14. Why do uniform negatives fail and what does logQ correction change?
15. What happens in `rank_recipes` for a new user with no history?

## 15. Open items and where they are tracked

| Item | Owner | Where |
|---|---|---|
| Food.com-derived nutrition for hard clinical rules | Venkat | contract note Q2 |
| PER_SERVING quantities in the CSP; integer rounding policy | Venkat | contract note Q1, Q3 |
| Solver time on 446 meals x 4.5 configurations | Venkat | contract note Q4 |
| Cuisine-neutral breakfasts under STRICT | team | contract note Q5 |
| Storage of combinations | Aryaman | contract note Q6 |
| Human confirmation of `ai-review:claude` curation | team | contract note Q7 |
| Onboarding seed dishes as history | Aryaman, team | ADR 0004 D7 |
| Sodium / saturated-fat DV source verification | team | ADR 0001 D1 |
| Production evidence path (Member 2 contracts accept SYNTHETIC only) | team | contract note 4 |
