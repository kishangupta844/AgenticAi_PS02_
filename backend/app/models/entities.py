from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RequirementType(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    BONUS = "bonus"


class AssessmentStatus(str, Enum):
    MET = "met"
    PARTIAL = "partial"
    UNMET = "unmet"
    NEEDS_REVIEW = "needs_review"


# 1. Job Entity
class JobBase(SQLModel):
    title: str
    company: Optional[str] = None
    source_url: Optional[str] = None
    raw_text: str
    role_profile: Optional[str] = None  # JSON string: seniority, domain, skill_depths
    source: Optional[str] = None          # "naukri", "manual", "url"
    external_id: Optional[str] = None     # external job ID from provider
    location: Optional[str] = None
    experience: Optional[str] = None
    salary: Optional[str] = None
    apply_url: Optional[str] = None


class Job(JobBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_utc_now)

    requirements: List["Requirement"] = Relationship(back_populates="job")


# 2. Requirement Entity
class RequirementBase(SQLModel):
    title: str
    category: str  # e.g., "Languages", "Frameworks", "Architecture", "Databases"
    requirement_type: RequirementType = Field(default=RequirementType.REQUIRED)
    weight: float = Field(default=1.0)
    source_snippet: str  # Exact sentence/excerpt from the job posting
    aliases: Optional[str] = None  # JSON string of list of aliases/synonyms/imports


class Requirement(RequirementBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    created_at: datetime = Field(default_factory=get_utc_now)

    job: Optional[Job] = Relationship(back_populates="requirements")
    assessments: List["Assessment"] = Relationship(back_populates="requirement")
    audit_history: List["AuditHistory"] = Relationship(back_populates="requirement")


# Learning Resource Cache Entity
class LearningResourceCache(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cache_key: str = Field(index=True, unique=True)  # normalized_skill:level
    skill: str
    level: str  # intern, junior, mid, senior, lead
    resources_json: str  # JSON list of LearningResource objects
    created_at: datetime = Field(default_factory=get_utc_now)
    expires_at: datetime


# 3. Repository Entity
class RepositoryBase(SQLModel):
    full_name: str  # e.g. "octocat/Hello-World"
    clone_url: str
    default_branch: str = "main"
    latest_commit_sha: Optional[str] = None


class Repository(RepositoryBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    connected_at: datetime = Field(default_factory=get_utc_now)

    assessments: List["Assessment"] = Relationship(back_populates="repository")


# 4. Assessment Entity
class AssessmentBase(SQLModel):
    status: AssessmentStatus = Field(default=AssessmentStatus.UNMET)
    confidence_score: float = Field(default=0.0)  # 0.0 to 1.0
    reason: str
    llm_model: Optional[str] = None
    llm_raw_response: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=get_utc_now)


class Assessment(AssessmentBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    requirement_id: int = Field(foreign_key="requirement.id", index=True)
    repo_id: int = Field(foreign_key="repository.id", index=True)

    requirement: Optional[Requirement] = Relationship(back_populates="assessments")
    repository: Optional[Repository] = Relationship(back_populates="assessments")
    citations: List["Citation"] = Relationship(back_populates="assessment")


# 5. Citation Entity
class CitationBase(SQLModel):
    file_path: str
    start_line: int
    end_line: int
    commit_sha: str
    snippet_text: str
    github_url: Optional[str] = None


class Citation(CitationBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    assessment_id: int = Field(foreign_key="assessment.id", index=True)

    assessment: Optional[Assessment] = Relationship(back_populates="citations")


# 6. Audit History Entity
class AuditHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    requirement_id: int = Field(foreign_key="requirement.id", index=True)
    previous_status: Optional[str] = None
    new_status: str
    trigger_event: str  # e.g. "initial_scan", "github_webhook_push"
    commit_sha: Optional[str] = None
    created_at: datetime = Field(default_factory=get_utc_now)

    requirement: Optional[Requirement] = Relationship(back_populates="audit_history")


# 7. Webhook Event Entity (Deduplication & Pipeline Status)
class WebhookEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    delivery_id: str = Field(unique=True, index=True)
    event_type: str = Field(default="push")
    repository_full_name: str = Field(index=True)
    sender_login: Optional[str] = None
    commit_sha: Optional[str] = None
    status: str = Field(default="received")  # received | processing | completed | failed | ignored
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=get_utc_now)
    completed_at: Optional[datetime] = None

