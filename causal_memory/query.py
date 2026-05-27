"""ChainQuery — search and analyze causal histories."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from .memory import CausalEvent, CausalMemory
from .chain import CausalChain


class ChainQuery:
    """Fluent query builder over a :class:`CausalMemory`."""

    def __init__(self, memory: CausalMemory) -> None:
        self._memory = memory

    # --- filters -----------------------------------------------------------

    def by_tag(self, tag: str) -> list[CausalEvent]:
        return [e for e in self._memory.all_events() if tag in e.tags]

    def by_tags(self, tags: list[str], *, match_all: bool = True) -> list[CausalEvent]:
        events = self._memory.all_events()
        if match_all:
            return [e for e in events if all(t in e.tags for t in tags)]
        return [e for e in events if any(t in e.tags for t in tags)]

    def by_confidence(self, min_confidence: float) -> list[CausalEvent]:
        return [e for e in self._memory.all_events() if e.confidence >= min_confidence]

    def by_timerange(self, start: datetime, end: datetime) -> list[CausalEvent]:
        return self._memory.get_temporal_events(start, end)

    def containing_text(self, text: str) -> list[CausalEvent]:
        return [e for e in self._memory.all_events() if text.lower() in e.description.lower()]

    def roots(self) -> list[CausalEvent]:
        return self._memory.roots()

    def leaves(self) -> list[CausalEvent]:
        """Events that have no downstream effects in the graph."""
        return [
            e for e in self._memory.all_events()
            if not self._memory._forward.get(e.id)
        ]

    # --- analysis ----------------------------------------------------------

    def path_between(self, from_id: str, to_id: str) -> Optional[list[CausalEvent]]:
        """Find a causal path from *from_id* to *to_id* (BFS).  Returns ``None`` if none."""
        if from_id == to_id:
            ev = self._memory.get(from_id)
            return [ev] if ev else None

        visited: set[str] = {from_id}
        prev: dict[str, Optional[str]] = {from_id: None}
        queue: list[str] = [from_id]

        while queue:
            cur = queue.pop(0)
            ev = self._memory.get(cur)
            if ev is None:
                continue
            for child_id in self._memory._forward.get(cur, set()):
                if child_id in visited:
                    continue
                visited.add(child_id)
                prev[child_id] = cur
                if child_id == to_id:
                    # reconstruct
                    path: list[str] = []
                    node: Optional[str] = to_id
                    while node is not None:
                        path.append(node)
                        node = prev[node]
                    path.reverse()
                    return [self._memory.get(pid) for pid in path if self._memory.get(pid)]
                queue.append(child_id)
        return None

    def counterfactual(self, event_id: str, condition: dict[str, Any]) -> list[CausalEvent]:
        """Find events before *event_id* that match *condition* keys on metadata."""
        target = self._memory.get(event_id)
        if target is None:
            return []
        return [
            e
            for e in self._memory.all_events()
            if e.timestamp < target.timestamp
            and all(e.metadata.get(k) == v for k, v in condition.items())
        ]

    def statistics(self) -> dict[str, Any]:
        """Summary stats over the memory."""
        events = self._memory.all_events()
        confidences = [e.confidence for e in events]
        return {
            "total_events": len(events),
            "root_events": len(self._memory.roots()),
            "leaf_events": len(self.leaves()),
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
            "tags": sorted({t for e in events for t in e.tags}),
        }
