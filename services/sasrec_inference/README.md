# Verified SASRec inference source (GC1)

This directory archives the independently deployed Hugging Face service.
It is outside both the uv and pnpm workspaces. Adding it does not enable a backend
adapter, change the application runtime, or require another GC1 service.
Member 1 owns the model and ranking integration; Member 3 owns backend wiring.

| Item | Pinned value |
| --- | --- |
| Space | [vvenkata/savora-sasrec-inference](https://huggingface.co/spaces/vvenkata/savora-sasrec-inference) |
| Inference host | `https://vvenkata-savora-sasrec-inference.hf.space` |
| Verified revision | `ed1392996183abfdc844529dd93c251d568b2cb8` |
| Model | `sasrec-content-v2` |
| Protocol | `savora-rank-v1`, `score_mode=transformer_only` |
| Required checkpoint | `sasrec_content.pt`, 196,509,717 bytes; hosted on Hugging Face only |
| Checkpoint SHA-256 | `87f1855284befc8e6b43d86779edc177b592bbe68f0cb3a8f89c288e41f0cb45` |

Cloning GitHub does **not** provide trained weights. No model binary, LFS pointer,
raw dataset, credentials or deployment automation is included. The model has
15,354,134 parameters, 231,637 Food.com recipe IDs, 64-dimensional embeddings,
two causal Transformer layers and 50 history positions.

## Source provenance

`app.py`, `model.py`, `Dockerfile`, `.dockerignore`, `requirements.in`,
`requirements.txt`, `sasrec_content.json` and `fixture.json` retain the exact
bytes recorded in the verified upload manifest. `.gitattributes` prevents newline
conversion for these files. `test_contract.py` checks their SHA-256 digests.

`evidence/upload-manifest.json` is the historical HF upload inventory, **not** a
GitHub staging list: it describes the HF-only checkpoint and the original Space
README, tests and dev dependencies. GitHub documentation and ignore rules were
rewritten for this repository. Tests were adapted to support an external checkpoint
and explicit skips when it is absent. The dev list now needs only pytest and httpx;
deployment/credential-management tools are deliberately excluded. `ruff.toml`
retains narrowly scoped style exemptions for the unmodified deployed runtime.

See [DEPLOYMENT_REPORT.md](DEPLOYMENT_REPORT.md) for dated evidence and
[RENDER_HANDOFF.md](RENDER_HANDOFF.md) for the exact HTTP contract, credentials,
fallback rules and integration steps. `evidence/remote.json` and
`evidence/local.json` contain non-sensitive measured fixtures, not current health
promises. A read-only source/health recheck is recorded separately in
`evidence/source-verification.json`: all eight runtime files match the pinned HF
revision, health is ready, and `/rank` without application credentials returns 401.
The Space now reports **public** visibility and unauthenticated health returns 200;
the original deployment evidence recorded private visibility. No remote deployment
or configuration change is part of this contribution.

## Reproduce locally

Use Python 3.12 (deployment used 3.12.14) in a separate environment. Run from this
directory; these dependencies intentionally do not join the application lockfile.

```sh
python -m venv .venv
# Activate .venv using your platform's activation command.
python -m pip install --require-hashes -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pytest -c pytest.ini -q
```

Without the checkpoint, protocol/failure/provenance tests run and real-checkpoint
tests explicitly skip. To run the full suite against an already authorized
artifact without copying it into the repository, set
`SAVORA_TEST_CHECKPOINT_PATH` to that file. It must have its original
`sasrec_content.json` sidecar beside it. This is a test-only setting; the deployed
app does not read it. An explicitly configured incorrect artifact fails tests.

For an independent local runtime build, an authorized maintainer must obtain
`sasrec_content.pt` from the Space at the pinned revision, verify its
size and SHA-256 above, and supply it beside the source in a private build context.
The Dockerfile intentionally requires it with `COPY`: building from a GitHub-only
clone fails rather than substituting a random model. No download/upload helper is
provided. The existing HF service requires no rebuilding for this contribution.

```sh
# Only after privately supplying the verified artifact:
docker build -t savora-sasrec-inference .
# Supply a securely generated >=32-character secret in the shell environment.
docker run --rm -p 7860:7860 -e SAVORA_SERVICE_TOKEN savora-sasrec-inference
```

The image uses CPU PyTorch 2.10.0, hash-locked runtime packages, non-root UID 1000,
one Uvicorn worker, two Torch threads and port 7860. Do not publish the local
container or checkpoint to another registry as part of this source handoff.
`.env.example` contains blank secret fields and is documentation only; neither
the service nor the backend automatically loads these settings.

Startup verifies the checkpoint hash **before** restricted `weights_only=True`
loading, checks configuration/catalog/features and finite tensors, freezes the
model, and warms it up. Missing/corrupt weights or missing/short service secrets
keep readiness false; there is no random-model fallback. Runtime inference timeout
defaults to 5 seconds, configurable through `INFERENCE_TIMEOUT_SECONDS` within
0.1–10 seconds. A timed-out native computation retains its slot until completion.

## Architecture boundary and limitations

`ARCHITECTURE.md` sections 7, 9 and 12.1 remain authoritative. The application AI
package is in-process and cannot import HTTP/backend modules. This optional source
archive does not amend that rule. Making the remote Space an application runtime
dependency requires a separately reviewed architecture decision and backend
adapter. The remote snake_case protocol is separate from the public camelCase
`/api` contract and its standard envelopes.

The Space scores only supplied, known, rule-eligible **recipe IDs**. It has no
combination endpoint, clinical rules, portion optimizer, user-profile endpoint or
training endpoint. `recommend_next` is an existing model helper, not the HTTP
integration entry point; `/rank` uses bounded `score_candidates` only.

Raw Transformer logits can be negative and are not probabilities. The metadata's
`hybridWeight=8.0` does not reproduce the historical popularity blend: its exact
training counts are absent. Backend popularity fallback is a separate behavior.
No fabricated history, unknown-ID substitution, nutrition generation, or new
history/feedback persistence is authorized. GC2 is outside this contribution.
