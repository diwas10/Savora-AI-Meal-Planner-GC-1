# ADR 0005: Onboarding seed dishes and delivery of the trained model

- **Status:** D1 **Accepted** by the whole team on 2026-10-20 (as written). D2 mechanism
  accepted; the hosting choice is **deferred** (see open items).
- **Date:** 2026-10-19 (proposed); 2026-10-20 (team decision)
- **Owner:** Member 1 (ranking); Member 3 wires the endpoints, storage and UI.
- **Relates to:** ARCHITECTURE.md sections 4.1, 7, 9.2, 11; ADR 0004 D7 and open items 1-2;
  AGENTS.md "Persist generated plans and substitutions only"

## Context

The Transformer ranks with a user's history, but GC1 stores no ratings, consumption or
feedback, so a new user has none. ADR 0004 D7 said onboarding should ask for 3 to 5 liked
dishes; nothing implements it yet. Without them every plan uses the popularity fallback
(`fallbackReason: NO_HISTORY`) and the trained model is never used.

The trained checkpoint (`sasrec_content.pt`, about 190 MB) is git-ignored, so no teammate
or server can load it today, and nothing checks that a file under that name is the
evaluated model.

## Decision

### D1. Seed dishes are a stored profile preference, chosen from a rule-safe shortlist

1. After the profile is saved, the backend loads the catalogue dishes the Rule Engine
   passes for this profile and cuisine policy (`filter_candidates`; unknown safety facts
   do not pass) and calls `suggest_seed_dishes(rule_safe_dishes, preferred_cuisines)`.
2. It returns 12 suggestions by default: Food.com dishes with a main or breakfast-base
   role, by training popularity, interleaved across cuisines, the user's preferred
   cuisines first. Deterministic; no torch needed; it never decides safety.
3. The user picks 3 to 5 (from the suggestions or from search). The backend calls
   `validate_seed_picks(picks, rule_safe_dishes)` and stores the IDs, in pick order, on
   the profile (for example `seed_recipe_ids`).
4. Every ranking call passes those IDs as the history. Picks the model does not know are
   dropped by the ranker; if none is left the result says `NO_HISTORY`.
5. Seeds are a preference the user states, like cuisine or diet, not a feedback event:
   they are edited only by the user, never derived from saved plans, swaps or behaviour.
   This keeps the AGENTS.md rule (no ratings, consumption, feedback or retraining).
6. When the profile's rules change (new allergy, diet), the backend revalidates the
   stored seeds and drops any no longer rule-safe, asking the user to replace them if
   fewer than 3 remain. A seed is history only, never a recommendation by itself.

### D2. The model is published as a versioned release file, pinned by a tracked manifest

1. `Data/models/manifest.json` (tracked) records `modelVersion`, `fileName`,
   `sizeBytes`, `sha256` and an https `sourceUrl`: a GitHub release asset tagged
   `model-<modelVersion>`.
2. `python -m savora_ai.core.recommendation.model_store --download` downloads, verifies
   and only then renames the file into place; without `--download` it verifies.
3. The backend loads the scorer once at startup with
   `load_scorer(path, counts, manifest=...)`. A missing file falls back to popularity,
   labelled `MODEL_UNAVAILABLE`; a file that does not match the manifest raises
   `ModelIntegrityError` and is not loaded.
4. A retrained model gets a new `modelVersion`, a new release tag and a new manifest;
   old release files stay, so saved plans remain attributable.

## Alternatives considered

- **Seed from the first saved plan:** rejected; saved plans are not positive feedback
  (ADR 0004 D7) and the first plan would still be cold.
- **Ask for cuisines only:** already in the profile; the model needs dish IDs.
- **Commit the model with Git LFS:** adds a tool and LFS bandwidth limits for a 190 MB
  file; a release asset plus a checksum gives the same pinning.
- **Supabase Storage:** possible later for a private model; the repository is public and
  the release asset needs no credentials.

## Consequences

- Member 3: a profile field and migration, two endpoints (suggestions, save picks), the
  onboarding step in the UI, revalidation on profile change, and the startup load.
- The shortlist comes from the 164 catalogue dishes. Measured on the shipped catalogue
  (19 Oct 2026) with the coverage report's 8 proxy profiles (anchors of allowed meals,
  strict cuisines applied): every profile gets the full 12 suggestions, so 3 to 5 picks
  are always possible. Planning coverage is the tighter limit: 7 of 8 profiles have
  enough distinct meals for a week; strict Nepali has no breakfast (catalogue contract
  question 5), and Thai without peanut has 8 lunch/dinner anchors for the 7 needed.
- Publishing the checkpoint publicly redistributes a model trained on the Food.com
  dataset (Majumder et al., 2019); the team should confirm the dataset's terms allow it.
  If not, use Supabase Storage with a private bucket and the same manifest.

## Team decision (2026-10-20)

1. **D1 accepted as written.** Seed dishes are stored on the profile as `seed_recipe_ids`
   (3 to 5, in pick order, edited only by the user, revalidated on profile change).
2. **D2 hosting deferred.** The manifest and checksum verification stay as decided, but
   the model is not published yet: public GitHub release vs a private Supabase bucket is
   decided once the Food.com dataset terms are checked, before the final demo. Until
   then the backend runs the labelled popularity fallback (`MODEL_UNAVAILABLE`), and
   developers who hold the file locally get it verified against the manifest.
3. **Names accepted** (docs/member3/IMPLEMENTATION_SPEC.md section 4): profile field
   `seed_recipe_ids`; `GET /api/onboarding/seed-suggestions` returns `SeedSuggestions`;
   `PUT /api/onboarding/seed-picks` takes `{recipeIds}` and returns `{seedRecipeIds}`.

## Open items

1. Decide D2 hosting (public release or private Supabase bucket) after checking the
   Food.com dataset terms; then upload `model-sasrec-content-v2` and update `sourceUrl`
   in the manifest if the location changes.
