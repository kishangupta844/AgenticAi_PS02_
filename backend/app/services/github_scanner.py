import os
import re
import httpx
from typing import List, Dict, Optional, Tuple, Any
from app.core.config import settings
from app.schemas.repo import EvidenceSnippet

class GitHubScannerService:
    BASE_URL = "https://api.github.com"

    @classmethod
    def _get_headers(cls) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Career-Coach/1.0"
        }
        token = settings.GITHUB_TOKEN or os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers
    @classmethod
    async def get_repo_details(cls, owner_repo: str) -> Dict[str, Any]:
        """Fetch repo details from GitHub (GET /repos/{owner}/{repo}) to verify existence and get default branch."""
        url = f"{cls.BASE_URL}/repos/{owner_repo}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=cls._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "status": 200,
                        "default_branch": data.get("default_branch", "main"),
                        "clone_url": data.get("clone_url", f"https://github.com/{owner_repo}.git"),
                        "full_name": data.get("full_name", owner_repo)
                    }
                elif resp.status_code == 404:
                    return {"status": 404, "error": "Repository not found or is private."}
                elif resp.status_code in (403, 429):
                    return {"status": resp.status_code, "error": "GitHub API rate limit exceeded. Please wait or set GITHUB_TOKEN."}
                else:
                    return {"status": resp.status_code, "error": f"GitHub returned HTTP {resp.status_code}"}
        except Exception as e:
            # If offline / network error, return offline fallback status
            return {"status": 503, "error": f"Network error contacting GitHub: {str(e)}"}

    @classmethod
    async def get_latest_commit_sha(cls, owner_repo: str, branch: Optional[str] = None) -> str:
        """Fetch latest commit SHA for the given repository, falling back gracefully if branch is unknown."""
        urls_to_try = []
        if branch:
            urls_to_try.append(f"{cls.BASE_URL}/repos/{owner_repo}/commits/{branch}")
        # Always allow query without branch to get default branch's HEAD commit
        urls_to_try.append(f"{cls.BASE_URL}/repos/{owner_repo}/commits?per_page=1")
        if not branch:
            urls_to_try.append(f"{cls.BASE_URL}/repos/{owner_repo}/commits/main")
            urls_to_try.append(f"{cls.BASE_URL}/repos/{owner_repo}/commits/master")

        for url in urls_to_try:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=cls._get_headers())
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            return data[0].get("sha", "")
                        elif isinstance(data, dict):
                            return data.get("sha", "")
            except Exception as e:
                print(f"Failed to fetch commit SHA from {url}: {e}")

        # Return a deterministic fallback SHA only if network completely failed
        return "c9f3e8b417a250d4f9b871c890a1b2c3d4e5f678"

    _zip_cache: Dict[str, Any] = {}

    @classmethod
    async def _get_repo_archive_zip(cls, owner_repo: str, ref: str = "HEAD") -> Optional[Any]:
        """Download and cache repo zip archive in memory using public codeload without GitHub API rate limits."""
        cache_key = f"{owner_repo}@{ref}"
        if cache_key in cls._zip_cache:
            return cls._zip_cache[cache_key]

        refs_to_try = [ref]
        if ref in ("HEAD", "main", "master", "c9f3e8b417a250d4f9b871c890a1b2c3d4e5f678"):
            refs_to_try = ["HEAD", "main", "master"]

        import io
        import zipfile

        for r in refs_to_try:
            urls = [
                f"https://codeload.github.com/{owner_repo}/zip/refs/heads/{r}" if r in ("main", "master") else f"https://codeload.github.com/{owner_repo}/zip/{r}",
                f"https://github.com/{owner_repo}/archive/{r}.zip"
            ]
            for url in urls:
                try:
                    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                        if resp.status_code == 200 and len(resp.content) > 100:
                            z = zipfile.ZipFile(io.BytesIO(resp.content))
                            cls._zip_cache[cache_key] = z
                            return z
                except Exception as e:
                    pass

        return None

    @classmethod
    async def get_repo_tree(cls, owner_repo: str, commit_sha: str) -> List[Dict[str, str]]:
        """Fetch git tree recursively for a given commit SHA with rate-limit resilient codeload fallback."""
        real_sha = commit_sha
        if not real_sha or real_sha == "c9f3e8b417a250d4f9b871c890a1b2c3d4e5f678":
            resolved = await cls.get_latest_commit_sha(owner_repo)
            if resolved and resolved != "c9f3e8b417a250d4f9b871c890a1b2c3d4e5f678":
                real_sha = resolved

        # 1. Try official GitHub API git tree
        url = f"{cls.BASE_URL}/repos/{owner_repo}/git/trees/{real_sha}?recursive=1"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=cls._get_headers())
                if resp.status_code == 200:
                    tree_data = resp.json().get("tree", [])
                    return [item for item in tree_data if item.get("type") == "blob"]
                elif resp.status_code in (404, 422):
                    head_url = f"{cls.BASE_URL}/repos/{owner_repo}/git/trees/HEAD?recursive=1"
                    h_resp = await client.get(head_url, headers=cls._get_headers())
                    if h_resp.status_code == 200:
                        tree_data = h_resp.json().get("tree", [])
                        return [item for item in tree_data if item.get("type") == "blob"]
        except Exception as e:
            print(f"Failed to fetch tree from GitHub API for {owner_repo}: {e}")

        # 2. Rate-limit resilient fallback: Download repository archive zip from codeload.github.com
        try:
            z = await cls._get_repo_archive_zip(owner_repo, real_sha or "HEAD")
            if z:
                extracted_tree = []
                # First segment is root folder like 'fastapi-master/'
                for name in z.namelist():
                    if name.endswith("/"):
                        continue
                    parts = name.split("/", 1)
                    rel_path = parts[1] if len(parts) > 1 else name
                    extracted_tree.append({"path": rel_path, "type": "blob", "size": 1000})
                if extracted_tree:
                    return extracted_tree
        except Exception as e:
            print(f"Failed to parse codeload zip for {owner_repo}: {e}")

        # Only use local files if the repo is explicitly a mock/local portfolio repository
        if owner_repo.startswith("candidate/") or owner_repo.startswith("local/"):
            return [
                {"path": "backend/app/main.py", "type": "blob", "size": 1500},
                {"path": "backend/app/core/db.py", "type": "blob", "size": 800},
                {"path": "backend/app/api/jobs.py", "type": "blob", "size": 2500},
                {"path": "backend/app/models/entities.py", "type": "blob", "size": 3200},
                {"path": "Dockerfile", "type": "blob", "size": 400},
                {"path": "requirements.txt", "type": "blob", "size": 200},
                {"path": "frontend/src/App.tsx", "type": "blob", "size": 1800},
                {"path": ".github/workflows/ci.yml", "type": "blob", "size": 650}
            ]

        return []

    @classmethod
    async def fetch_file_content(cls, owner_repo: str, file_path: str, commit_sha: str) -> Optional[str]:
        """Fetch raw content of a specific file at commit SHA from GitHub. Never leaks local project files for remote repos."""
        # 1. Try raw.githubusercontent.com first
        raw_urls = [
            f"https://raw.githubusercontent.com/{owner_repo}/{commit_sha}/{file_path}"
        ]
        if commit_sha in ("c9f3e8b417a250d4f9b871c890a1b2c3d4e5f678", "HEAD", "main", "master"):
            raw_urls.extend([
                f"https://raw.githubusercontent.com/{owner_repo}/HEAD/{file_path}",
                f"https://raw.githubusercontent.com/{owner_repo}/main/{file_path}",
                f"https://raw.githubusercontent.com/{owner_repo}/master/{file_path}"
            ])

        for r_url in raw_urls:
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(r_url)
                    if resp.status_code == 200:
                        return resp.text
            except Exception:
                pass

        # 2. Try codeload zip archive cache
        try:
            z = await cls._get_repo_archive_zip(owner_repo, commit_sha or "HEAD")
            if z:
                # Find matching filename in zip archive
                target_suffix = "/" + file_path.replace("\\", "/").lstrip("/")
                for name in z.namelist():
                    norm_name = "/" + name.replace("\\", "/").lstrip("/")
                    if norm_name.endswith(target_suffix):
                        data = z.read(name)
                        return data.decode("utf-8", errors="ignore")
        except Exception:
            pass

        # 3. Try GitHub API contents endpoint (if token is available)
        try:
            api_url = f"{cls.BASE_URL}/repos/{owner_repo}/contents/{file_path}?ref={commit_sha}"
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(api_url, headers=cls._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    import base64
                    if data.get("encoding") == "base64" and data.get("content"):
                        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        except Exception:
            pass

        # STRICT ISOLATION: Local file fallback is ONLY permitted for local/candidate synthetic mock repos
        if owner_repo.startswith("candidate/") or owner_repo.startswith("local/"):
            candidates = [
                file_path,
                os.path.join(os.getcwd(), file_path),
                os.path.join(os.path.dirname(os.getcwd()), file_path),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", file_path),
            ]
            for cand in candidates:
                norm_cand = os.path.normpath(cand)
                if os.path.exists(norm_cand) and os.path.isfile(norm_cand):
                    try:
                        with open(norm_cand, "r", encoding="utf-8", errors="ignore") as f:
                            return f.read()
                    except Exception:
                        pass

        return None

    @classmethod
    def extract_line_range_snippets(
        cls,
        code_text: str,
        keyword: str,
        file_path: str,
        commit_sha: str,
        owner_repo: str,
        window: int = 5
    ) -> List[EvidenceSnippet]:
        """Locates keyword occurrences, calculates valid 1-indexed line ranges, and builds exact citation links."""
        lines = code_text.splitlines()
        snippets: List[EvidenceSnippet] = []
        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)

        visited_lines = set()
        for idx, line in enumerate(lines):
            if pattern.search(line) and idx not in visited_lines:
                start_idx = max(0, idx - window)
                end_idx = min(len(lines) - 1, idx + window)

                # Mark indices as covered to prevent duplicate overlapping snippets
                for i in range(start_idx, end_idx + 1):
                    visited_lines.add(i)

                start_line = start_idx + 1  # 1-indexed
                end_line = end_idx + 1      # 1-indexed

                excerpt = "\n".join(lines[start_idx:end_idx + 1])
                github_url = f"https://github.com/{owner_repo}/blob/{commit_sha}/{file_path}#L{start_line}-L{end_line}"

                snippets.append(
                    EvidenceSnippet(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        commit_sha=commit_sha,
                        snippet_text=excerpt,
                        github_url=github_url,
                        matched_keyword=keyword
                    )
                )

        return snippets
