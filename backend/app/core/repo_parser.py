import re
from typing import Optional, Tuple
from urllib.parse import urlparse

REPO_NAME_REGEX = re.compile(r"^[A-Za-z0-9_.-]+$")

def parse_github_repo(input_str: Optional[str]) -> Optional[Tuple[str, str, str]]:
    """
    Normalizes and parses a GitHub repository input string.
    Returns (owner, repo, full_name) or None if invalid.
    
    Accepts:
    - "owner/repo"
    - "https://github.com/owner/repo" (http, www, query params, subpaths like /tree/..., trailing slashes)
    - "git@github.com:owner/repo.git"
    """
    if not input_str or not isinstance(input_str, str):
        return None
    raw = input_str.strip()
    if not raw:
        return None

    # Strip decorator suffix if present (e.g. " (main) - SHA: 1234567")
    raw = re.sub(r"\s*\([^)]*\)\s*-\s*SHA:.*$", "", raw, flags=re.IGNORECASE).strip()
    if not raw:
        return None

    # SSH format: git@github.com:owner/repo(.git)?
    ssh_match = re.match(r"^git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$", raw, re.IGNORECASE)
    if ssh_match:
        owner, repo = ssh_match.group(1), ssh_match.group(2)
        if REPO_NAME_REGEX.match(owner) and REPO_NAME_REGEX.match(repo):
            return owner, repo, f"{owner}/{repo}"
        return None

    # URL format
    if re.match(r"^(https?:)?//", raw, re.IGNORECASE) or raw.lower().startswith("www.github.com") or raw.lower().startswith("github.com"):
        normalized = raw
        if not re.match(r"^[a-zA-Z]+://", normalized):
            normalized = "https://" + re.sub(r"^//", "", normalized)
        try:
            parsed = urlparse(normalized)
            hostname = (parsed.hostname or "").lower()
            if hostname not in ("github.com", "www.github.com"):
                return None
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) < 2:
                return None
            owner = parts[0]
            repo = re.sub(r"\.git$", "", parts[1], flags=re.IGNORECASE)
            if REPO_NAME_REGEX.match(owner) and REPO_NAME_REGEX.match(repo):
                return owner, repo, f"{owner}/{repo}"
            return None
        except Exception:
            return None

    # Direct owner/repo
    cleaned = raw.rstrip("/")
    parts = cleaned.split("/")
    if len(parts) >= 2:
        owner = parts[0]
        repo = re.sub(r"\.git$", "", parts[1], flags=re.IGNORECASE)
        if REPO_NAME_REGEX.match(owner) and REPO_NAME_REGEX.match(repo):
            return owner, repo, f"{owner}/{repo}"

    return None
