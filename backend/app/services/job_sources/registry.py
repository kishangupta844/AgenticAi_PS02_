import time
import logging
from typing import List, Optional, Tuple, Dict
from app.core.config import settings
from app.schemas.job import JobListing, NaukriSearchResponse
from app.services.job_sources.base import JobSourceProvider
from app.services.job_sources.naukri_provider import NaukriProvider
from app.services.job_sources.fallback_provider import FallbackJobProvider

logger = logging.getLogger(__name__)

class JobSourceRegistry:
    def __init__(self):
        self.naukri_provider = NaukriProvider()
        self.fallback_provider = FallbackJobProvider()
        # In-memory TTL cache: (query, location, experience, page) -> (timestamp, list[JobListing], provider)
        self._cache: Dict[Tuple[str, str, str, int], Tuple[float, List[JobListing], str]] = {}
        # Simple sliding window rate limiter: list of timestamps
        self._request_timestamps: List[float] = []
        self._max_req_per_minute = 30

    def _check_rate_limit(self) -> bool:
        now = time.time()
        # Keep timestamps from the last 60 seconds
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 60.0]
        if len(self._request_timestamps) >= self._max_req_per_minute:
            return False
        self._request_timestamps.append(now)
        return True

    async def search_jobs(
        self,
        query: str,
        location: Optional[str] = None,
        experience: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[JobListing], str, bool]:
        """
        Search jobs using configured provider with cache, rate-limiting, and automatic fallback.
        Returns: (results, provider_name, cached)
        """
        cache_key = (
            query.strip().lower(),
            (location or "").strip().lower(),
            (experience or "").strip().lower(),
            page
        )
        now = time.time()
        ttl = getattr(settings, "JOB_SEARCH_CACHE_TTL", 600)

        # Check Cache
        if cache_key in self._cache:
            ts, cached_results, provider = self._cache[cache_key]
            if now - ts < ttl:
                logger.info("Serving job search from cache for %s (%s)", query, provider)
                return cached_results, provider, True

        # Check Rate Limit
        if not self._check_rate_limit():
            logger.warning("Search rate limit exceeded (30 req/min). Using fallback/cached results.")
            if cache_key in self._cache:
                _, cached_results, provider = self._cache[cache_key]
                return cached_results, provider, True
            fallback_res = await self.fallback_provider.search(query, location, experience, page, page_size)
            return fallback_res, "fallback_rate_limited", False

        primary_choice = settings.JOB_SOURCE.lower()
        results: List[JobListing] = []
        active_provider = "naukri"

        if primary_choice == "naukri":
            try:
                results = await self.naukri_provider.search(query, location, experience, page, page_size)
                active_provider = "naukri"
                if not results:
                    logger.info("Naukri returned 0 results, attempting fallback provider.")
                    results = await self.fallback_provider.search(query, location, experience, page, page_size)
                    active_provider = "fallback"
            except PermissionError as pe:
                logger.warning("Naukri anti-bot triggered (%s). Falling back to fallback provider.", pe)
                results = await self.fallback_provider.search(query, location, experience, page, page_size)
                active_provider = "fallback_anti_bot"
            except Exception as e:
                logger.warning("Naukri search failed (%s). Falling back to fallback provider.", e)
                results = await self.fallback_provider.search(query, location, experience, page, page_size)
                active_provider = "fallback"
        else:
            results = await self.fallback_provider.search(query, location, experience, page, page_size)
            active_provider = "fallback"

        # Cache valid results
        if results:
            self._cache[cache_key] = (now, results, active_provider)

        return results, active_provider, False

    async def get_job_detail(self, external_id: str, apply_url: Optional[str] = None) -> Optional[str]:
        detail = await self.naukri_provider.get_detail(external_id, apply_url)
        if detail:
            return detail
        return await self.fallback_provider.get_detail(external_id, apply_url)

job_source_registry = JobSourceRegistry()
