"""The catalogue bundle shared with the AI runtime (loaded once, never per request)."""

from typing import Annotated

from fastapi import Depends

from savora_ai.core.pipelines import CatalogueBundle
from savora_backend.ai.runtime import AiRuntime, get_ai_runtime, get_default_ai_runtime


def get_catalogue_bundle() -> CatalogueBundle:
    """The process-wide bundle, for code outside a request (jobs, tests)."""
    return get_default_ai_runtime().bundle


def get_request_bundle(runtime: Annotated[AiRuntime, Depends(get_ai_runtime)]) -> CatalogueBundle:
    return runtime.bundle


CatalogueBundleDep = Annotated[CatalogueBundle, Depends(get_request_bundle)]
