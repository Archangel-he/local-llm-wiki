from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.health import router as health_router
from .api.jobs import router as jobs_router
from .api.model_profiles import router as model_profiles_router
from .api.sources import router as sources_router
from .api.wiki import router as wiki_router
from .api.workspaces import router as workspaces_router
from .config import settings
from .core.errors import RequestIdMiddleware, install_error_handlers

app = FastAPI(
    title="local-llm-wiki",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)
install_error_handlers(app)

app.include_router(health_router, prefix="/api")
app.include_router(workspaces_router, prefix="/api")
app.include_router(model_profiles_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(wiki_router, prefix="/api")


@app.get("/api")
def root():
    return {"app": "local-llm-wiki", "version": "0.1.0"}


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
