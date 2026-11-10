"""Context Intelligence gateway — FastAPI app (Phase 0 skeleton).

Exposes the health check and the shape of the MCP-aligned context/memory API.
Retrieval and persistence are implemented in Phase 2; endpoints here return
NotImplemented so the contract is visible and testable end-to-end early.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import __version__
from .config import Settings

settings = Settings.from_env()

app = FastAPI(
    title="Context Intelligence Gateway",
    version=__version__,
    description=f"CI {settings.edition.value} edition — context & memory API",
)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "edition": settings.edition.value, "version": __version__}


# --- request/response contracts -------------------------------------------
class ContextPackRequest(BaseModel):
    project_id: str
    repository_id: str | None = None
    task: str = Field(min_length=1)
    token_budget: int = Field(default=6000, ge=500, le=32000)
    tenant_id: str | None = None  # required for CI-Metis


class MemoryProposal(BaseModel):
    type: str
    title: str
    content: str
    project: str | None = None
    repository: str | None = None
    evidence_ids: list[str] = []
    tenant_id: str | None = None


# --- MCP-aligned endpoints (stubs; Phase 2) --------------------------------
@app.post("/v1/context/pack")
def get_context_pack(req: ContextPackRequest) -> dict:
    # TODO(Phase 2): authenticate caller -> resolve authorised scope ->
    # hybrid search -> rerank -> dedup -> pack to token budget -> cite.
    raise HTTPException(status_code=501, detail="context.pack not implemented (Phase 2)")


@app.post("/v1/memory/propose")
def propose_memory(proposal: MemoryProposal) -> dict:
    # TODO(Phase 2): validate scope, redact, store as 'proposed' for review.
    raise HTTPException(status_code=501, detail="memory.propose not implemented (Phase 2)")
