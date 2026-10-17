import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx
from bs4 import BeautifulSoup
from app.models.entities import RequirementType
from app.schemas.job import ExtractedRequirement, JobExtractionResult
from app.services.gemini_service import sanitize
from app.services.llm_provider import get_provider

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class JobFetcherService:
    last_source: str = "heuristic"
    last_model: Optional[str] = None

    @staticmethod
    def normalize_url(url: str) -> str:
        """Ensure URL is well-formed with scheme."""
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        return url

    @classmethod
    async def fetch_url_content(cls, url: str) -> str:
        """
        Robust multi-strategy external URL reader.
        1. Specialized ATS APIs (Greenhouse, Lever, LinkedIn guest API)
        2. Direct HTTP fetch with modern Chrome browser headers
        3. Jina AI Reader fallback (handles client-side JS / SPAs)
        4. Cleans HTML, extracts meaningful text and bounds context size.
        """
        norm_url = cls.normalize_url(url)
        if not norm_url:
            raise ValueError("URL cannot be empty.")

        # --- Strategy 1: Greenhouse Board API ---
        gh_match = re.search(r'(?:boards|job-boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)', norm_url)
        if gh_match:
            board, job_id = gh_match.group(1), gh_match.group(2)
            api_url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
            try:
                async with httpx.AsyncClient(timeout=15.0, headers=BROWSER_HEADERS) as client:
                    resp = await client.get(api_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        content_html = data.get("content", "")
                        soup = BeautifulSoup(content_html, "html.parser")
                        text = soup.get_text("\n")
                        title = data.get("title", "")
                        comp = data.get("company_name", board.capitalize())
                        loc = data.get("location", {}).get("name", "")
                        return f"Job Title: {title}\nCompany: {comp}\nLocation: {loc}\n\nJob Description:\n{text}"
            except Exception as e:
                logger.debug("Greenhouse API lookup failed for %s: %s", norm_url, e)

        # --- Strategy 2: Lever Postings API ---
        lever_match = re.search(r'jobs\.lever\.co/([^/]+)/([a-f0-9\-]+)', norm_url)
        if lever_match:
            company, job_id = lever_match.group(1), lever_match.group(2)
            api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
            try:
                async with httpx.AsyncClient(timeout=15.0, headers=BROWSER_HEADERS) as client:
                    resp = await client.get(api_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        title = data.get("text", "")
                        desc_plain = data.get("descriptionPlain", "")
                        lists = []
                        for l in data.get("lists", []):
                            lists.append(f"{l.get('text', '')}:\n{l.get('content', '')}")
                        lists_str = "\n".join(lists)
                        return f"Job Title: {title}\nCompany: {company.capitalize()}\n\n{desc_plain}\n\n{lists_str}"
            except Exception as e:
                logger.debug("Lever API lookup failed: %s", e)

        # --- Strategy 3: LinkedIn Guest Job API ---
        li_match = re.search(r'linkedin\.com/jobs/view/.*?(\d{7,14})', norm_url)
        if li_match:
            li_job_id = li_match.group(1)
            li_api = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{li_job_id}"
            try:
                async with httpx.AsyncClient(timeout=15.0, headers=BROWSER_HEADERS, follow_redirects=True) as client:
                    resp = await client.get(li_api)
                    if resp.status_code == 200 and len(resp.text) > 300:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                            tag.decompose()
                        cleaned = cls._clean_soup_text(soup)
                        if len(cleaned) > 200:
                            return cleaned
            except Exception as e:
                logger.debug("LinkedIn guest endpoint failed: %s", e)

        # --- Strategy 4: Direct fetch with modern browser headers ---
        try:
            async with httpx.AsyncClient(timeout=18.0, headers=BROWSER_HEADERS, follow_redirects=True) as client:
                resp = await client.get(norm_url)
                if resp.status_code == 200 and len(resp.text.strip()) > 300:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # Remove unwanted web elements (preserve form/aside as jobs may be wrapped in them)
                    for tag in soup([
                        "script", "style", "nav", "footer", "header", "noscript", "svg", "iframe"
                    ]):
                        tag.decompose()
                    # Also remove common cookie banner / popup classes
                    for elem in soup.find_all(attrs={"class": re.compile(r"cookie|consent|banner|popup|modal", re.I)}):
                        elem.decompose()

                    cleaned = cls._clean_soup_text(soup)
                    if len(cleaned) > 250:
                        return cleaned[:18000]
        except Exception as e:
            logger.info("Direct fetch failed for %s (%s). Trying Jina Reader fallback...", norm_url, e)

        # --- Strategy 5: Jina AI Reader Fallback ---
        try:
            jina_url = f"https://r.jina.ai/{norm_url}"
            jina_headers = {
                "User-Agent": BROWSER_HEADERS["User-Agent"],
                "X-Return-Format": "markdown",
                "Accept": "text/plain, text/markdown, text/html",
            }
            async with httpx.AsyncClient(timeout=22.0, headers=jina_headers, follow_redirects=True) as client:
                resp = await client.get(jina_url)
                if resp.status_code == 200 and len(resp.text.strip()) > 100:
                    raw_jina = resp.text.strip()
                    # Extract markdown body after metadata header if present
                    if "Markdown Content:" in raw_jina:
                        candidate_body = raw_jina.split("Markdown Content:", 1)[1].strip()
                    else:
                        candidate_body = raw_jina
                    # Filter out obvious error responses in the candidate body
                    body_lower = candidate_body[:500].lower()
                    is_err = any(err in body_lower for err in [
                        "job not found", "page not found", "404 not found",
                        "position may have been removed", "access denied", "please sign in"
                    ])
                    if not is_err:
                        lines = [line.strip() for line in candidate_body.splitlines() if line.strip()]
                        cleaned_jina = "\n".join(lines)
                        if len(cleaned_jina) > 150:
                            return cleaned_jina[:18000]
        except Exception as e:
            logger.warning("Jina Reader fetch failed for %s: %s", norm_url, e)

        # --- Strategy 6: Fallback domain extraction if text cannot be reached ---
        domain = norm_url.split("//")[-1].split("/")[0]
        raise ValueError(
            f"Could not extract meaningful content from '{norm_url}'. "
            f"The site ({domain}) may require direct login or block automated access. "
            "Please paste the job text directly into the description box below."
        )

    @classmethod
    async def summarize_job_text(cls, text: str, source_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Use Groq AI LLM to summarize job description text into
        clean, short necessary job data, role profile, and technical requirements.
        """
        norm_url = cls.normalize_url(source_url) if source_url else ""
        content = (text or "").strip()
        if not content:
            raise ValueError("Job text cannot be empty.")

        # Call Groq AI LLM to extract structured data and clean concise summary
        prompt = f"""You are an expert technical recruiter and system architect.
Analyze the extracted job webpage data below and summarize it into clean, concise, necessary job information.

INVARIANTS:
1. "summary_text": A concise, highly readable, structured Job Description (around 150-250 words).
   Include:
   - Role Overview (1-2 sentences)
   - Key Responsibilities (3-5 concise bullet points)
   - Core Technical Requirements & Skills (Languages, Frameworks, Databases, Tools)
   - Qualifications & Seniority
   (Do NOT include cookie policies, navigation bars, website footers, legal disclaimers, or generic marketing.)
2. "title": Exact job title (e.g. "Senior Backend Engineer", "Staff Full-Stack AI Engineer").
3. "company": Company name (e.g. "Google", "GitLab", "Stripe").
4. "location": Location or "Remote".
5. "role_profile":
   - "seniority": one of "intern", "junior", "mid", "senior", "lead"
   - "domain": one of "backend", "full-stack", "frontend", "ai-ml", "devops", "data"
   - "expected_depth": description of depth needed (e.g. senior/lead requires production error handling, tests, architecture, performance, not just usage).
6. "requirements": List of technical requirements:
   [
     {{
       "title": str,
       "category": "Languages" | "Frameworks" | "Databases" | "Cloud & DevOps" | "System Design" | "Testing" | "Tools",
       "requirement_type": "required" | "preferred" | "bonus",
       "weight": float (0.5 to 2.0),
       "source_snippet": str (exact short excerpt from text)
     }}
   ]

Return strictly valid JSON only:
{{
  "title": "str",
  "company": "str",
  "location": "str",
  "summary_text": "str",
  "role_profile": {{
    "seniority": "junior|mid|senior|lead|intern",
    "domain": "backend|full-stack|frontend|ai-ml|devops|data",
    "expected_depth": "str"
  }},
  "requirements": [
    {{
      "title": "str",
      "category": "str",
      "requirement_type": "required|preferred|bonus",
      "weight": 1.2,
      "source_snippet": "str"
    }}
  ]
}}

<DATA>
{sanitize(content, 14000)}
</DATA>"""

        res = get_provider().generate_json(prompt)
        if res.data and isinstance(res.data, dict) and res.data.get("title"):
            try:
                data = res.data
                cls.last_source = "groq_llm"
                cls.last_model = res.model

                # Clean and ensure summary_text exists
                summary_text = data.get("summary_text", "").strip()
                if not summary_text or len(summary_text) < 50:
                    summary_text = cls._build_heuristic_summary(data.get("title"), data.get("company"), content)

                reqs = data.get("requirements", [])
                if not isinstance(reqs, list):
                    reqs = []

                # Format requirements cleanly
                formatted_reqs = []
                for r in reqs:
                    if isinstance(r, dict) and r.get("title"):
                        formatted_reqs.append({
                            "title": str(r.get("title")),
                            "category": str(r.get("category", "General")),
                            "requirement_type": str(r.get("requirement_type", "required")),
                            "weight": float(r.get("weight", 1.0)),
                            "source_snippet": str(r.get("source_snippet", ""))[:250],
                        })

                role_profile = data.get("role_profile")
                if not role_profile or not isinstance(role_profile, dict):
                    from app.services.job_extractor import JobExtractorService
                    role_profile = JobExtractorService._derive_role_profile(data.get("title", ""), content)

                return {
                    "title": data.get("title", "Software Engineer"),
                    "company": data.get("company") or "Direct Posting",
                    "location": data.get("location", "Remote"),
                    "source_url": norm_url,
                    "summary_text": summary_text,
                    "role_profile": role_profile,
                    "requirements": formatted_reqs,
                    "extraction_source": "groq_llm",
                    "llm_model": res.model,
                }
            except Exception as err:
                logger.warning("Error structuring Groq LLM result: %s", err)

        # Fallback heuristic summary
        logger.info("Falling back to heuristic summarizer for content")
        return cls._heuristic_summarize(norm_url or "Direct Posting", content)

    @classmethod
    async def summarize_job_url(cls, url: str) -> Dict[str, Any]:
        """
        Fetch any external job URL and use Groq AI LLM to summarize it into
        clean, short necessary job data, role profile, and technical requirements.
        """
        norm_url = cls.normalize_url(url)
        content = await cls.fetch_url_content(norm_url)
        return await cls.summarize_job_text(content, source_url=norm_url)

    @staticmethod
    def _clean_soup_text(soup: BeautifulSoup) -> str:
        """Extract clean text lines without empty noise."""
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    @classmethod
    def _build_heuristic_summary(cls, title: Optional[str], company: Optional[str], raw_text: str) -> str:
        """Construct a structured concise summary from raw text."""
        t = title or "Software Engineer"
        c = company or "Direct Company Posting"
        lines = [l.strip() for l in raw_text.splitlines() if len(l.strip()) > 20]
        responsibilities = lines[1:5] if len(lines) > 5 else lines[:3]
        resp_bullets = "\n".join([f"- {r}" for r in responsibilities])

        return (
            f"Job Title: {t}\n"
            f"Company: {c}\n\n"
            f"Role Overview:\n"
            f"Key technical position requiring solid software development, system design, and engineering practices.\n\n"
            f"Key Responsibilities:\n"
            f"{resp_bullets}\n\n"
            f"Core Requirements:\n"
            f"- Strong foundation in primary programming languages, modern frameworks, and API development.\n"
            f"- Experience with database design, containerization, and testing.\n"
            f"- Problem-solving, code quality, and production deployment skills."
        )

    @classmethod
    def _heuristic_summarize(cls, url: str, content: str) -> Dict[str, Any]:
        """Heuristic fallback extraction when LLM is unavailable."""
        from app.services.job_extractor import JobExtractorService

        lines = [l.strip() for l in content.splitlines() if l.strip()]
        title = "Software Engineer"
        for line in lines[:8]:
            if any(k in line.lower() for k in ["engineer", "developer", "architect", "lead", "specialist"]):
                title = line[:80]
                break

        # Guess company from URL
        domain = url.split("//")[-1].split("/")[0].replace("www.", "")
        company = domain.split(".")[0].capitalize()

        summary_text = cls._build_heuristic_summary(title, company, content)
        extracted = JobExtractorService._fallback_extract(content)

        req_dicts = [
            {
                "title": r.title,
                "category": r.category,
                "requirement_type": r.requirement_type.value if hasattr(r.requirement_type, "value") else str(r.requirement_type),
                "weight": r.weight,
                "source_snippet": r.source_snippet[:250],
            }
            for r in extracted.requirements
        ]

        return {
            "title": title,
            "company": company,
            "location": "Remote",
            "source_url": url,
            "summary_text": summary_text,
            "role_profile": extracted.role_profile or {
                "seniority": "mid",
                "domain": "backend",
                "expected_depth": "Mid-level depth: working implementation, clear modularity, and standard test coverage.",
            },
            "requirements": req_dicts,
            "extraction_source": "heuristic",
            "llm_model": None,
        }
