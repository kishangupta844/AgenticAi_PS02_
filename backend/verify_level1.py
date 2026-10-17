import os
import sys

# Ensure backend root is in sys.path
backend_path = os.path.dirname(os.path.abspath(__file__))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlmodel import Session, select
from app.core.db import engine, init_db
from app.models.entities import (
    Job, Requirement, RequirementType, Repository,
    Assessment, AssessmentStatus, Citation, AuditHistory
)

def run_db_verification():
    print("Initializing Database...")
    init_db()
    print("Database tables created successfully!")

    with Session(engine) as session:
        # Create a test job
        job = Job(
            title="Senior Full-Stack Engineer",
            company="TechCorp",
            source_url="https://example.com/jobs/123",
            raw_text="Must have experience with Python, FastAPI, React, and PostgreSQL."
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        print(f"Created Job: ID={job.id}, Title='{job.title}'")

        # Create requirements for the job
        req1 = Requirement(
            job_id=job.id,
            title="FastAPI Backend Development",
            category="Frameworks",
            requirement_type=RequirementType.REQUIRED,
            weight=1.5,
            source_snippet="Must have experience with Python, FastAPI"
        )
        req2 = Requirement(
            job_id=job.id,
            title="PostgreSQL Database Design",
            category="Databases",
            requirement_type=RequirementType.REQUIRED,
            weight=1.2,
            source_snippet="and PostgreSQL."
        )
        session.add(req1)
        session.add(req2)
        session.commit()
        session.refresh(req1)
        session.refresh(req2)
        print(f"Created Requirements: req1={req1.id}, req2={req2.id}")

        # Create a repository
        repo = Repository(
            full_name="candidate/portfolio-api",
            clone_url="https://github.com/candidate/portfolio-api.git",
            default_branch="main",
            latest_commit_sha="a1b2c3d4e5f67890"
        )
        session.add(repo)
        session.commit()
        session.refresh(repo)
        print(f"Created Repository: ID={repo.id}, FullName='{repo.full_name}'")

        # Create an assessment
        assessment = Assessment(
            requirement_id=req1.id,
            repo_id=repo.id,
            status=AssessmentStatus.MET,
            confidence_score=0.95,
            reason="Found FastAPI application with routers, middleware, and dependency injection."
        )
        session.add(assessment)
        session.commit()
        session.refresh(assessment)
        print(f"Created Assessment: ID={assessment.id}, Status='{assessment.status.value}'")

        # Create citation for assessment
        citation = Citation(
            assessment_id=assessment.id,
            file_path="src/main.py",
            start_line=10,
            end_line=25,
            commit_sha=repo.latest_commit_sha,
            snippet_text="app = FastAPI()\napp.include_router(api_router)",
            github_url=f"https://github.com/{repo.full_name}/blob/{repo.latest_commit_sha}/src/main.py#L10-L25"
        )
        session.add(citation)
        session.commit()
        session.refresh(citation)
        print(f"Created Citation: ID={citation.id}, Range='{citation.file_path}#L{citation.start_line}-L{citation.end_line}'")

        # Create audit history record
        audit = AuditHistory(
            requirement_id=req1.id,
            previous_status="unmet",
            new_status="met",
            trigger_event="initial_scan",
            commit_sha=repo.latest_commit_sha
        )
        session.add(audit)
        session.commit()
        print("Created Audit History record successfully!")

        job_id = job.id
        assessment_id = assessment.id

    print("\nVerifying database relationships and queries:")
    with Session(engine) as session:
        fetched_job = session.exec(select(Job).where(Job.id == job_id)).first()
        assert fetched_job is not None
        assert len(fetched_job.requirements) == 2
        print(f"Verified Job '{fetched_job.title}' with {len(fetched_job.requirements)} requirements.")

        fetched_assessment = session.exec(select(Assessment).where(Assessment.id == assessment_id)).first()
        assert fetched_assessment is not None
        assert len(fetched_assessment.citations) == 1
        print(f"Verified Assessment '{fetched_assessment.requirement.title}' with citation on '{fetched_assessment.citations[0].file_path}'.")

    print("\nALL LEVEL 1 DATA MODEL & DB CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_db_verification()
