from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.entities import AssessmentStatus

class CitationItem(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    commit_sha: str
    snippet_text: str
    github_url: Optional[str] = None
    is_dependency_or_doc_only: bool = False
    repo_full_name: Optional[str] = None

class LearningResource(BaseModel):
    id: Optional[str] = None
    skill: str
    requirement_id: Optional[int] = None
    title: str
    url: str
    type: str  # "youtube" | "docs" | "article" | "course"
    channel_or_site: Optional[str] = None
    duration_minutes: Optional[int] = None
    why_relevant: Optional[str] = None
    level: str = "all"  # "intern" | "junior" | "mid" | "senior" | "lead" | "all"
    verified_at: Optional[datetime] = None

class ReadinessDriver(BaseModel):
    skill: str
    impact: str  # e.g., "+18% readiness boost" or "-22% missing core requirement"
    status: str

class WhatIfScore(BaseModel):
    projected_score: float
    projected_band: str
    gain: float
    closed_gaps: List[str]

class ReadinessPrediction(BaseModel):
    score: int  # 0 - 100
    band: str  # "Not ready" | "Stretch" | "Competitive" | "Strong"
    confidence: str  # "low" | "medium" | "high"
    rationale: str
    top_drivers: List[ReadinessDriver] = []
    top_blockers: List[ReadinessDriver] = []
    what_if: Optional[WhatIfScore] = None
    disclaimer: str = "This readiness prediction is an evidence-based estimate derived solely from public repository code and does not represent a hiring guarantee. 'Unmet' indicates evidence was not found in the inspected repository files, not that the user lacks the skill."

class RoadmapTask(BaseModel):
    day: int  # 1 to 15
    day_title: str  # e.g. "Day 1-2: Core Async Endpoint & Error Model"
    target_skill: str
    action_goal: str
    code_task: str
    verification_step: str
    recommended_resources: List[LearningResource] = []

class RoadmapPhase(BaseModel):
    phase_number: int  # 1 to 3
    title: str  # e.g. "Phase 1: Closing Critical Architecture & Backend Gaps (Days 1-5)"
    day_range: str  # "Days 1-5"
    focus_skills: List[str]
    tasks: List[RoadmapTask] = []
    milestone: str

class RoadmapPlan(BaseModel):
    title: str = "15-Day Targeted Skill Gap Implementation Plan"
    target_role: str
    target_repo: str
    duration_days: int = 15
    summary: str
    phases: List[RoadmapPhase] = []
    expected_outcome: str

class SkillAssessmentResult(BaseModel):
    requirement_id: int
    requirement_title: str
    category: str
    requirement_type: str
    weight: float
    source_snippet: str
    status: AssessmentStatus
    confidence_score: float
    reason: str
    limitations: List[str] = []
    next_step: Optional[str] = None
    citations: List[CitationItem] = []
    resources: List[LearningResource] = []
    practice_task: Optional[str] = None
    winning_repo: Optional[str] = None
    llm_used: bool = False
    llm_model: Optional[str] = None
    llm_response: Optional[dict] = None

class AssessmentRunRequest(BaseModel):
    job_id: int
    repo_id: int

class MultiRepoAssessmentRequest(BaseModel):
    job_id: int
    repo_ids: List[int]

class RepoContribution(BaseModel):
    repo_id: int
    repo_full_name: str
    skills_met: int
    skills_partial: int
    score_percentage: float

class AssessmentSummary(BaseModel):
    total_skills: int
    met: int
    partial: int
    unmet: int
    needs_review: int = 0
    overall_match_percentage: float
    weighted_score: float

class AssessmentResponse(BaseModel):
    job_id: int
    job_title: str
    repo_id: int
    repo_full_name: str
    evaluated_at: datetime
    summary: AssessmentSummary
    readiness: Optional[ReadinessPrediction] = None
    roadmap: Optional[RoadmapPlan] = None
    skill_assessments: List[SkillAssessmentResult]

class MultiRepoAssessmentResponse(BaseModel):
    job_id: int
    job_title: str
    repos: List[str]
    summary: AssessmentSummary
    repo_contributions: List[RepoContribution] = []
    skill_assessments: List[SkillAssessmentResult]

