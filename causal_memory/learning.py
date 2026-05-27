"""CausalLearning — extract patterns from past decisions."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from .memory import CausalMemory, CausalEvent
from .chain import CausalChain, ChainLink
from .query import ChainQuery


@dataclass
class Pattern:
    """A recurring cause-effect pattern."""

    cause_description: str
    effect_description: str
    frequency: int
    avg_confidence: float
    tags: list[str] = field(default_factory=list)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Pattern({self.cause_description!r} → {self.effect_description!r}, "
            f"freq={self.frequency}, conf={self.avg_confidence:.2f})"
        )


class CausalLearning:
    """Extract patterns and insights from a :class:`CausalMemory`."""

    def __init__(self, memory: CausalMemory) -> None:
        self.memory = memory
        self.query = ChainQuery(memory)

    def frequent_causes(self, min_frequency: int = 2) -> list[tuple[str, int]]:
        """Return cause descriptions that appear ≥ *min_frequency* times."""
        counter = Counter(e.description for e in self.memory.all_events() if not e.is_root)
        return [(desc, cnt) for desc, cnt in counter.most_common() if cnt >= min_frequency]

    def frequent_tags(self, min_frequency: int = 2) -> list[tuple[str, int]]:
        counter = Counter(t for e in self.memory.all_events() for t in e.tags)
        return [(tag, cnt) for tag, cnt in counter.most_common() if cnt >= min_frequency]

    def extract_patterns(self, min_confidence: float = 0.5) -> list[Pattern]:
        """Find recurring cause→effect pairs across all events."""
        pair_data: dict[tuple[str, str], list[float]] = {}
        pair_tags: dict[tuple[str, str], set[str]] = {}

        for ev in self.memory.all_events():
            if ev.cause_id is None:
                continue
            parent = self.memory.get(ev.cause_id)
            if parent is None:
                continue
            key = (parent.description, ev.description)
            pair_data.setdefault(key, []).append(ev.confidence)
            pair_tags.setdefault(key, set()).update(ev.tags)
            pair_tags[key].update(parent.tags)

        patterns: list[Pattern] = []
        for (cause_desc, effect_desc), confs in pair_data.items():
            avg = sum(confs) / len(confs)
            if avg >= min_confidence and len(confs) >= 1:
                patterns.append(
                    Pattern(
                        cause_description=cause_desc,
                        effect_description=effect_desc,
                        frequency=len(confs),
                        avg_confidence=avg,
                        tags=sorted(pair_tags.get((cause_desc, effect_desc), set())),
                    )
                )
        patterns.sort(key=lambda p: p.frequency, reverse=True)
        return patterns

    def confidence_drift(self) -> list[tuple[str, float]]:
        """Return events ordered by timestamp with their confidence, showing drift."""
        events = sorted(self.memory.all_events(), key=lambda e: e.timestamp)
        return [(e.id, e.confidence) for e in events]

    def tag_correlations(self) -> dict[str, dict[str, int]]:
        """For each tag, count how often other tags co-occur."""
        events = self.memory.all_events()
        corr: dict[str, Counter] = {}
        for ev in events:
            for t1 in ev.tags:
                for t2 in ev.tags:
                    if t1 != t2:
                        corr.setdefault(t1, Counter())[t2] += 1
        return {k: dict(v) for k, v in corr.items()}

    def chain_patterns(self, chains: list[CausalChain]) -> list[Pattern]:
        """Extract patterns across multiple chains (same decision text mapping to same outcome)."""
        pair_data: dict[tuple[str, Optional[str]], list[float]] = {}
        for chain in chains:
            for link in chain.links():
                key = (link.decision, link.outcome)
                pair_data.setdefault(key, []).append(link.confidence)

        patterns: list[Pattern] = []
        for (decision, outcome), confs in pair_data.items():
            if len(confs) >= 2 and outcome is not None:
                patterns.append(
                    Pattern(
                        cause_description=decision,
                        effect_description=outcome,
                        frequency=len(confs),
                        avg_confidence=sum(confs) / len(confs),
                    )
                )
        patterns.sort(key=lambda p: p.frequency, reverse=True)
        return patterns
