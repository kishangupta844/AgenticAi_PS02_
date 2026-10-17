from typing import List, Optional
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.entities import Job, Requirement, RequirementType
from app.schemas.job import (
    JobImportRequest,
    JobResponse,
    JobUrlSummarizeRequest,
    JobUrlSummarizeResponse,
    JobTextSummarizeRequest,
)
from app.services.job_fetcher import JobFetcherService
from app.services.job_extractor import JobExtractorService

router = APIRouter()

@router.post("/fetch-url", response_model=JobUrlSummarizeResponse)
async def fetch_and_summarize_url(
    payload: JobUrlSummarizeRequest,
    session: Session = Depends(get_session)
):
    """
    Fetch any external job URL, summarize into clean concise necessary data
    using Groq AI LLM, extract structured requirements, and optionally persist the Job.
    """
    if not payload.url or not payload.url.strip():
        raise HTTPException(status_code=400, detail="A valid job URL must be provided.")

    data = None
    try:
        data = await JobFetcherService.summarize_job_url(payload.url)
    except Exception as e:
        url_err = str(e)
        if payload.raw_text and len(payload.raw_text.strip()) >= 20:
            try:
                data = await JobFetcherService.summarize_job_text(payload.raw_text, source_url=payload.url)
            except Exception as e_text:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unable to read external job page ({url_err}), and summarizing provided text also failed: {str(e_text)}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to read external job page from '{payload.url}': {url_err}. You can paste the job description text below and click 'Summarize Text with Groq AI'."
            )

    job_resp = None
    if payload.save_job:
        role_profile_str = json.dumps(data.get("role_profile")) if data.get("role_profile") else None

        job = Job(
            title=data["title"],
            company=data.get("company") or "Direct Posting",
            source_url=data.get("source_url") or payload.url,
            raw_text=data["summary_text"],
            role_profile=role_profile_str,
            location=data.get("location"),
            source="external_url"
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        req_dicts = []
        for req in data.get("requirements", []):
            req_type_enum = RequirementType.REQUIRED
            rt_val = str(req.get("requirement_type", "required")).lower()
            if "prefer" in rt_val:
                req_type_enum = RequirementType.PREFERRED
            elif "bonus" in rt_val:
                req_type_enum = RequirementType.BONUS

            db_req = Requirement(
                job_id=job.id,
                title=req["title"],
                category=req.get("category", "General"),
                requirement_type=req_type_enum,
                weight=float(req.get("weight", 1.0)),
                source_snippet=req.get("source_snippet", "")
            )
            session.add(db_req)
            session.commit()
            session.refresh(db_req)
            req_dicts.append({
                "id": db_req.id,
                "title": db_req.title,
                "category": db_req.category,
                "requirement_type": db_req.requirement_type.value,
                "weight": db_req.weight,
                "source_snippet": db_req.source_snippet
            })

        role_prof_dict = json.loads(job.role_profile) if job.role_profile else None
        job_resp = JobResponse(
            id=job.id,
            title=job.title,
            company=job.company,
            source_url=job.source_url,
            raw_text=job.raw_text,
            role_profile=role_prof_dict,
            created_at=job.created_at,
            requirements=req_dicts,
            extraction_source=data.get("extraction_source"),
            llm_model=data.get("llm_model"),
            location=job.location,
            source=job.source
        )

    return JobUrlSummarizeResponse(
        job=job_resp,
        title=data["title"],
        company=data.get("company"),
        location=data.get("location"),
        source_url=data.get("source_url") or payload.url,
        summary_text=data["summary_text"],
        role_profile=data.get("role_profile"),
        requirements=data.get("requirements", []),
        extraction_source=data.get("extraction_source"),
        llm_model=data.get("llm_model")
    )

@router.post("/summarize-text", response_model=JobUrlSummarizeResponse)
async def summarize_job_text_endpoint(
    payload: JobTextSummarizeRequest,
    session: Session = Depends(get_session)
):
    """
    Summarize raw job description text into structured data using Groq AI LLM.
    """
    if not payload.raw_text or not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="Job description text must be provided.")

    try:
        data = await JobFetcherService.summarize_job_text(payload.raw_text, payload.source_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to summarize job text: {str(e)}")

    job_resp = None
    if payload.save_job:
        role_profile_str = json.dumps(data.get("role_profile")) if data.get("role_profile") else None

        job = Job(
            title=data["title"],
            company=data.get("company") or "Direct Posting",
            source_url=data.get("source_url") or payload.source_url or "",
            raw_text=data["summary_text"],
            role_profile=role_profile_str,
            location=data.get("location"),
            source="manual_text"
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        req_dicts = []
        for req in data.get("requirements", []):
            req_type_enum = RequirementType.REQUIRED
            rt_val = str(req.get("requirement_type", "required")).lower()
            if "prefer" in rt_val:
                req_type_enum = RequirementType.PREFERRED
            elif "bonus" in rt_val:
                req_type_enum = RequirementType.BONUS

            db_req = Requirement(
                job_id=job.id,
                title=req["title"],
                category=req.get("category", "General"),
                requirement_type=req_type_enum,
                weight=float(req.get("weight", 1.0)),
                source_snippet=req.get("source_snippet", "")
            )
            session.add(db_req)
            session.commit()
            session.refresh(db_req)
            req_dicts.append({
                "id": db_req.id,
                "title": db_req.title,
                "category": db_req.category,
                "requirement_type": db_req.requirement_type.value,
                "weight": db_req.weight,
                "source_snippet": db_req.source_snippet
            })

        role_prof_dict = json.loads(job.role_profile) if job.role_profile else None
        job_resp = JobResponse(
            id=job.id,
            title=job.title,
            company=job.company,
            source_url=job.source_url,
            raw_text=job.raw_text,
            role_profile=role_prof_dict,
            created_at=job.created_at,
            requirements=req_dicts,
            extraction_source=data.get("extraction_source"),
            llm_model=data.get("llm_model"),
            location=job.location,
            source=job.source
        )

    return JobUrlSummarizeResponse(
        job=job_resp,
        title=data["title"],
        company=data.get("company"),
        location=data.get("location"),
        source_url=data.get("source_url") or payload.source_url or "",
        summary_text=data["summary_text"],
        role_profile=data.get("role_profile"),
        requirements=data.get("requirements", []),
        extraction_source=data.get("extraction_source"),
        llm_model=data.get("llm_model")
    )

@router.post("/import", response_model=JobResponse)
async def import_job(payload: JobImportRequest, session: Session = Depends(get_session)):
    """Import a job listing from either a source URL (using Groq AI LLM summarizer) or raw text."""
    if not payload.source_url and not payload.raw_text:
        raise HTTPException(status_code=400, detail="Either source_url or raw_text must be provided.")

    raw_text = payload.raw_text
    
    # Check if this is a URL-driven import:
    is_default_placeholder = bool(
        raw_text and "Job Title: Staff Full-Stack AI Engineer" in raw_text and "Apex Innovations" in raw_text
    )
    is_url_mode = bool(payload.source_url and (not raw_text or len(raw_text.strip()) < 20 or is_default_placeholder))

    if is_url_mode and payload.source_url:
        try:
            summarized = await JobFetcherService.summarize_job_url(payload.source_url)
            raw_text = summarized["summary_text"]
            
            role_profile_str = json.dumps(summarized.get("role_profile")) if summarized.get("role_profile") else None
            job = Job(
                title=summarized["title"],
                company=summarized.get("company") or "Direct Posting",
                source_url=payload.source_url,
                raw_text=raw_text,
                role_profile=role_profile_str,
                location=summarized.get("location"),
                source="external_url"
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            req_dicts = []
            for req in summarized.get("requirements", []):
                req_type_enum = RequirementType.REQUIRED
                rt_val = str(req.get("requirement_type", "required")).lower()
                if "prefer" in rt_val:
                    req_type_enum = RequirementType.PREFERRED
                elif "bonus" in rt_val:
                    req_type_enum = RequirementType.BONUS

                db_req = Requirement(
                    job_id=job.id,
                    title=req["title"],
                    category=req.get("category", "General"),
                    requirement_type=req_type_enum,
                    weight=float(req.get("weight", 1.0)),
                    source_snippet=req.get("source_snippet", "")
                )
                session.add(db_req)
                session.commit()
                session.refresh(db_req)
                req_dicts.append({
                    "id": db_req.id,
                    "title": db_req.title,
                    "category": db_req.category,
                    "requirement_type": db_req.requirement_type.value,
                    "weight": db_req.weight,
                    "source_snippet": db_req.source_snippet
                })

            role_prof_dict = json.loads(job.role_profile) if job.role_profile else None
            return JobResponse(
                id=job.id,
                title=job.title,
                company=job.company,
                source_url=job.source_url,
                raw_text=job.raw_text,
                role_profile=role_prof_dict,
                created_at=job.created_at,
                requirements=req_dicts,
                extraction_source=summarized.get("extraction_source"),
                llm_model=summarized.get("llm_model"),
                location=job.location,
                source=job.source
            )
        except Exception as e:
            # If URL fetch failed but raw_text is provided, fall back to extracting that text!
            if raw_text and len(raw_text.strip()) >= 20:
                pass
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unable to read external job page from '{payload.source_url}': {str(e)}. Please paste the job description text below and click 'Parse & Extract'."
                )

    if not raw_text or len(raw_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="The job listing text is too short or empty. Please paste the job description.")

    # Extract structured requirements using LLM (with fallback)
    extracted = JobExtractorService.extract_requirements(raw_text, payload.source_url)

    role_profile_str = json.dumps(extracted.role_profile) if extracted.role_profile else None

    job = Job(
        title=extracted.title,
        company=extracted.company or "Direct Posting",
        source_url=payload.source_url,
        raw_text=raw_text,
        role_profile=role_profile_str
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # Persist Requirements
    req_dicts = []
    for req in extracted.requirements:
        db_req = Requirement(
            job_id=job.id,
            title=req.title,
            category=req.category,
            requirement_type=req.requirement_type,
            weight=req.weight,
            source_snippet=req.source_snippet
        )
        session.add(db_req)
        session.commit()
        session.refresh(db_req)
        req_dicts.append({
            "id": db_req.id,
            "title": db_req.title,
            "category": db_req.category,
            "requirement_type": db_req.requirement_type.value,
            "weight": db_req.weight,
            "source_snippet": db_req.source_snippet
        })

    role_prof_dict = json.loads(job.role_profile) if job.role_profile else None
    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        source_url=job.source_url,
        raw_text=job.raw_text,
        role_profile=role_prof_dict,
        created_at=job.created_at,
        requirements=req_dicts,
        extraction_source=JobExtractorService.last_source,
        llm_model=JobExtractorService.last_model,
    )

@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, session: Session = Depends(get_session)):
    """Fetch job details and its associated structured requirements."""
    import json
    job = session.exec(select(Job).where(Job.id == job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    reqs = session.exec(select(Requirement).where(Requirement.job_id == job.id)).all()
    req_dicts = [
        {
            "id": r.id,
            "title": r.title,
            "category": r.category,
            "requirement_type": r.requirement_type.value,
            "weight": r.weight,
            "source_snippet": r.source_snippet
        }
        for r in reqs
    ]
    role_prof_dict = json.loads(job.role_profile) if job.role_profile else None

    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        source_url=job.source_url,
        raw_text=job.raw_text,
        role_profile=role_prof_dict,
        created_at=job.created_at,
        requirements=req_dicts
    )

@router.get("", response_model=List[JobResponse], include_in_schema=False)
@router.get("/", response_model=List[JobResponse])
def list_jobs(session: Session = Depends(get_session)):
    """List all imported jobs."""
    import json
    jobs = session.exec(select(Job)).all()
    results = []
    for j in jobs:
        reqs = session.exec(select(Requirement).where(Requirement.job_id == j.id)).all()
        role_prof_dict = json.loads(j.role_profile) if j.role_profile else None
        results.append(
            JobResponse(
                id=j.id,
                title=j.title,
                company=j.company,
                source_url=j.source_url,
                raw_text=j.raw_text,
                role_profile=role_prof_dict,
                created_at=j.created_at,
                requirements=[
                    {
                        "id": r.id,
                        "title": r.title,
                        "category": r.category,
                        "requirement_type": r.requirement_type.value,
                        "weight": r.weight,
                        "source_snippet": r.source_snippet
                    }
                    for r in reqs
                ]
            )
        )
    return results
