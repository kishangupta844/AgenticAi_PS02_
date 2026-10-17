from typing import Optional, List, Dict, Any
from sqlmodel import Session, select
from app.models.entities import Job, Requirement
from app.schemas.job import JobResponse
from app.services.job_extractor import JobExtractorService

def persist_job_and_requirements(
    session: Session,
    raw_text: str,
    source_url: Optional[str] = None,
    source: Optional[str] = "manual",
    external_id: Optional[str] = None,
    override_title: Optional[str] = None,
    override_company: Optional[str] = None,
    location: Optional[str] = None,
    experience: Optional[str] = None,
    salary: Optional[str] = None,
    apply_url: Optional[str] = None
) -> JobResponse:
    """
    Shared helper for /jobs/import and /naukri/import.
    Extracts structured requirements and persists Job + Requirement entities,
    or returns existing job if already persisted with the same (source, external_id).
    """
    # 1. Deduplication check if external_id and source provided
    if source and external_id:
        existing_job = session.exec(
            select(Job).where(Job.source == source, Job.external_id == external_id)
        ).first()
        if existing_job:
            reqs = session.exec(select(Requirement).where(Requirement.job_id == existing_job.id)).all()
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
            return JobResponse(
                id=existing_job.id,
                title=existing_job.title,
                company=existing_job.company,
                source_url=existing_job.source_url,
                raw_text=existing_job.raw_text,
                created_at=existing_job.created_at,
                requirements=req_dicts,
                extraction_source="deduplicated_cache",
                llm_model="cached",
                source=existing_job.source,
                external_id=existing_job.external_id,
                location=existing_job.location,
                experience=existing_job.experience,
                salary=existing_job.salary,
                apply_url=existing_job.apply_url
            )

    # 2. Extract structured requirements via LLM
    extracted = JobExtractorService.extract_requirements(raw_text, source_url)

    job_title = override_title or extracted.title
    job_company = override_company or extracted.company

    # 3. Create Job
    job = Job(
        title=job_title,
        company=job_company,
        source_url=source_url,
        raw_text=raw_text,
        source=source,
        external_id=external_id,
        location=location,
        experience=experience,
        salary=salary,
        apply_url=apply_url
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # 4. Create Requirements
    req_dicts: List[Dict[str, Any]] = []
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

    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        source_url=job.source_url,
        raw_text=job.raw_text,
        created_at=job.created_at,
        requirements=req_dicts,
        extraction_source=JobExtractorService.last_source,
        llm_model=JobExtractorService.last_model,
        source=job.source,
        external_id=job.external_id,
        location=job.location,
        experience=job.experience,
        salary=job.salary,
        apply_url=job.apply_url
    )
