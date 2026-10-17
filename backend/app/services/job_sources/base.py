from abc import ABC, abstractmethod
from typing import List, Optional
from app.schemas.job import JobListing

class JobSourceProvider(ABC):
    """Abstract base class for all external job feed providers."""
    
    provider_name: str = "base"

    @abstractmethod
    async def search(
        self,
        query: str,
        location: Optional[str] = None,
        experience: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> List[JobListing]:
        """Search job listings based on query parameters."""
        pass

    @abstractmethod
    async def get_detail(self, external_id: str, apply_url: Optional[str] = None) -> Optional[str]:
        """Fetch the full description text for a specific job."""
        pass
