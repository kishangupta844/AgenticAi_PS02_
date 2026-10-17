from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.entities import Repository, Requirement
from app.schemas.repo import (
    ConnectRepoRequest,
    RepoInspectResponse,
    RepoEvidenceResponse,
    EvidenceSnippet
)
from app.services.github_scanner import GitHubScannerService

router = APIRouter()

from app.core.repo_parser import parse_github_repo

@router.get("/lookup")
async def lookup_repository(name_or_url: str = Query(..., description="GitHub owner/repo or full GitHub URL")):
    """Verify repo existence and get default branch & latest commit SHA using normalized input."""
    parsed = parse_github_repo(name_or_url)
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid repository format. Please enter 'owner/repo' or a valid GitHub URL.")
    
    owner, repo_name, full_name = parsed
    details = await GitHubScannerService.get_repo_details(full_name)
    if details.get("status") == 404:
        raise HTTPException(status_code=404, detail="Repository not found or is private.")
    elif details.get("status") in (403, 429):
        raise HTTPException(status_code=details.get("status"), detail=details.get("error", "GitHub API rate limit exceeded."))
    elif details.get("status") != 200:
        raise HTTPException(status_code=502, detail=details.get("error", "Failed to resolve repository from GitHub."))
    
    branch = details.get("default_branch", "main")
    sha = await GitHubScannerService.get_latest_commit_sha(full_name, branch)
    return {
        "owner": owner,
        "repo": repo_name,
        "full_name": full_name,
        "default_branch": branch,
        "latest_commit_sha": sha,
        "clone_url": details.get("clone_url", f"https://github.com/{full_name}.git")
    }

@router.post("/connect", response_model=Repository)
async def connect_repository(payload: ConnectRepoRequest, session: Session = Depends(get_session)):
    """Connect a GitHub repository to the coach and resolve its HEAD commit SHA. Accepts raw input or owner/repo."""
    parsed = parse_github_repo(payload.full_name)
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid repository format. Please enter 'owner/repo' or a valid GitHub URL.")
    
    owner, repo_name, full_name = parsed

    # Check if already connected
    existing = session.exec(select(Repository).where(Repository.full_name == full_name)).first()
    
    # Try fetching repo details to confirm default branch
    repo_details = await GitHubScannerService.get_repo_details(full_name)
    default_branch = payload.default_branch or (repo_details.get("default_branch") if repo_details.get("status") == 200 else "main")
    sha = await GitHubScannerService.get_latest_commit_sha(full_name, default_branch)
    clone_url = payload.clone_url or repo_details.get("clone_url") or f"https://github.com/{full_name}.git"

    if existing:
        existing.latest_commit_sha = sha
        existing.default_branch = default_branch
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    repo = Repository(
        full_name=full_name,
        clone_url=clone_url,
        default_branch=default_branch,
        latest_commit_sha=sha
    )
    session.add(repo)
    session.commit()
    session.refresh(repo)
    return repo

@router.get("/{repo_id}/inspect", response_model=RepoInspectResponse)
async def inspect_repository(repo_id: int, session: Session = Depends(get_session)):
    """Inspect the repository tree and latest commit SHA."""
    repo = session.exec(select(Repository).where(Repository.id == repo_id)).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")

    tree = await GitHubScannerService.get_repo_tree(repo.full_name, repo.latest_commit_sha or "main")
    file_paths = [item["path"] for item in tree]

    return RepoInspectResponse(
        repo_id=repo.id,
        full_name=repo.full_name,
        default_branch=repo.default_branch,
        latest_commit_sha=repo.latest_commit_sha or "HEAD",
        tree_file_count=len(file_paths),
        sample_files=file_paths[:15]
    )

@router.get("/{repo_id}/evidence", response_model=RepoEvidenceResponse)
async def collect_repo_evidence(
    repo_id: int,
    keywords: Optional[str] = Query(None, description="Comma-separated skills to search, e.g. 'FastAPI,Docker,PostgreSQL'"),
    session: Session = Depends(get_session)
):
    """Scan repo files for skill evidence and return citations with exact line numbers and commit SHA."""
    repo = session.exec(select(Repository).where(Repository.id == repo_id)).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")

    # Parse keywords to search
    target_keywords = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else ["FastAPI", "Python", "Docker"]

    tree = await GitHubScannerService.get_repo_tree(repo.full_name, repo.latest_commit_sha or "main")
    collected: List[EvidenceSnippet] = []

    # Filter candidate code and config files (skip binaries, images, lockfiles)
    candidate_extensions = (
        ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
        ".sql", ".yml", ".yaml", "Dockerfile", "requirements.txt", "package.json"
    )

    for item in tree:
        path = item.get("path", "")
        if any(path.endswith(ext) or path == ext for ext in candidate_extensions):
            content = await GitHubScannerService.fetch_file_content(repo.full_name, path, repo.latest_commit_sha or "main")
            if content:
                for kw in target_keywords:
                    snippets = GitHubScannerService.extract_line_range_snippets(
                        code_text=content,
                        keyword=kw,
                        file_path=path,
                        commit_sha=repo.latest_commit_sha or "HEAD",
                        owner_repo=repo.full_name
                    )
                    collected.extend(snippets)

    return RepoEvidenceResponse(
        repo_id=repo.id,
        full_name=repo.full_name,
        commit_sha=repo.latest_commit_sha or "HEAD",
        collected_evidences=collected
    )

@router.get("", response_model=List[Repository], include_in_schema=False)
@router.get("/", response_model=List[Repository])
def list_repositories(session: Session = Depends(get_session)):
    """List all connected repositories."""
    return session.exec(select(Repository)).all()
