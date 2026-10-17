import json
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.entities import Job, Repository, Requirement, Assessment, Citation, AuditHistory, AssessmentStatus
from app.schemas.assessment import (
    AssessmentRunRequest,
    AssessmentResponse,
    AssessmentSummary,
    SkillAssessmentResult,
    CitationItem,
    ReadinessPrediction,
    LearningResource
)
from app.services.github_scanner import GitHubScannerService
from app.services.assessment_engine import AssessmentEngineService
from app.services.readiness_calculator import ReadinessCalculator
from app.services.resource_finder import ResourceFinderService
from app.services.roadmap_generator import RoadmapGenerator

router = APIRouter()

@router.post("/run", response_model=AssessmentResponse)
async def run_assessment(payload: AssessmentRunRequest, session: Session = Depends(get_session)):
    """
    Run an end-to-end skill assessment and gap analysis for a Job and connected Repository:
    1. Fetches job requirements and repo file tree.
    2. Runs multi-signal alias retrieval and batched role-aware LLM evaluation.
    3. Finds verified learning resources (YouTube + official docs) for every gap.
    4. Computes deterministic, explainable readiness prediction with top drivers, blockers, and what-if.
    5. Persists Assessment, Citation, and AuditHistory records.
    """
    job = session.exec(select(Job).where(Job.id == payload.job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    repo = session.exec(select(Repository).where(Repository.id == payload.repo_id)).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")

    requirements = session.exec(select(Requirement).where(Requirement.job_id == job.id)).all()
    if not requirements:
        raise HTTPException(status_code=400, detail="Job has no extracted requirements.")

    # Ensure latest commit SHA is accurate for the repository
    if not repo.latest_commit_sha or repo.latest_commit_sha == "c9f3e8b417a250d4f9b871c890a1b2c3d4e5f678":
        latest_sha = await GitHubScannerService.get_latest_commit_sha(repo.full_name, repo.default_branch)
        if latest_sha and latest_sha != "c9f3e8b417a250d4f9b871c890a1b2c3d4e5f678":
            repo.latest_commit_sha = latest_sha
            session.add(repo)
            session.commit()
            session.refresh(repo)

    # Get repository file tree
    tree = await GitHubScannerService.get_repo_tree(repo.full_name, repo.latest_commit_sha or "HEAD")
    tree_paths = [item["path"] for item in tree]
    content_cache: dict = {}

    # Run batched, role-aware evaluation
    eval_pack = await AssessmentEngineService.evaluate_all_requirements(
        job=job,
        requirements=requirements,
        repo=repo,
        tree_paths=tree_paths,
        content_cache=content_cache,
        session=session
    )
    skill_results: List[SkillAssessmentResult] = eval_pack["skill_results"]
    llm_rationale: Optional[str] = eval_pack.get("llm_rationale")

    for eval_result in skill_results:
        # Check existing assessment record for this requirement and repo
        existing_assessment = session.exec(
            select(Assessment).where(
                Assessment.requirement_id == eval_result.requirement_id,
                Assessment.repo_id == repo.id
            )
        ).first()

        prev_status = existing_assessment.status.value if existing_assessment else None

        # Build raw response payload including resources and practice task
        persisted_response = dict(eval_result.llm_response or {})
        persisted_response["practice_task"] = eval_result.practice_task
        persisted_response["resources"] = [r.model_dump(mode="json") for r in eval_result.resources]

        if existing_assessment:
            existing_assessment.status = eval_result.status
            existing_assessment.confidence_score = eval_result.confidence_score
            existing_assessment.reason = eval_result.reason
            existing_assessment.llm_model = eval_result.llm_model
            existing_assessment.llm_raw_response = json.dumps(persisted_response)
            existing_assessment.evaluated_at = datetime.now(timezone.utc)
            session.add(existing_assessment)
            session.flush()
            assessment_record = existing_assessment

            # Delete old citations
            old_citations = session.exec(select(Citation).where(Citation.assessment_id == assessment_record.id)).all()
            for old_c in old_citations:
                session.delete(old_c)
        else:
            assessment_record = Assessment(
                requirement_id=eval_result.requirement_id,
                repo_id=repo.id,
                status=eval_result.status,
                confidence_score=eval_result.confidence_score,
                reason=eval_result.reason,
                llm_model=eval_result.llm_model,
                llm_raw_response=json.dumps(persisted_response),
            )
            session.add(assessment_record)
            session.flush()

        # Persist citations
        for cit in eval_result.citations:
            citation_entity = Citation(
                assessment_id=assessment_record.id,
                file_path=cit.file_path,
                start_line=cit.start_line,
                end_line=cit.end_line,
                commit_sha=cit.commit_sha,
                snippet_text=cit.snippet_text,
                github_url=cit.github_url
            )
            session.add(citation_entity)

        # Record audit history on status changes
        if prev_status != eval_result.status.value:
            audit = AuditHistory(
                requirement_id=eval_result.requirement_id,
                previous_status=prev_status,
                new_status=eval_result.status.value,
                trigger_event="manual_assessment_run",
                commit_sha=repo.latest_commit_sha
            )
            session.add(audit)

    session.commit()

    # Determine seniority and repo signals for readiness calculation
    role_prof = {}
    if job.role_profile:
        try:
            role_prof = json.loads(job.role_profile)
        except Exception:
            pass
    seniority = role_prof.get("seniority", "mid")

    repo_signals = {
        "has_tests": any("test" in p.lower() for p in tree_paths),
        "has_ci": any(".github/workflows" in p or "ci" in p.lower() for p in tree_paths),
        "is_tiny_repo": len(tree_paths) < 4
    }

    readiness = ReadinessCalculator.calculate(
        skills=skill_results,
        seniority=seniority,
        repo_signals=repo_signals,
        llm_rationale=llm_rationale
    )

    summary = AssessmentEngineService.calculate_summary(skill_results)

    roadmap = RoadmapGenerator.generate_15_day_roadmap(
        target_role=job.title,
        target_repo=repo.full_name,
        skills=skill_results
    )

    return AssessmentResponse(
        job_id=job.id,
        job_title=job.title,
        repo_id=repo.id,
        repo_full_name=repo.full_name,
        evaluated_at=datetime.now(timezone.utc),
        summary=summary,
        readiness=readiness,
        roadmap=roadmap,
        skill_assessments=skill_results
    )

@router.get("/job/{job_id}", response_model=List[AssessmentResponse])
def get_assessments_for_job(job_id: int, session: Session = Depends(get_session)):
    """Fetch existing assessments grouped by repository for a job."""
    job = session.exec(select(Job).where(Job.id == job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    role_prof = {}
    if job.role_profile:
        try:
            role_prof = json.loads(job.role_profile)
        except Exception:
            pass
    seniority = role_prof.get("seniority", "mid")

    repos = session.exec(select(Repository)).all()
    results = []

    for repo in repos:
        assessments = session.exec(
            select(Assessment).where(
                Assessment.repo_id == repo.id,
                Assessment.requirement_id.in_([r.id for r in job.requirements])
            )
        ).all()

        if assessments:
            skill_results = []
            for a in assessments:
                req = a.requirement
                citations = [
                    CitationItem(
                        file_path=c.file_path,
                        start_line=c.start_line,
                        end_line=c.end_line,
                        commit_sha=c.commit_sha,
                        snippet_text=c.snippet_text,
                        github_url=c.github_url
                    ) for c in a.citations
                ]

                # Extract persisted resources and practice task from llm_raw_response
                res_items = []
                practice_task = None
                parsed_resp = None
                if a.llm_raw_response:
                    try:
                        parsed_resp = json.loads(a.llm_raw_response)
                        practice_task = parsed_resp.get("practice_task")
                        for r_dict in parsed_resp.get("resources", []):
                            res_items.append(LearningResource(**r_dict))
                    except Exception:
                        pass

                skill_results.append(
                    SkillAssessmentResult(
                        requirement_id=req.id,
                        requirement_title=req.title,
                        category=req.category,
                        requirement_type=req.requirement_type.value,
                        weight=req.weight,
                        source_snippet=req.source_snippet,
                        status=a.status,
                        confidence_score=a.confidence_score,
                        reason=a.reason,
                        limitations=[],
                        next_step=None,
                        citations=citations,
                        resources=res_items,
                        practice_task=practice_task,
                        llm_used=bool(a.llm_model),
                        llm_model=a.llm_model,
                        llm_response=parsed_resp,
                    )
                )

            summary = AssessmentEngineService.calculate_summary(skill_results)
            readiness = ReadinessCalculator.calculate(
                skills=skill_results,
                seniority=seniority
            )

            roadmap = RoadmapGenerator.generate_15_day_roadmap(
                target_role=job.title,
                target_repo=repo.full_name,
                skills=skill_results
            )

            results.append(
                AssessmentResponse(
                    job_id=job.id,
                    job_title=job.title,
                    repo_id=repo.id,
                    repo_full_name=repo.full_name,
                    evaluated_at=assessments[0].evaluated_at,
                    summary=summary,
                    readiness=readiness,
                    roadmap=roadmap,
                    skill_assessments=skill_results
                )
            )

    return results

@router.get("/history")
def assessment_history(session: Session = Depends(get_session)):
    """Timeline of status transitions (architecture: Change History)."""
    rows = session.exec(select(AuditHistory).order_by(AuditHistory.created_at.desc())).all()
    return [
        {
            "id": r.id,
            "requirement_id": r.requirement_id,
            "previous_status": r.previous_status,
            "new_status": r.new_status,
            "trigger_event": r.trigger_event,
            "commit_sha": r.commit_sha,
            "created_at": r.created_at,
        }
        for r in rows
    ]

@router.get("/audit/{requirement_id}", response_model=List[AuditHistory])
def get_audit_history(requirement_id: int, session: Session = Depends(get_session)):
    """Fetch timeline of status transitions for a specific job requirement."""
    return session.exec(
        select(AuditHistory).where(AuditHistory.requirement_id == requirement_id).order_by(AuditHistory.created_at.desc())
    ).all()
