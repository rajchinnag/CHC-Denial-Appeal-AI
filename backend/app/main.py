from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.routers import claims
from app.routes import auth, registration

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="CHC Denial Appeal AI", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims.router, prefix="/api")
app.include_router(auth.router)
app.include_router(registration.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "gemini_mode": settings.GEMINI_MODE}
