"""FastAPI application for Web Admin."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from admin.api.router import api_router
from admin.spa_path import index_file_response, static_file_response
from shared.monitor.prometheus_metrics import render_prometheus_metrics


def create_app() -> FastAPI:
    app = FastAPI(
        title="机器草 Web Admin",
        description="Admin panel for 机器草 Bilibili monitoring bot",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics():
        body, content_type = render_prometheus_metrics()
        return Response(content=body, media_type=content_type)

    app.include_router(api_router)

    app_base = (
        Path(sys._MEIPASS)
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent.parent
    )
    web_dist = app_base / "web" / "dist"
    if web_dist.is_dir():
        web_dist = web_dist.resolve()
        assets_dir = web_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            if response := static_file_response(web_dist, full_path):
                return response
            if response := index_file_response(web_dist):
                return response
            raise HTTPException(status_code=404, detail="Not found")

    return app
