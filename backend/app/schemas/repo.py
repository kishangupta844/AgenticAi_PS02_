from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class ConnectRepoRequest(BaseModel):
    full_name: str  # e.g., "octocat/Hello-World" or "fastapi/fastapi"
    clone_url: Optional[str] = None
    default_branch: Optional[str] = "main"

class EvidenceSnippet(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    commit_sha: str
    snippet_text: str
    github_url: str
    matched_keyword: str

class RepoInspectResponse(BaseModel):
    repo_id: int
    full_name: str
    default_branch: str
    latest_commit_sha: str
    tree_file_count: int
    sample_files: List[str]

class RepoEvidenceResponse(BaseModel):
    repo_id: int
    full_name: str
    commit_sha: str
    collected_evidences: List[EvidenceSnippet]
