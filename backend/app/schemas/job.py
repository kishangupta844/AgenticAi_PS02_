from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from app.models.entities import RequirementType

class ExtractedRequirement(BaseModel):
    title: str
    category: str
    requirement_type: RequirementType
    weight: float
    source_snippet: str

class JobExtractionResult(BaseModel):
    title: str
    company: Optional[str] = None
    role_profile: Optional[dict] = None
    requirements: List[ExtractedRequirement]

class JobImportRequest(BaseModel):
    source_url: Optional[str] = None
    raw_text: Optional[str] = None

class JobResponse(BaseModel):
    id: int
    title: str
    company: Optional[str] = None
    source_url: Optional[str] = None
    raw_text: str
    role_profile: Optional[dict] = None
    created_at: datetime
    requirements: List[dict]
    extraction_source: Optional[str] = None
    llm_model: Optional[str] = None
    source: Optional[str] = None
    external_id: Optional[str] = None
    location: Optional[str] = None
    experience: Optional[str] = None
    salary: Optional[str] = None
    apply_url: Optional[str] = None

class JobUrlSummarizeRequest(BaseModel):
    url: str
    save_job: bool = True
    raw_text: Optional[str] = None

class JobTextSummarizeRequest(BaseModel):
    raw_text: str
    source_url: Optional[str] = None
    save_job: bool = True

class JobUrlSummarizeResponse(BaseModel):
    job: Optional[JobResponse] = None
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    source_url: str
    summary_text: str
    role_profile: Optional[dict] = None
    requirements: List[dict] = []
    extraction_source: Optional[str] = None
    llm_model: Optional[str] = None

class JobListing(BaseModel):
    external_id: str
    source: str = "naukri"
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    experience: Optional[str] = None
    salary: Optional[str] = None
    posted: Optional[str] = None
    skills: List[str] = []
    snippet: Optional[str] = None
    apply_url: str
    logo_url: Optional[str] = None

class NaukriSearchResponse(BaseModel):
    query: str
    location: Optional[str] = None
    page: int
    total: Optional[int] = None
    provider: str
    cached: bool
    results: List[JobListing]

class NaukriImportRequest(BaseModel):
    external_id: str
    apply_url: str
    title: str
    company: Optional[str] = None
    snippet: Optional[str] = None
    location: Optional[str] = None
    experience: Optional[str] = None
    salary: Optional[str] = None
