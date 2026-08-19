from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import XPost


class ReadOnlyProvider(ABC):
    name: str

    @abstractmethod
    def search_public_posts(self, queries: list[str], limit: int) -> list[XPost]:
        """Return public X posts. Implementations must not interact with posts or users."""

