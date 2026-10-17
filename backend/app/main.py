from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.db import init_db
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.repos import router as repos_router
from app.api.assessments import router as assessments_router
from app.api.webhooks import router as webhooks_router
from app.api.naukri import router as naukri_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Set up CORS directly (No Nginx proxy needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|.*\.vercel\.app)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(health_router, prefix=settings.API_V1_STR, tags=["System"])
app.include_router(jobs_router, prefix=f"{settings.API_V1_STR}/jobs", tags=["Jobs"])
app.include_router(naukri_router, prefix=f"{settings.API_V1_STR}/naukri", tags=["Naukri"])
app.include_router(repos_router, prefix=f"{settings.API_V1_STR}/repos", tags=["Repositories"])
app.include_router(assessments_router, prefix=f"{settings.API_V1_STR}/assessments", tags=["Assessments"])
app.include_router(webhooks_router, prefix=f"{settings.API_V1_STR}/webhooks", tags=["Webhooks"])

@app.get("/")
def root():
    return {
        "message": "AI Career Coach API is running.",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health"
    }
