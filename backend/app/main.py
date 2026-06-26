from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import claims

app = FastAPI(title="CHC Denial Appeal AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "gemini_mode": settings.GEMINI_MODE}
