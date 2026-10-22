"""AI runtime loaded once during FastAPI lifespan."""

import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

from savora_ai.core.pipelines import CatalogueBundle, load_catalogue_export
from savora_ai.core.recommendation.model_store import (
    ModelIntegrityError,
    load_manifest,
    model_path,
)
from savora_ai.core.recommendation.ranking import SequenceScorer, load_scorer
from savora_backend.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AiRuntime:
    bundle: CatalogueBundle
    scorer: SequenceScorer | None


_default_runtime: AiRuntime | None = None


def build_ai_runtime(
    *,
    catalogue_dir: Path | None = None,
    model_dir: Path | None = None,
    settings: Settings | None = None,
) -> AiRuntime:
    """Load the catalogue bundle and optional trained Transformer scorer.

    Raises ModelIntegrityError if the model file exists and does not match the manifest.
    """
    cfg = settings or get_settings()
    cat_dir = catalogue_dir or cfg.catalogue_dir
    mod_dir = model_dir or cfg.model_dir

    bundle = load_catalogue_export(cat_dir)
    manifest_file = mod_dir / "manifest.json"
    scorer: SequenceScorer | None = None
    if manifest_file.exists():
        manifest = load_manifest(manifest_file)
        ckpt_path = model_path(manifest, mod_dir)
        try:
            scorer = load_scorer(
                ckpt_path,
                bundle.popularity.counts,
                manifest=manifest,
            )
        except ModelIntegrityError as exc:
            logger.error("Model integrity verification failed: %s", exc)
            raise RuntimeError(f"Refusing to start due to model integrity error: {exc}") from exc

    if scorer is not None:
        logger.info("AI runtime initialized with scorer modelVersion=%s", scorer.model_version)
    else:
        logger.info("AI runtime initialized with popularity fallback")

    return AiRuntime(bundle=bundle, scorer=scorer)


def get_default_ai_runtime() -> AiRuntime:
    global _default_runtime
    if _default_runtime is None:
        _default_runtime = build_ai_runtime()
    return _default_runtime


def get_ai_runtime(request: Request) -> AiRuntime:
    runtime = getattr(request.app.state, "ai_runtime", None)
    if isinstance(runtime, AiRuntime):
        return runtime
    return get_default_ai_runtime()
