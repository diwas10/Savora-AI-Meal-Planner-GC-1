"""AI runtime loaded once during the FastAPI lifespan: catalogue, ranker and NLU parser."""

import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

from savora_ai.core.craving_nlu import (
    CravingParser,
    QwenParser,
    TemplateParser,
    build_qwen_client,
)
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
    parser: CravingParser


_default_runtime: AiRuntime | None = None


def build_craving_parser(bundle: CatalogueBundle, settings: Settings) -> CravingParser:
    """Local Qwen (HYBRID with the template parse) unless disabled; one pooled client."""
    template = TemplateParser(bundle.cuisine_ids)
    if settings.qwen_provider == "none":
        logger.info("Craving NLU: template parser only (QWEN_PROVIDER=none)")
        return template
    client = build_qwen_client(
        provider=settings.qwen_provider,
        base_url=settings.qwen_base_url,
        api_key=settings.qwen_api_key,
    )
    logger.info(
        "Craving NLU: %s via %s at %s, template fallback",
        settings.qwen_model_name,
        settings.qwen_provider,
        settings.qwen_base_url,
    )
    return QwenParser(
        client,
        model=settings.qwen_model_name,
        timeout_s=settings.qwen_timeout_s,
        cuisine_ids=bundle.cuisine_ids,
        template_fallback=template,
    )


def build_ai_runtime(
    *,
    catalogue_dir: Path | None = None,
    model_dir: Path | None = None,
    settings: Settings | None = None,
) -> AiRuntime:
    """Load the catalogue bundle, the optional trained Transformer scorer and the parser.

    Raises RuntimeError if the model file exists and does not match the manifest.
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

    return AiRuntime(bundle=bundle, scorer=scorer, parser=build_craving_parser(bundle, cfg))


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
