"""MemoryDecay — time-based and relevance-based forgetting."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Callable, Optional

from .memory import CausalMemory, CausalEvent


class MemoryDecay:
    """Apply forgetting curves to prune or score events in a :class:`CausalMemory`."""

    def __init__(self, memory: CausalMemory) -> None:
        self.memory = memory

    # --- scoring -----------------------------------------------------------

    @staticmethod
    def time_score(
        event: CausalEvent,
        now: datetime,
        half_life: timedelta = timedelta(days=7),
    ) -> float:
        """Exponential decay score in [0, 1]. Score halves every *half_life*."""
        age = (now - event.timestamp).total_seconds()
        hl = half_life.total_seconds()
        if hl <= 0:
            return 0.0
        return 0.5 ** (age / hl)

    @staticmethod
    def relevance_score(event: CausalEvent, query_tags: list[str]) -> float:
        """Fraction of *query_tags* present in the event's tags."""
        if not query_tags:
            return 1.0
        if not event.tags:
            return 0.0
        hits = sum(1 for t in query_tags if t in event.tags)
        return hits / len(query_tags)

    def combined_score(
        self,
        event: CausalEvent,
        now: datetime,
        query_tags: Optional[list[str]] = None,
        half_life: timedelta = timedelta(days=7),
        time_weight: float = 0.6,
        relevance_weight: float = 0.4,
    ) -> float:
        """Weighted combination of time and relevance scores."""
        t = self.time_score(event, now, half_life)
        r = self.relevance_score(event, query_tags or [])
        return time_weight * t + relevance_weight * r

    # --- pruning -----------------------------------------------------------

    def prune_older_than(self, cutoff: datetime) -> int:
        """Remove all events older than *cutoff*. Returns count removed."""
        to_remove = [
            e.id for e in self.memory.all_events() if e.timestamp < cutoff
        ]
        for eid in to_remove:
            self.memory.remove(eid)
        return len(to_remove)

    def prune_below_score(
        self,
        now: datetime,
        threshold: float = 0.1,
        half_life: timedelta = timedelta(days=7),
    ) -> int:
        """Remove events whose time-decay score falls below *threshold*."""
        to_remove = [
            e.id
            for e in self.memory.all_events()
            if self.time_score(e, now, half_life) < threshold
        ]
        for eid in to_remove:
            self.memory.remove(eid)
        return len(to_remove)

    def prune_by_relevance(
        self,
        query_tags: list[str],
        threshold: float = 0.3,
    ) -> int:
        """Remove events whose tag relevance is below *threshold*."""
        to_remove = [
            e.id
            for e in self.memory.all_events()
            if self.relevance_score(e, query_tags) < threshold
        ]
        for eid in to_remove:
            self.memory.remove(eid)
        return len(to_remove)

    def prune_custom(
        self,
        predicate: Callable[[CausalEvent], bool],
    ) -> int:
        """Remove events for which *predicate* returns ``True``."""
        to_remove = [e.id for e in self.memory.all_events() if predicate(e)]
        for eid in to_remove:
            self.memory.remove(eid)
        return len(to_remove)

    # --- ranking -----------------------------------------------------------

    def rank_events(
        self,
        now: datetime,
        query_tags: Optional[list[str]] = None,
        half_life: timedelta = timedelta(days=7),
    ) -> list[tuple[CausalEvent, float]]:
        """Return all events sorted by combined score descending."""
        scored = [
            (e, self.combined_score(e, now, query_tags, half_life))
            for e in self.memory.all_events()
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored
