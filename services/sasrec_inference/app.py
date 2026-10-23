"""Private, bounded CPU inference API. No user profiles or training endpoints."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import hmac
import logging
import os
from pathlib import Path
import threading
import time
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
import torch

from model import CHECKPOINT_SHA256, MODEL_VERSION, load_model, score_candidates

LOG = logging.getLogger("savora")
API_VERSION = "savora-rank-v1"
MAX_BODY_BYTES = 32768
RecipeId = Annotated[str, Field(strict=True, pattern=r"^FC_[0-9]{1,12}$")]


class RankRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["savora-rank-v1"]
    history_ids: list[RecipeId] = Field(min_length=1, max_length=50)
    candidate_ids: list[RecipeId] = Field(min_length=1, max_length=512)

    @field_validator("candidate_ids")
    @classmethod
    def unique_candidates(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("candidate_ids must be unique")
        return value


class CandidateScore(BaseModel):
    candidate_id: str
    score: float = Field(allow_inf_nan=False)
    rank: int


class RankResponse(BaseModel):
    schema_version: Literal["savora-rank-v1"] = API_VERSION
    model_version: str = MODEL_VERSION
    score_mode: Literal["transformer_only"] = "transformer_only"
    scores: list[CandidateScore]


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/rank":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_BODY_BYTES:
                return await JSONResponse({"detail": "Request body too large"}, 413)(scope, receive, send)
            if not message.get("more_body", False):
                break
        async def replay():
            return {"type": "http.request", "body": bytes(body), "more_body": False}
        await self.app(scope, replay, send)


def create_app(model_path: Path | None = None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.ready = False
        app.state.secret = os.environ.get("SAVORA_SERVICE_TOKEN", "")
        app.state.gate = threading.Lock()
        app.state.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="inference")
        app.state.timeout = min(10.0, max(0.1, float(os.getenv("INFERENCE_TIMEOUT_SECONDS", "5"))))
        try:
            if len(app.state.secret) < 32:
                raise ValueError("A service secret of at least 32 characters is required")
            torch.set_num_threads(2)
            started = time.perf_counter()
            app.state.model, app.state.ids, app.state.row_map = load_model(
                model_path or Path(__file__).with_name("sasrec_content.pt"))
            score_candidates(app.state.model, app.state.ids[1:4], app.state.ids[4:7], app.state.row_map)
            app.state.ready = True
            LOG.warning("Model ready version=%s load_seconds=%.3f", MODEL_VERSION,
                        time.perf_counter() - started)
        except Exception as exc:
            LOG.error("Model unavailable (%s)", type(exc).__name__)
        try:
            yield
        finally:
            app.state.ready = False
            app.state.executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="Savora SASRec inference", version=API_VERSION, lifespan=lifespan,
                  docs_url=None, redoc_url=None)
    app.add_middleware(BodyLimit)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"detail": "Invalid savora-rank-v1 request"}, status_code=422)

    async def authorize(authorization: str | None = Header(default=None),
                        service_authorization: str | None = Header(
                            default=None, alias="X-Savora-Authorization")):
        secret = app.state.secret
        if not secret:
            raise HTTPException(503, "Service unavailable")
        supplied = service_authorization if service_authorization is not None else authorization
        expected = "Bearer " + secret
        if supplied is None or not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise HTTPException(401, "Unauthorized", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/health")
    async def health():
        ready = app.state.ready
        return JSONResponse({"status": "ready" if ready else "unavailable", "ready": ready,
                             "model_version": MODEL_VERSION, "schema_version": API_VERSION,
                             "score_mode": "transformer_only",
                             "checkpoint_sha256": CHECKPOINT_SHA256 if ready else None},
                            status_code=200 if ready else 503)

    @app.post("/rank", response_model=RankResponse, dependencies=[Depends(authorize)])
    async def rank(payload: RankRequest):
        if not app.state.ready:
            raise HTTPException(503, "Model unavailable")
        if any(rid not in app.state.row_map for rid in (*payload.history_ids, *payload.candidate_ids)):
            raise HTTPException(422, "Unavailable recipe identifier")
        if not app.state.gate.acquire(blocking=False):
            raise HTTPException(429, "Inference busy", headers={"Retry-After": "1"})
        try:
            future = app.state.executor.submit(score_candidates, app.state.model,
                                              payload.history_ids, payload.candidate_ids,
                                              app.state.row_map)
        except Exception:
            app.state.gate.release()
            raise HTTPException(503, "Inference unavailable") from None
        future.add_done_callback(lambda _: app.state.gate.release())
        try:
            scores = await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)),
                                            timeout=app.state.timeout)
        except TimeoutError:
            raise HTTPException(504, "Inference timed out") from None
        except Exception:
            LOG.error("Inference failed")
            raise HTTPException(503, "Inference unavailable") from None
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        ranks = {index: rank + 1 for rank, index in enumerate(order)}
        return RankResponse(scores=[CandidateScore(candidate_id=rid, score=score, rank=ranks[i])
                                    for i, (rid, score) in enumerate(zip(payload.candidate_ids, scores))])

    return app


app = create_app()
