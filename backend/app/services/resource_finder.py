import os
import json
import re
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.models.entities import LearningResourceCache
from app.schemas.assessment import LearningResource

SEED_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources_seed.json")

class ResourceFinderService:
    """
    Finds real, verified learning resources without LLM url hallucinations:
    1. YouTube Data API v3 (if YOUTUBE_API_KEY configured).
    2. Fallback to curated official docs (resources_seed.json) and safe youtube search link.
    3. Live URL verification (oembed for youtube, HTTP GET/HEAD for web docs).
    4. Caches verified resources in DB for 7 days.
    """

    @classmethod
    def _normalize_skill(cls, skill: str) -> str:
        s = skill.lower().strip()
        s = re.sub(r'[^a-z0-9+/]+', '', s)
        return s

    @classmethod
    async def verify_url(cls, url: str) -> bool:
        """Verify URL returns 2xx. Drops broken links."""
        if not url or not url.startswith("http"):
            return False
        
        # YouTube verification via oembed
        if "youtube.com/watch" in url or "youtu.be/" in url:
            oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(url)}&format=json"
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(oembed_url)
                    return resp.status_code == 200
            except Exception:
                return False

        # Web links verification
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Career-Coach/1.0"}
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                resp = await client.head(url, headers=headers)
                if resp.status_code < 400:
                    return True
                resp = await client.get(url, headers=headers)
                return resp.status_code < 400
        except Exception:
            return False

    @classmethod
    def _load_seed_resources(cls) -> Dict[str, Any]:
        if os.path.exists(SEED_FILE_PATH):
            try:
                with open(SEED_FILE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    @classmethod
    async def search_youtube_api(cls, query: str, level: str) -> List[LearningResource]:
        """Query YouTube Data API v3 and fetch video metadata."""
        api_key = settings.YOUTUBE_API_KEY
        if not api_key:
            return []

        search_url = "https://www.googleapis.com/youtube/v3/search"
        search_params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 3,
            "key": api_key
        }

        try:
            async with httpx.AsyncClient(timeout=7.0) as client:
                res = await client.get(search_url, params=search_params)
                if res.status_code != 200:
                    return []
                items = res.json().get("items", [])
                video_ids = [it["id"]["videoId"] for it in items if "videoId" in it.get("id", {})]
                if not video_ids:
                    return []

                # Fetch video details for durations
                videos_url = "https://www.googleapis.com/youtube/v3/videos"
                v_params = {
                    "part": "contentDetails,snippet,statistics",
                    "id": ",".join(video_ids),
                    "key": api_key
                }
                v_res = await client.get(videos_url, params=v_params)
                if v_res.status_code != 200:
                    return []
                
                v_items = v_res.json().get("items", [])
                out = []
                for v in v_items:
                    snippet = v.get("snippet", {})
                    v_id = v.get("id")
                    title = snippet.get("title", "YouTube Tutorial")
                    channel = snippet.get("channelTitle", "YouTube")
                    iso_dur = v.get("contentDetails", {}).get("duration", "")
                    
                    # Approximate duration minutes from ISO 8601 duration
                    dur_min = 20
                    m = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_dur)
                    if m:
                        hours = int(m.group(1) or 0)
                        mins = int(m.group(2) or 0)
                        dur_min = hours * 60 + mins

                    url = f"https://www.youtube.com/watch?v={v_id}"
                    out.append(
                        LearningResource(
                            id=v_id,
                            skill=query,
                            title=title,
                            url=url,
                            type="youtube",
                            channel_or_site=channel,
                            duration_minutes=dur_min if dur_min > 0 else None,
                            why_relevant=f"Top-rated technical tutorial on {query}.",
                            level=level,
                            verified_at=datetime.now(timezone.utc)
                        )
                    )
                return out
        except Exception as e:
            print(f"YouTube API lookup error: {e}")
            return []

    @classmethod
    async def get_resources_for_skill(
        cls,
        skill: str,
        role_title: str = "Engineer",
        seniority: str = "mid",
        session: Optional[Session] = None
    ) -> List[LearningResource]:
        """
        Returns 1-3 verified learning resources (fundamentals -> build-along -> advanced)
        ordered as a learning path.
        """
        norm_skill = cls._normalize_skill(skill)
        cache_key = f"{norm_skill}:{seniority}"

        # 1. Check DB Cache
        if session:
            try:
                cached = session.exec(select(LearningResourceCache).where(LearningResourceCache.cache_key == cache_key)).first()
                if cached and cached.expires_at > datetime.now(timezone.utc):
                    data = json.loads(cached.resources_json)
                    return [LearningResource(**item) for item in data]
            except Exception as e:
                print(f"Cache check error: {e}")

        candidates: List[LearningResource] = []

        # 2. YouTube Data API search if key configured
        query = f"{skill} tutorial"
        if seniority in ("senior", "lead"):
            query = f"{skill} advanced tutorial architecture"
        yt_candidates = await cls.search_youtube_api(query, seniority)
        for ytc in yt_candidates:
            if await cls.verify_url(ytc.url):
                candidates.append(ytc)
                if len(candidates) >= 2:
                    break

        # 3. Seed Fallback Map for official docs
        seed_map = cls._load_seed_resources()
        matched_doc = None
        for key, info in seed_map.items():
            if key in norm_skill or norm_skill in key:
                matched_doc = info
                break

        if matched_doc:
            doc_url = matched_doc["url"]
            if await cls.verify_url(doc_url):
                candidates.append(
                    LearningResource(
                        id=f"doc-{norm_skill}",
                        skill=skill,
                        title=matched_doc["title"],
                        url=doc_url,
                        type="docs",
                        channel_or_site=matched_doc.get("channel_or_site", "Official Docs"),
                        duration_minutes=None,
                        why_relevant=matched_doc.get("why_relevant", f"Official documentation and guide for {skill}."),
                        level=seniority,
                        verified_at=datetime.now(timezone.utc)
                    )
                )

        # 4. Safe YouTube Search query fallback (guaranteed real url)
        search_query_encoded = urllib.parse.quote(f"{skill} {seniority} tutorial")
        safe_search_url = f"https://www.youtube.com/results?search_query={search_query_encoded}"
        candidates.append(
            LearningResource(
                id=f"yt-search-{norm_skill}",
                skill=skill,
                title=f"Curated YouTube Video Search: {skill}",
                url=safe_search_url,
                type="youtube",
                channel_or_site="YouTube Search",
                duration_minutes=None,
                why_relevant=f"Explore community tutorials and walk-throughs for {skill} ({seniority} level).",
                level=seniority,
                verified_at=datetime.now(timezone.utc)
            )
        )

        # Keep top 3 unique by url
        unique_resources: List[LearningResource] = []
        seen_urls = set()
        for r in candidates:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_resources.append(r)
            if len(unique_resources) >= 3:
                break

        # 5. Persist to cache (7 days TTL)
        if session and unique_resources:
            try:
                serialized = json.dumps([r.model_dump(mode="json") for r in unique_resources])
                expires = datetime.now(timezone.utc) + timedelta(days=7)
                cache_entry = session.exec(select(LearningResourceCache).where(LearningResourceCache.cache_key == cache_key)).first()
                if cache_entry:
                    cache_entry.resources_json = serialized
                    cache_entry.expires_at = expires
                    session.add(cache_entry)
                else:
                    cache_entry = LearningResourceCache(
                        cache_key=cache_key,
                        skill=skill,
                        level=seniority,
                        resources_json=serialized,
                        expires_at=expires
                    )
                    session.add(cache_entry)
                session.commit()
            except Exception as e:
                print(f"Failed to persist resource cache: {e}")

        return unique_resources
