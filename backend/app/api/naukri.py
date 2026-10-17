import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session
from app.core.db import get_session
from app.schemas.job import (
    NaukriSearchResponse,
    JobListing,
    NaukriImportRequest,
    JobResponse
)
from app.services.job_sources.registry import job_source_registry
from app.services.job_importer import persist_job_and_requirements
from app.services.job_fetcher import JobFetcherService

logger = logging.getLogger(__name__)

router = APIRouter()

COMMON_ROLES = [
    "Python Developer",
    "Full Stack Engineer",
    "FastAPI Backend Developer",
    "Data Analyst",
    "DevOps Engineer",
    "Machine Learning Engineer",
    "Frontend Developer",
    "Cloud Architect",
    "Software Engineer",
    "React Developer",
    "Backend Engineer",
    "AI/ML Engineer",
    "Data Scientist",
    "Golang Developer"
]

@router.get("/roles/suggest", response_model=List[str])
def suggest_roles(q: Optional[str] = Query(None, description="Typeahead prefix search for roles")):
    """Static + fast typeahead list of common tech roles."""
    if not q or not q.strip():
        return COMMON_ROLES
    q_lower = q.strip().lower()
    matches = [role for role in COMMON_ROLES if q_lower in role.lower()]
    return matches if matches else [q.strip().title()]

@router.get("/search", response_model=NaukriSearchResponse)
async def search_naukri_jobs(
    role: str = Query(..., min_length=1, max_length=100, description="Job role or search keyword"),
    location: Optional[str] = Query(None, max_length=100, description="Target location / city"),
    experience: Optional[str] = Query(None, max_length=50, description="Experience filter (e.g. 0-2 Yrs)"),
    page: int = Query(1, ge=1, le=50, description="Page number"),
    page_size: int = Query(20, ge=1, le=50, description="Results per page")
):
    """
    Search live jobs from Naukri with resilient fallback and in-memory TTL caching.
    """
    cleaned_role = role.strip()
    if not cleaned_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Job role cannot be empty.", "code": "BAD_INPUT"}
        )

    try:
        results, provider_name, cached = await job_source_registry.search_jobs(
            query=cleaned_role,
            location=location.strip() if location else None,
            experience=experience.strip() if experience else None,
            page=page,
            page_size=page_size
        )
        return NaukriSearchResponse(
            query=cleaned_role,
            location=location,
            page=page,
            total=len(results),
            provider=provider_name,
            cached=cached,
            results=results
        )
    except PermissionError as pe:
        logger.warning("Naukri blocked request: %s", pe)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": "Naukri search is temporarily rate-limited or blocked.", "code": "SOURCE_BLOCKED"}
        )
    except TimeoutError as te:
        logger.warning("Naukri timeout: %s", te)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"detail": "Naukri search request timed out.", "code": "SOURCE_TIMEOUT"}
        )
    except Exception as e:
        logger.error("Unhandled error searching jobs: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": f"Failed to search jobs: {str(e)}", "code": "INTERNAL_ERROR"}
        )

@router.post("/import", response_model=JobResponse)
async def import_naukri_job(
    payload: NaukriImportRequest,
    session: Session = Depends(get_session)
):
    """
    Import a Naukri job into the system:
    1. Fetch full JD text via provider or URL reader (with Jina fallback).
    2. Extract structured requirements via LLM with fallback.
    3. Deduplicate on (source="naukri", external_id).
    4. Persist Job + Requirement entities.
    """
    if not payload.external_id or not payload.apply_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "external_id and apply_url are required.", "code": "BAD_INPUT"}
        )

    # 1. Fetch full description text
    raw_text = None
    try:
        # Check provider's detail fetcher first
        raw_text = await job_source_registry.get_job_detail(payload.external_id, payload.apply_url)
    except Exception as e:
        logger.debug("Provider detail lookup failed: %s", e)

    # 2. If provider detail fetch did not succeed, fetch via JobFetcherService (handles direct + Jina reader)
    if not raw_text or len(raw_text.strip()) < 50:
        if payload.apply_url and payload.apply_url.startswith("http"):
            try:
                raw_text = await JobFetcherService.fetch_url_content(payload.apply_url)
            except Exception as e:
                logger.warning("JobFetcherService URL fetch failed for %s: %s", payload.apply_url, e)

    # 3. If still empty, fall back to snippet or metadata synthesization
    if not raw_text or len(raw_text.strip()) < 30:
        if payload.snippet and len(payload.snippet.strip()) >= 20:
            raw_text = f"Job Title: {payload.title}\nCompany: {payload.company or 'N/A'}\nLocation: {payload.location or 'N/A'}\nExperience: {payload.experience or 'N/A'}\nDescription:\n{payload.snippet}"
        else:
            raw_text = f"Job Title: {payload.title}\nCompany: {payload.company or 'N/A'}\nLocation: {payload.location or 'N/A'}\nExperience: {payload.experience or 'N/A'}\nDescription: Seeking skilled {payload.title} proficient in modern software engineering practices, testing, and deployment."

    try:
        job_response = persist_job_and_requirements(
            session=session,
            raw_text=raw_text,
            source_url=payload.apply_url,
            source="naukri",
            external_id=payload.external_id,
            override_title=payload.title,
            override_company=payload.company,
            location=payload.location,
            experience=payload.experience,
            salary=payload.salary,
            apply_url=payload.apply_url
        )
        return job_response
    except Exception as e:
        logger.error("Failed to extract and persist Naukri job: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": f"Failed to parse and import job: {str(e)}", "code": "EXTRACTION_FAILED"}
        )
