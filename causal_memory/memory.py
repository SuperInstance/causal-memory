"""CausalMemory — core store for cause-effect chains with timestamps."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class CausalEvent:
    """A single causal event linking a cause to an effect."""

    description: str
    cause_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    effect_ids: list[str] = field(default_factory=list)

    # --- derived helpers ---------------------------------------------------
    @property
    def is_root(self) -> bool:
        return self.cause_id is None

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"CausalEvent(id={self.id!r}, desc={self.description!r}, "
            f"cause={self.cause_id!r}, ts={self.timestamp.isoformat(timespec='seconds')})"
        )


class CausalMemory:
    """In-memory store of :class:`CausalEvent` objects with graph indexing."""

    def __init__(self) -> None:
        self._events: dict[str, CausalEvent] = {}
        # adjacency: cause-id → set of direct effect ids
        self._forward: dict[str, set[str]] = {}
        # adjacency: effect-id → cause-id
        self._backward: dict[str, str] = {}

    # --- mutators ----------------------------------------------------------

    def add(
        self,
        description: str,
        *,
        cause_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        confidence: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        event_id: Optional[str] = None,
    ) -> CausalEvent:
        """Create and store a new :class:`CausalEvent`.

        If *cause_id* refers to an existing event, the forward/backward
        indexes are updated automatically.
        """
        event = CausalEvent(
            description=description,
            cause_id=cause_id,
            tags=tags or [],
            confidence=confidence,
            metadata=metadata or {},
            timestamp=timestamp or datetime.now(timezone.utc),
            id=event_id or uuid.uuid4().hex[:12],
        )
        self._events[event.id] = event

        # update graph edges
        if event.cause_id is not None:
            self._forward.setdefault(event.cause_id, set()).add(event.id)
            self._backward[event.id] = event.cause_id

        return event

    def link(self, cause_id: str, effect_id: str) -> None:
        """Add a cause→effect link between two existing events."""
        if cause_id not in self._events or effect_id not in self._events:
            raise KeyError("Both cause_id and effect_id must reference existing events")
        self._forward.setdefault(cause_id, set()).add(effect_id)
        self._backward[effect_id] = cause_id
        cause_ev = self._events[cause_id]
        if effect_id not in cause_ev.effect_ids:
            cause_ev.effect_ids.append(effect_id)
        effect_ev = self._events[effect_id]
        if effect_ev.cause_id is None:
            effect_ev.cause_id = cause_id

    def remove(self, event_id: str) -> None:
        """Remove an event and clean up graph edges."""
        if event_id not in self._events:
            raise KeyError(f"No event with id {event_id!r}")
        # remove from forward edges
        if event_id in self._forward:
            for eid in list(self._forward[event_id]):
                ev = self._events.get(eid)
                if ev and ev.cause_id == event_id:
                    ev.cause_id = None
            del self._forward[event_id]
        # remove from backward edges
        if event_id in self._backward:
            parent_id = self._backward.pop(event_id)
            sib = self._forward.get(parent_id)
            if sib:
                sib.discard(event_id)
        # remove from parent's effect_ids
        ev = self._events[event_id]
        if ev.cause_id and ev.cause_id in self._events:
            parent = self._events[ev.cause_id]
            parent.effect_ids = [x for x in parent.effect_ids if x != event_id]
        del self._events[event_id]

    # --- queries -----------------------------------------------------------

    def get(self, event_id: str) -> Optional[CausalEvent]:
        return self._events.get(event_id)

    def get_effects(self, cause_id: str, depth: int = 1) -> list[CausalEvent]:
        """BFS traversal returning effects up to *depth* hops."""
        results: list[CausalEvent] = []
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(cause_id, 0)]
        while queue:
            cur_id, level = queue.pop(0)
            if cur_id in visited:
                continue
            visited.add(cur_id)
            if level > 0 and cur_id in self._events:
                results.append(self._events[cur_id])
            if level < depth:
                for child in self._forward.get(cur_id, set()):
                    queue.append((child, level + 1))
        return results

    def get_causal_chain(self, event_id: str, max_depth: int = 50) -> list[CausalEvent]:
        """Walk backwards from *event_id* to root, returning the chain root→event."""
        chain: list[CausalEvent] = []
        cur: Optional[str] = event_id
        depth = 0
        while cur is not None and depth < max_depth:
            ev = self._events.get(cur)
            if ev is None:
                break
            chain.append(ev)
            cur = ev.cause_id
            depth += 1
        chain.reverse()
        return chain

    def get_temporal_events(
        self,
        start: datetime,
        end: datetime,
    ) -> list[CausalEvent]:
        """Return events whose timestamps fall within [start, end], sorted."""
        return sorted(
            [e for e in self._events.values() if start <= e.timestamp <= end],
            key=lambda e: e.timestamp,
        )

    def roots(self) -> list[CausalEvent]:
        """Return all root events (no cause)."""
        return [e for e in self._events.values() if e.is_root]

    def all_events(self) -> list[CausalEvent]:
        return list(self._events.values())

    def __len__(self) -> int:
        return len(self._events)

    def __contains__(self, event_id: str) -> bool:
        return event_id in self._events

    def __repr__(self) -> str:  # pragma: no cover
        return f"CausalMemory(events={len(self)})"
