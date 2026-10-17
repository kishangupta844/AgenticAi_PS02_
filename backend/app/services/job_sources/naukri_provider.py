import re
import html
import random
import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
import httpx

from app.core.config import settings
from app.schemas.job import JobListing
from app.services.job_sources.base import JobSourceProvider

logger = logging.getLogger(__name__)

# NOTE: Naukri has no public API. This provider communicates with the public web endpoint.
# If an official/partner API is obtained, swap this implementation.

def _clean_html(raw_html: Optional[str]) -> str:
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

def _normalize(raw: Dict[str, Any]) -> Optional[JobListing]:
    """
    Defensively normalizes a raw Naukri job item into a typed JobListing.
    Returns None if missing required identification/title.
    """
    if not isinstance(raw, dict):
        return None

    # external ID candidates: jobId, id, vacancyId
    ext_id = str(raw.get("jobId") or raw.get("id") or raw.get("vacancyId") or "").strip()
    title = str(raw.get("title") or raw.get("jobTitle") or "").strip()
    if not title:
        return None
    if not ext_id:
        ext_id = str(abs(hash(title + str(raw.get("companyName") or ""))))

    # Company name
    company = None
    if "companyName" in raw and raw["companyName"]:
        company = str(raw["companyName"]).strip()
    elif isinstance(raw.get("company"), dict):
        company = raw["company"].get("name")

    # Location
    location = None
    if isinstance(raw.get("placeholders"), list):
        for p in raw["placeholders"]:
            if isinstance(p, dict) and p.get("type") == "location":
                location = p.get("label")
                break
    if not location:
        if isinstance(raw.get("locations"), list):
            location_names = [l.get("label") for l in raw["locations"] if isinstance(l, dict) and l.get("label")]
            location = ", ".join(location_names) if location_names else None
        elif raw.get("location"):
            location = str(raw.get("location"))

    # Experience
    experience = None
    if isinstance(raw.get("placeholders"), list):
        for p in raw["placeholders"]:
            if isinstance(p, dict) and p.get("type") == "experience":
                experience = p.get("label")
                break
    if not experience and raw.get("experience"):
        experience = str(raw.get("experience"))

    # Salary
    salary = None
    if isinstance(raw.get("placeholders"), list):
        for p in raw["placeholders"]:
            if isinstance(p, dict) and p.get("type") == "salary":
                salary = p.get("label")
                break
    if not salary and raw.get("salary"):
        salary = str(raw.get("salary"))

    # Posted
    posted = None
    for k in ("footerPlaceholderLabel", "createdDate", "postedDate", "posted"):
        if raw.get(k):
            posted = str(raw.get(k)).strip()
            break

    # Skills / tags
    skills: List[str] = []
    if isinstance(raw.get("tagsAndSkills"), list):
        for s in raw["tagsAndSkills"]:
            if isinstance(s, dict) and s.get("label"):
                skills.append(str(s.get("label")).strip())
            elif isinstance(s, str) and s.strip():
                skills.append(s.strip())
    elif isinstance(raw.get("keySkills"), list):
        for s in raw["keySkills"]:
            if isinstance(s, str) and s.strip():
                skills.append(s.strip())
    elif isinstance(raw.get("tags"), list):
        for s in raw["tags"]:
            if isinstance(s, str) and s.strip():
                skills.append(s.strip())

    # Snippet / description
    snippet = _clean_html(raw.get("jobDescription") or raw.get("description") or raw.get("snippet"))

    # Apply URL
    apply_url = raw.get("jdURL") or raw.get("staticUrl") or raw.get("url") or raw.get("applyUrl") or ""
    if apply_url and not apply_url.startswith("http"):
        apply_url = f"https://www.naukri.com{apply_url if apply_url.startswith('/') else '/' + apply_url}"
    if not apply_url:
        clean_slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
        apply_url = f"https://www.naukri.com/job-listings-{clean_slug}-{ext_id}"

    # Logo URL
    logo_url = raw.get("logoPath") or raw.get("logoUrl") or None
    if logo_url and not logo_url.startswith("http"):
        logo_url = f"https://img.naukimg.com{logo_url if logo_url.startswith('/') else '/' + logo_url}"

    return JobListing(
        external_id=ext_id,
        source="naukri",
        title=title,
        company=company,
        location=location,
        experience=experience,
        salary=salary,
        posted=posted,
        skills=skills[:15],
        snippet=snippet[:400] if snippet else None,
        apply_url=apply_url,
        logo_url=logo_url
    )


class NaukriProvider(JobSourceProvider):
    provider_name: str = "naukri"

    def __init__(self):
        self.search_url = f"{settings.NAUKRI_BASE_URL.rstrip('/')}/jobapi/v3/search"
        self._headers = {
            "appid": settings.NAUKRI_APP_ID,
            "systemid": settings.NAUKRI_SYSTEM_ID,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.naukri.com/",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin"
        }

    async def search(
        self,
        query: str,
        location: Optional[str] = None,
        experience: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> List[JobListing]:
        params = {
            "noOfResults": min(max(page_size, 1), 50),
            "urlType": "search_by_keyword",
            "searchType": "adv",
            "keyword": query.strip(),
            "pageNo": max(page, 1),
            "k": query.strip(),
            "seoKey": f"{query.strip().lower().replace(' ', '-')}-jobs",
            "src": "jobsearchDesk"
        }
        if location and location.strip():
            params["location"] = location.strip()
            params["l"] = location.strip()
        if experience and experience.strip():
            params["experience"] = experience.strip()

        retries = 2
        last_exception = None

        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(self.search_url, params=params, headers=self._headers)
                    if resp.status_code in (403, 429):
                        logger.warning("Naukri returned HTTP %s on search attempt %d", resp.status_code, attempt + 1)
                        if attempt < retries:
                            await asyncio.sleep(0.5 + random.uniform(0.1, 0.4))
                            continue
                        raise PermissionError(f"SOURCE_BLOCKED: Naukri anti-bot triggered ({resp.status_code})")
                    
                    if resp.status_code != 200:
                        logger.warning("Naukri returned unexpected status code: %d", resp.status_code)
                        if attempt < retries:
                            await asyncio.sleep(0.4)
                            continue
                        return []

                    data = resp.json()
                    job_details = data.get("jobDetails", [])
                    if not job_details and "jobs" in data:
                        job_details = data.get("jobs", [])

                    results: List[JobListing] = []
                    for raw_job in job_details:
                        norm = _normalize(raw_job)
                        if norm:
                            results.append(norm)
                    return results

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exception = e
                logger.warning("Naukri request timeout/network error on attempt %d: %s", attempt + 1, e)
                if attempt < retries:
                    await asyncio.sleep(0.5 + random.uniform(0.1, 0.4))
                    continue
            except PermissionError:
                raise
            except Exception as e:
                logger.error("Unexpected error in NaukriProvider.search: %s", e)
                if attempt < retries:
                    await asyncio.sleep(0.3)
                    continue
                last_exception = e

        if last_exception:
            raise TimeoutError(f"SOURCE_TIMEOUT: Failed to query Naukri: {str(last_exception)}")
        return []

    async def get_detail(self, external_id: str, apply_url: Optional[str] = None) -> Optional[str]:
        """Attempt to fetch job details via Naukri's detail endpoint or via URL fetch."""
        if not external_id and not apply_url:
            return None

        # Try detail API endpoint if external_id is available
        if external_id:
            detail_url = f"{settings.NAUKRI_BASE_URL.rstrip('/')}/jobapi/v3/job/{external_id}"
            try:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    resp = await client.get(detail_url, headers=self._headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        desc = data.get("jobDetails", {}).get("description") or data.get("description")
                        if desc:
                            return _clean_html(desc)
            except Exception as e:
                logger.debug("Naukri detail API fetch failed for %s: %s", external_id, e)

        return None
