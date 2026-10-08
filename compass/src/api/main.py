"""Combined entrypoint:  uvicorn src.api.main:app --port 8000

If the existing logistics app (src/api/app.py) is importable, MEDEVAC routes are
mounted onto it and nothing about it changes (including its CORS settings).
Otherwise a standalone MEDEVAC-only app is created, so the simulator runs with
no Anthropic key and no logistics dependencies.

Set COMPASS_CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173" to override
origins in standalone mode.
"""
import base64
import os
import secrets
from pathlib import Path

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


# --- Optional shared-demo hardening -----------------------------------------
# COMPASS_ACCESS_CODE: if set, every request must carry it as the HTTP Basic
# password (any username). Browsers prompt once and then remember it, so the
# served web app needs no changes. Unset = open (fine for localhost only).
_CODE = os.environ.get("COMPASS_ACCESS_CODE", "")
if _CODE:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response

    async def _gate(request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        hdr = request.headers.get("authorization", "")
        if hdr.lower().startswith("basic "):
            try:
                pw = base64.b64decode(hdr[6:]).decode("utf-8", "ignore").split(":", 1)[-1]
            except Exception:
                pw = ""
            if secrets.compare_digest(pw.encode(), _CODE.encode()):
                return await call_next(request)
        return Response("Access code required", status_code=401,
                        headers={"WWW-Authenticate": 'Basic realm="COMPASS demo"'})

    app.add_middleware(BaseHTTPMiddleware, dispatch=_gate)

# --- Serve the built web app (frontend `npm run build` output) ---------------
# Put the contents of frontend/dist in <app folder>/web (or set COMPASS_WEB_DIR).
# Mounted last so every /api route keeps priority.
_WEB = Path(os.environ.get("COMPASS_WEB_DIR", Path(__file__).resolve().parents[2] / "web"))
if (_WEB / "index.html").is_file():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_WEB), html=True), name="web")
    MODE += "+web"
