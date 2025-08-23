from __future__ import annotations

from typing import Protocol, Any


class BaseAgent(Protocol):
    """Minimal interface for feature-specific agents."""

    def can_handle(self, command: str) -> bool:  # pragma: no cover - interface only
        ...

    async def handle(self, **kwargs: Any) -> Any:  # pragma: no cover - interface only
        ...


