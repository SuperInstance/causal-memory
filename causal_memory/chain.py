"""CausalChain — link decisions to outcomes in a typed chain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .memory import CausalEvent, CausalMemory


@dataclass
class ChainLink:
    """A node in a :class:`CausalChain` pairing a decision with its outcome."""

    decision: str
    outcome: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolved(self) -> bool:
        return self.outcome is not None


class CausalChain:
    """An ordered sequence of :class:`ChainLink` objects backed by a :class:`CausalMemory`."""

    def __init__(self, memory: Optional[CausalMemory] = None, name: str = "default") -> None:
        self.memory = memory if memory is not None else CausalMemory()
        self.name = name
        self._links: list[ChainLink] = []
        self._event_ids: list[str] = []  # parallel to _links

    # --- building ----------------------------------------------------------

    def add_decision(
        self,
        decision: str,
        *,
        tags: Optional[list[str]] = None,
        confidence: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ChainLink:
        """Append a new decision to the chain."""
        link = ChainLink(
            decision=decision,
            tags=tags or [],
            confidence=confidence,
            metadata=metadata or {},
        )
        # Create a CausalEvent in the memory store
        parent_id = self._event_ids[-1] if self._event_ids else None
        ev = self.memory.add(
            decision,
            cause_id=parent_id,
            tags=tags or [],
            confidence=confidence,
            metadata=metadata or {},
        )
        self._links.append(link)
        self._event_ids.append(ev.id)
        return link

    def resolve_last(self, outcome: str) -> ChainLink:
        """Set the outcome on the most recent unresolved link."""
        for link in reversed(self._links):
            if not link.resolved():
                link.outcome = outcome
                return link
        raise ValueError("No unresolved link to resolve")

    def resolve(self, index: int, outcome: str) -> ChainLink:
        """Resolve the link at *index*."""
        link = self._links[index]
        link.outcome = outcome
        return link

    # --- queries -----------------------------------------------------------

    def links(self) -> list[ChainLink]:
        return list(self._links)

    def event_ids(self) -> list[str]:
        return list(self._event_ids)

    def resolved_links(self) -> list[ChainLink]:
        return [l for l in self._links if l.resolved()]

    def unresolved_links(self) -> list[ChainLink]:
        return [l for l in self._links if not l.resolved()]

    def full_chain(self) -> list[CausalEvent]:
        """Return the CausalEvents for all links."""
        return [self.memory.get(eid) for eid in self._event_ids if self.memory.get(eid) is not None]

    def decision_outcome_pairs(self) -> list[tuple[str, Optional[str]]]:
        return [(l.decision, l.outcome) for l in self._links]

    def __len__(self) -> int:
        return len(self._links)

    def __repr__(self) -> str:  # pragma: no cover
        return f"CausalChain(name={self.name!r}, links={len(self)})"
