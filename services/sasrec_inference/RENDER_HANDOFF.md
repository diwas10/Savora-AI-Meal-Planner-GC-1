# Member 1 / Member 3 Render integration handoff

Space: **vvenkata/savora-sasrec-inference**
([repository](https://huggingface.co/spaces/vvenkata/savora-sasrec-inference)).
Inference host: **https://vvenkata-savora-sasrec-inference.hf.space**.
Verified revision: `ed1392996183abfdc844529dd93c251d568b2cb8`.
Model: `sasrec-content-v2`. Checkpoint SHA-256:
`87f1855284befc8e6b43d86779edc177b592bbe68f0cb3a8f89c288e41f0cb45`.

**Render integration is not implemented or verified.** These are instructions for
a future authorized task. No deployment settings should be changed for this PR.

Visibility preflight (23 October 2026): the Space currently reports **public**;
unauthenticated `/health` returns 200 and `/rank` without the application service
credential returns 401. The earlier deployment snapshot was private. This task
changed neither visibility nor secrets. The adapter must support both headers so
it works with private gateway access as well; public visibility does not remove
the application's service-token requirement.

## Required backend variables

| Render variable | Intended value |
| --- | --- |
| `SAVORA_SASREC_BASE_URL` | `https://vvenkata-savora-sasrec-inference.hf.space` |
| `SAVORA_SASREC_HF_TOKEN` | Least-privilege HF access token when private gateway access is required |
| `SAVORA_SASREC_SERVICE_TOKEN` | Existing application secret matching Space Secret `SAVORA_SERVICE_TOKEN` |
| `SAVORA_SASREC_TIMEOUT_SECONDS` | `8` |
| `SAVORA_SASREC_ENABLED` | `false` until adapter checks pass; then `true` in an approved integration task |

The existing backend does not consume these variables. Setting them alone will
not activate remote ranking. Keep both tokens in backend secret management only;
never use `NEXT_PUBLIC_*`, frontend storage, URLs, fixtures or request logs.
Arrange secure access to the existing matching service secret; no credential is
provided in this repository and no HF secret rotation is requested here.

## Exact `savora-rank-v1` contract

`POST /rank` uses `Content-Type: application/json` and **both** headers:

```text
Authorization: Bearer <SAVORA_SASREC_HF_TOKEN>
X-Savora-Authorization: Bearer <SAVORA_SASREC_SERVICE_TOKEN>
```

The first authenticates at the HF gateway when access is private; the second at the application.
For direct local calls, the app also accepts its service bearer in `Authorization`.
When present, `X-Savora-Authorization` takes precedence at the app.

Exact request (also [fixture.json](fixture.json)):

```json
{
  "schema_version": "savora-rank-v1",
  "history_ids": ["FC_100", "FC_10000", "FC_100000"],
  "candidate_ids": ["FC_100001", "FC_100002", "FC_100003", "FC_100004", "FC_100005"]
}
```

No extra fields are accepted. Both ID arrays contain strict strings matching
`^FC_[0-9]{1,12}$` **and present in the checkpoint catalog**. Padding, unknown IDs,
numbers and arbitrary recipe embeddings are rejected. History contains 1–50 IDs,
oldest first; repeated interactions are allowed. Retain the latest 50 valid,
legitimately ordered history entries before calling. Candidates contain 1–512
unique, already eligible recipe IDs. Maximum body size is 32,768 bytes.
Candidates may also occur in history; the service does not remove them.

Observed remote response for this fixture:

```json
{
  "schema_version": "savora-rank-v1",
  "model_version": "sasrec-content-v2",
  "score_mode": "transformer_only",
  "scores": [
    {"candidate_id": "FC_100001", "score": -1.0865507125854492, "rank": 4},
    {"candidate_id": "FC_100002", "score": -2.292989492416382, "rank": 5},
    {"candidate_id": "FC_100003", "score": -0.9994651675224304, "rank": 2},
    {"candidate_id": "FC_100004", "score": -1.047228455543518, "rank": 3},
    {"candidate_id": "FC_100005", "score": 2.2045743465423584, "rank": 1}
  ]
}
```

`scores` retains request order. Each input candidate appears exactly once; ranks
are the permutation `1..N`, descending by finite raw score, ties in request order.
Rank 1 is best. Scores may be negative and are not probabilities, nutrition values
or clinical estimates. Require exact schema/model/mode, candidate order/count,
finite scores and rank consistency before using a response.

`GET /health` requires no application secret; supply the HF bearer for private
gateway access. Ready returns HTTP 200:

```json
{
  "status": "ready",
  "ready": true,
  "model_version": "sasrec-content-v2",
  "schema_version": "savora-rank-v1",
  "score_mode": "transformer_only",
  "checkpoint_sha256": "87f1855284befc8e6b43d86779edc177b592bbe68f0cb3a8f89c288e41f0cb45"
}
```

Unready returns 503, `ready=false`, `status=unavailable`, digest null. The private
gateway previously returned 404 without HF access; do not assume gateway errors
use the application's JSON schema. This internal protocol uses snake_case and no
Savora `/api` envelope; public camelCase DTOs remain unchanged.

## Failures, deadlines and fallback

| HTTP result | Meaning / adapter action |
| --- | --- |
| 401 | App authentication failure; fallback and report a redacted configuration error |
| 413 | Body too large; fallback, correct batching/input bounds |
| 422 | Invalid schema or unavailable ID; fallback, investigate namespace/history |
| 429 | Inference busy; fallback promptly, respect `Retry-After: 1` for any bounded diagnostic retry |
| 503 | Model/inference unavailable; fallback |
| 504 | Inference deadline exceeded; fallback |
| HF gateway/network failure, malformed response | Fallback; never consume partial/unvalidated output |

Use a 3-second connection timeout and an **overall** 8-second interactive deadline,
including response validation/batching. The app's default model deadline is
5 seconds with one model job at a time. A timeout leaves native computation
occupying its slot until finished. Avoid retry storms. A separate cold-start
diagnostic may allow 120 seconds; interactive requests should fall back promptly.

For empty/unusable history, unknown IDs, disabled/unavailable service or invalid
output, retain the existing deterministic popularity fallback on the same eligible
set. Expose accurate model version/fallback reasons. Do not fabricate history,
replace IDs with arbitrary known IDs, or claim Transformer success after fallback.
The saved `hybridWeight=8.0` does not recreate the historical blend: exact training
popularity counts/preprocessing are missing. This endpoint is Transformer-only.

## Exact work for Member 1 (coordinate backend work with Member 3)

1. Obtain approval for a remote inference adapter under `ARCHITECTURE.md` §12.1.
   Keep the AI package free of HTTP/backend imports; place transport/configuration
   at the backend boundary and inject a typed scorer. Do not make this archive a
   mandatory application runtime or change GC2.
2. Verify application recipe IDs against the trained `FC_` catalog and validate
   history provenance/order. Current `ranking.py` describes onboarding seed dishes;
   these are preferences, not verified chronological consumption. Resolve the
   ordering/policy explicitly before enabling a sequential model. Generated plans,
   provisional CSP assignments and substitutions are not observed user history;
   add no new feedback/history persistence in GC1.
3. Implement backend-only settings and an HTTP scorer compatible with
   `SequenceScorer` in `apps/ai_system/src/savora_ai/core/recommendation/ranking.py`.
   The protocol's negative raw logits must flow through the existing ranking
   normalization; do not copy them into public `score` fields constrained to [0,1].
   Validate every response and handle HTTP failures explicitly: current ranking
   code does not automatically catch a new remote scorer's transport exceptions.
4. Send only rule-admitted recipe IDs. Retain existing recipe ranking for standalone
   cravings and documented ANCHOR/MEAN dish-score aggregation for combination
   ranking; `/rank` does not accept combination IDs. Handle >512 requested dish IDs
   with bounded batching within the total deadline or explicit popularity fallback.
   Define known/unknown catalog behavior and preserve unscored-candidate semantics.
   Keep all hard eligibility rules, composition, CSP/portion constraints, locked
   substitution slots and independent proof checks authoritative.
5. Add deterministic adapter tests for both auth headers, redacted failures,
   schema/version/mode and candidate validation, finite scores/tie ranks, history
   and size bounds, timeout/busy/malformed response fallback, unknown candidates,
   combinations and cold start. Verify the fixture locally/against authorized HF
   access with score tolerance `1e-5`; never call HF in regular unit tests.
6. In a separately authorized deployment task, configure the five backend Render
   variables using secure secret management, initially disabled. Verify authenticated
   health against the pinned version/hash and run end-to-end contract, fallback
   and safety checks from Render. Enable only after those pass; verify model-version
   reporting through planning, cravings and substitutions. Preserve quick disable
   to popularity fallback. No Space redeployment is required for this source PR.

Until these steps are complete, the deployed model is verified independently;
live website Transformer recommendations and Render connectivity are unverified.
