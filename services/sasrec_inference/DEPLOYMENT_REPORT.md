# Deployment provenance — 23 October 2026 (Singapore)

This is a source-control handoff of the deployment already verified in the
independent inference workspace. No Space, Render, Vercel or Supabase configuration
was changed for this contribution. Historical measurements below come from the
saved verification artifacts, not a newly initiated deployment or live guarantee.

- Space at original deployment: `vvenkata/savora-sasrec-inference` (private, Docker, `cpu-basic`).
- Inference host: `https://vvenkata-savora-sasrec-inference.hf.space`.
- Verified revision: `ed1392996183abfdc844529dd93c251d568b2cb8`.
- Model: `sasrec-content-v2`; 15,354,134 parameters; strict frozen/eval loading.
- HF-only checkpoint: 196,509,717 bytes, SHA-256
  `87f1855284befc8e6b43d86779edc177b592bbe68f0cb3a8f89c288e41f0cb45`.

## Observed verification

The original deployment report records a successful HF container build, startup
and model warmup on the revision above. Model load/warmup logged 1.489 seconds.
The original native Python 3.12.14 / Torch 2.10.0+cpu suite passed 27 tests.
Local Docker execution was not verified because Docker was unavailable.

The retained [remote evidence](evidence/remote.json) records:

| Request | Observed result |
| --- | --- |
| Health without HF access | 404 from the private gateway |
| Health with authorized HF bearer | 200, ready, pinned checkpoint digest |
| Rank with absent/wrong application credential | 401 |
| Rank with an unavailable recipe ID | 422 |
| Rank with both credentials and `fixture.json` | 200, real trained scores |

Five repeated remote rank calls returned identical JSON. Maximum absolute
local/remote score difference was `2.384185791015625e-7`, below `1e-5`, with exact
candidate/rank correspondence. Warm round-trip median was 388.2552 ms and maximum
433.6273 ms across five samples. These timings are observations, not guarantees.
See [local evidence](evidence/local.json) for native output and CPU measurements.

## Reproducibility and exclusions

[The historical upload manifest](evidence/upload-manifest.json) records original
per-file hashes. Its checkpoint entry documents the artifact hosted on HF; it
does not include that artifact in GitHub. The runtime, Dockerfile, hash-locked
dependencies, metadata and request fixture are reproduced byte-for-byte.
Repository-specific README/handoff/ignore/configuration files and adapted tests
are clearly separate from those deployed inputs.

Excluded: all model weights, private tokens, service-secret values, encrypted
credential files, `.local-secrets/`, `.env`, environments, caches, staging folders,
raw data, deployment scripts, build/runtime logs and temporary files. Only the
four reviewed, non-sensitive JSON evidence files are retained.

Checkpoint hash validation, restricted loading, bounds, application authentication,
body size limits, finite-output validation, timeout and busy handling remain in
the unmodified service source. This contribution does not claim an independent
training-data rights audit or a vulnerability audit of every locked dependency.

## Integration status

A read-only source-control preflight on 23 October 2026 confirmed the running
revision is still the pinned revision and all eight archived runtime/build inputs
match HF byte-for-byte. Health returned 200 with the pinned checkpoint digest.
Current metadata reports **public** visibility, unlike the original private
deployment snapshot; unauthenticated health now returns 200. `/rank` without an
application credential still returns 401. See
[the current source/health evidence](evidence/source-verification.json).
No Space visibility, secret or runtime configuration was changed in this task.

The model was deployed and remote inference verified at the pinned revision.
The current GC1 main baseline has no HF HTTP adapter or `SAVORA_SASREC_*` settings.
This PR does not implement them and does not connect Render or the website.
Member 1 and Member 3 must complete [the integration handoff](RENDER_HANDOFF.md),
including architecture approval, namespace/history checks, adapter validation,
backend-only secret configuration and end-to-end fallback/proof tests.
