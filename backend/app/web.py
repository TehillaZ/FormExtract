"""One server for the whole app: the built interface at / and the API at /api.

  python -m uvicorn app.web:root --port 8000      then open http://localhost:8000

For development keep using `app.api.main:app` with the Vite dev server. This module is for running and demoing the
app with one process and no Node: build the interface once (`cd frontend && npm run build`).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.main import app as api
from app.config import ROOT
from app.db.session import init_db, is_initialized

DIST = ROOT / "frontend" / "dist"


class SinglePageApp(StaticFiles):
    """Static files, where any path that is not a file serves index.html, so reloading the page works."""

    async def get_response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code != 404:
                raise
            response = await super().get_response("index.html", scope)
        if response.headers.get("content-type", "").startswith("text/html"):
            # the page names the current script file: it must be re-checked on every visit, or a browser keeps
            # running an old build after the interface was rebuilt (the hashed assets themselves can be cached)
            response.headers["Cache-Control"] = "no-cache"
        return response


def create_web_app(dist: Path = DIST) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if not is_initialized():   # a mounted app does not run its own startup
            init_db()
        yield

    web = FastAPI(title="FormExtract", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    web.mount("/api", api)         # the interface calls /api/..., exactly as the Vite dev proxy does
    if (dist / "index.html").is_file():
        web.mount("/", SinglePageApp(directory=dist, html=True), name="interface")
    else:
        @web.get("/", include_in_schema=False)
        def not_built() -> PlainTextResponse:
            return PlainTextResponse("The interface is not built yet. Run: cd frontend && npm run build", status_code=503)
    return web


root = create_web_app()
