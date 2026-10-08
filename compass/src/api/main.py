"""Combined entrypoint:  uvicorn src.api.main:app --port 8000

If the existing logistics app (src/api/app.py) is importable, MEDEVAC routes are
mounted onto it and nothing about it changes (including its CORS settings).
Otherwise a standalone MEDEVAC-only app is created, so the simulator runs with
no Anthropic key and no logistics dependencies.

Set COMPASS_CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173" to override
origins in standalone mode.
"""
import os

from src.api.medevac_routes import router as medevac_router

try:
    from src.api.app import app  # existing contested-logistics app
    MODE = "logistics+medevac"
except Exception as exc:  # missing deps, no key at import time, etc.
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="COMPASS-MEDEVAC (standalone)")
    origins = os.environ.get("COMPASS_CORS_ORIGINS",
                             "http://localhost:5173,http://127.0.0.1:5173").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins],
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    MODE = f"medevac-only ({type(exc).__name__})"

app.include_router(medevac_router)


@app.get("/api/medevac/health")
def medevac_health():
    return {"ok": True, "mode": MODE}
