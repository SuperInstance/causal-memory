"""Comprehensive tests for causal_memory."""

from datetime import datetime, timezone, timedelta

from causal_memory import (
    CausalMemory,
    CausalEvent,
    CausalChain,
    ChainLink,
    ChainQuery,
    CausalLearning,
    Pattern,
    MemoryDecay,
)


# ---------------------------------------------------------------------------
# CausalMemory
# ---------------------------------------------------------------------------

class TestCausalMemory:
    def test_add_root_event(self):
        mem = CausalMemory()
        ev = mem.add("deployed v1", tags=["deploy"])
        assert ev.description == "deployed v1"
        assert ev.is_root
        assert ev.cause_id is None
        assert len(mem) == 1

    def test_add_child_event(self):
        mem = CausalMemory()
        root = mem.add("deployed v1")
        child = mem.add("latency spike", cause_id=root.id)
        assert child.cause_id == root.id
        assert not child.is_root
        assert root.id in mem._forward
        assert child.id in mem._forward[root.id]

    def test_get_effects(self):
        mem = CausalMemory()
        a = mem.add("A")
        b = mem.add("B", cause_id=a.id)
        c = mem.add("C", cause_id=b.id)
        effects = mem.get_effects(a.id, depth=2)
        ids = {e.id for e in effects}
        assert b.id in ids
        assert c.id in ids

    def test_get_effects_depth_1(self):
        mem = CausalMemory()
        a = mem.add("A")
        b = mem.add("B", cause_id=a.id)
        mem.add("C", cause_id=b.id)
        effects = mem.get_effects(a.id, depth=1)
        assert len(effects) == 1
        assert effects[0].id == b.id

    def test_get_causal_chain(self):
        mem = CausalMemory()
        a = mem.add("A")
        b = mem.add("B", cause_id=a.id)
        c = mem.add("C", cause_id=b.id)
        chain = mem.get_causal_chain(c.id)
        assert [e.id for e in chain] == [a.id, b.id, c.id]

    def test_get_causal_chain_root(self):
        mem = CausalMemory()
        a = mem.add("A")
        chain = mem.get_causal_chain(a.id)
        assert len(chain) == 1
        assert chain[0].id == a.id

    def test_get_temporal_events(self):
        mem = CausalMemory()
        t1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 2, tzinfo=timezone.utc)
        t3 = datetime(2025, 1, 3, tzinfo=timezone.utc)
        mem.add("early", timestamp=t1)
        mem.add("mid", timestamp=t2)
        mem.add("late", timestamp=t3)
        results = mem.get_temporal_events(t1, t2)
        assert len(results) == 2

    def test_roots(self):
        mem = CausalMemory()
        a = mem.add("A")
        mem.add("B", cause_id=a.id)
        c = mem.add("C")
        assert len(mem.roots()) == 2

    def test_remove_event(self):
        mem = CausalMemory()
        a = mem.add("A")
        b = mem.add("B", cause_id=a.id)
        mem.remove(b.id)
        assert mem.get(b.id) is None
        assert b.id not in mem._forward.get(a.id, set())

    def test_remove_nonexistent(self):
        mem = CausalMemory()
        try:
            mem.remove("nope")
            assert False, "Should have raised"
        except KeyError:
            pass

    def test_link_events(self):
        mem = CausalMemory()
        a = mem.add("A")
        b = mem.add("B")
        mem.link(a.id, b.id)
        assert b.cause_id == a.id
        assert b.id in a.effect_ids

    def test_link_nonexistent(self):
        mem = CausalMemory()
        try:
            mem.link("x", "y")
            assert False
        except KeyError:
            pass

    def test_contains(self):
        mem = CausalMemory()
        ev = mem.add("test")
        assert ev.id in mem
        assert "nope" not in mem

    def test_custom_event_id(self):
        mem = CausalMemory()
        ev = mem.add("test", event_id="my-id")
        assert ev.id == "my-id"
        assert mem.get("my-id") is ev

    def test_get_returns_none_for_missing(self):
        mem = CausalMemory()
        assert mem.get("missing") is None


# ---------------------------------------------------------------------------
# CausalChain
# ---------------------------------------------------------------------------

class TestCausalChain:
    def test_add_decisions(self):
        chain = CausalChain(name="test")
        chain.add_decision("decide A")
        chain.add_decision("decide B")
        assert len(chain) == 2

    def test_resolve_last(self):
        chain = CausalChain()
        chain.add_decision("pick route")
        link = chain.resolve_last("arrived safely")
        assert link.outcome == "arrived safely"
        assert link.resolved()

    def test_resolve_by_index(self):
        chain = CausalChain()
        chain.add_decision("step 1")
        chain.add_decision("step 2")
        link = chain.resolve(0, "done 1")
        assert link.outcome == "done 1"

    def test_unresolved_links(self):
        chain = CausalChain()
        chain.add_decision("A")
        chain.add_decision("B")
        assert len(chain.unresolved_links()) == 2
        chain.resolve_last("ok")
        assert len(chain.unresolved_links()) == 1

    def test_full_chain_returns_events(self):
        chain = CausalChain()
        chain.add_decision("A")
        chain.add_decision("B")
        events = chain.full_chain()
        assert len(events) == 2

    def test_decision_outcome_pairs(self):
        chain = CausalChain()
        chain.add_decision("A")
        chain.resolve_last("ok")
        chain.add_decision("B")
        pairs = chain.decision_outcome_pairs()
        assert pairs == [("A", "ok"), ("B", None)]

    def test_resolve_empty_raises(self):
        chain = CausalChain()
        try:
            chain.resolve_last("x")
            assert False
        except ValueError:
            pass

    def test_shared_memory(self):
        mem = CausalMemory()
        c1 = CausalChain(memory=mem, name="c1")
        c2 = CausalChain(memory=mem, name="c2")
        c1.add_decision("A")
        c2.add_decision("B")
        assert len(mem) == 2


# ---------------------------------------------------------------------------
# ChainQuery
# ---------------------------------------------------------------------------

class TestChainQuery:
    def _memory(self):
        mem = CausalMemory()
        a = mem.add("deploy service", tags=["deploy", "infra"], confidence=0.9)
        b = mem.add("latency spike", tags=["alert", "latency"], cause_id=a.id, confidence=0.7)
        c = mem.add("scale up", tags=["deploy", "scaling"], cause_id=b.id, confidence=0.85)
        return mem

    def test_by_tag(self):
        q = ChainQuery(self._memory())
        results = q.by_tag("deploy")
        assert len(results) == 2

    def test_by_tags_all(self):
        q = ChainQuery(self._memory())
        results = q.by_tags(["deploy", "infra"], match_all=True)
        assert len(results) == 1

    def test_by_tags_any(self):
        q = ChainQuery(self._memory())
        results = q.by_tags(["deploy", "alert"], match_all=False)
        assert len(results) == 3

    def test_by_confidence(self):
        q = ChainQuery(self._memory())
        results = q.by_confidence(0.8)
        assert len(results) == 2

    def test_by_timerange(self):
        mem = CausalMemory()
        t1 = datetime(2025, 6, 1, tzinfo=timezone.utc)
        t2 = datetime(2025, 6, 2, tzinfo=timezone.utc)
        t3 = datetime(2025, 6, 3, tzinfo=timezone.utc)
        mem.add("a", timestamp=t1)
        mem.add("b", timestamp=t2)
        mem.add("c", timestamp=t3)
        q = ChainQuery(mem)
        results = q.by_timerange(t1, t2)
        assert len(results) == 2

    def test_containing_text(self):
        q = ChainQuery(self._memory())
        results = q.containing_text("latency")
        assert len(results) == 1

    def test_leaves(self):
        q = ChainQuery(self._memory())
        leaves = q.leaves()
        assert len(leaves) == 1
        assert leaves[0].description == "scale up"

    def test_path_between(self):
        mem = self._memory()
        q = ChainQuery(mem)
        events = mem.all_events()
        a = next(e for e in events if e.description == "deploy service")
        c = next(e for e in events if e.description == "scale up")
        path = q.path_between(a.id, c.id)
        assert path is not None
        assert len(path) == 3

    def test_path_between_unreachable(self):
        mem = CausalMemory()
        a = mem.add("A")
        b = mem.add("B")  # disconnected
        q = ChainQuery(mem)
        assert q.path_between(a.id, b.id) is None

    def test_path_same_id(self):
        mem = CausalMemory()
        a = mem.add("A")
        q = ChainQuery(mem)
        path = q.path_between(a.id, a.id)
        assert path is not None
        assert len(path) == 1

    def test_counterfactual(self):
        mem = CausalMemory()
        mem.add("early", metadata={"region": "us-east"}, timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc))
        target = mem.add("late", metadata={"region": "us-west"}, timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc))
        q = ChainQuery(mem)
        results = q.counterfactual(target.id, {"region": "us-east"})
        assert len(results) == 1

    def test_statistics(self):
        q = ChainQuery(self._memory())
        stats = q.statistics()
        assert stats["total_events"] == 3
        assert stats["root_events"] == 1
        assert stats["leaf_events"] == 1


# ---------------------------------------------------------------------------
# CausalLearning
# ---------------------------------------------------------------------------

class TestCausalLearning:
    def _setup(self):
        mem = CausalMemory()
        for _ in range(3):
            a = mem.add("deploy", tags=["deploy", "infra"])
            mem.add("latency spike", cause_id=a.id, tags=["alert"])
        return mem

    def test_frequent_causes(self):
        learn = CausalLearning(self._setup())
        freq = learn.frequent_causes(min_frequency=2)
        assert len(freq) == 1
        assert freq[0][0] == "latency spike"

    def test_frequent_tags(self):
        learn = CausalLearning(self._setup())
        freq = learn.frequent_tags(min_frequency=2)
        tag_map = dict(freq)
        assert tag_map["deploy"] >= 3
        assert tag_map["alert"] >= 3

    def test_extract_patterns(self):
        learn = CausalLearning(self._setup())
        patterns = learn.extract_patterns()
        assert len(patterns) >= 1
        assert patterns[0].cause_description == "deploy"
        assert patterns[0].effect_description == "latency spike"
        assert patterns[0].frequency >= 3

    def test_confidence_drift(self):
        mem = CausalMemory()
        mem.add("a", confidence=0.9, timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc))
        mem.add("b", confidence=0.5, timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc))
        learn = CausalLearning(mem)
        drift = learn.confidence_drift()
        assert len(drift) == 2
        assert drift[0][1] == 0.9

    def test_tag_correlations(self):
        mem = CausalMemory()
        mem.add("e1", tags=["a", "b"])
        mem.add("e2", tags=["a", "c"])
        learn = CausalLearning(mem)
        corr = learn.tag_correlations()
        assert corr["a"]["b"] == 1
        assert corr["a"]["c"] == 1

    def test_chain_patterns(self):
        mem = CausalMemory()
        c1 = CausalChain(memory=mem, name="c1")
        c1.add_decision("deploy", confidence=0.9)
        c1.resolve_last("success")
        c2 = CausalChain(memory=mem, name="c2")
        c2.add_decision("deploy", confidence=0.8)
        c2.resolve_last("success")
        learn = CausalLearning(mem)
        patterns = learn.chain_patterns([c1, c2])
        assert len(patterns) == 1
        assert patterns[0].frequency == 2


# ---------------------------------------------------------------------------
# MemoryDecay
# ---------------------------------------------------------------------------

class TestMemoryDecay:
    def test_time_score_fresh(self):
        now = datetime.now(timezone.utc)
        ev = CausalEvent(description="fresh", timestamp=now)
        score = MemoryDecay.time_score(ev, now)
        assert score == 1.0

    def test_time_score_old(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=14)
        ev = CausalEvent(description="old", timestamp=old)
        score = MemoryDecay.time_score(ev, now, half_life=timedelta(days=7))
        assert 0.2 < score < 0.3  # two half-lives ≈ 0.25

    def test_relevance_score(self):
        ev = CausalEvent(description="x", tags=["a", "b", "c"])
        assert MemoryDecay.relevance_score(ev, ["a", "d"]) == 0.5
        assert MemoryDecay.relevance_score(ev, ["a", "b"]) == 1.0
        assert MemoryDecay.relevance_score(ev, []) == 1.0

    def test_prune_older_than(self):
        mem = CausalMemory()
        t_old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        t_new = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mem.add("old", timestamp=t_old)
        mem.add("new", timestamp=t_new)
        decay = MemoryDecay(mem)
        removed = decay.prune_older_than(datetime(2023, 1, 1, tzinfo=timezone.utc))
        assert removed == 1
        assert len(mem) == 1

    def test_prune_below_score(self):
        mem = CausalMemory()
        now = datetime.now(timezone.utc)
        mem.add("fresh", timestamp=now)
        mem.add("stale", timestamp=now - timedelta(days=30))
        decay = MemoryDecay(mem)
        removed = decay.prune_below_score(now, threshold=0.1, half_life=timedelta(days=7))
        assert removed == 1
        assert len(mem) == 1

    def test_prune_by_relevance(self):
        mem = CausalMemory()
        mem.add("relevant", tags=["keep", "me"])
        mem.add("irrelevant", tags=["other"])
        decay = MemoryDecay(mem)
        removed = decay.prune_by_relevance(["keep"], threshold=0.5)
        assert removed == 1
        assert len(mem) == 1

    def test_prune_custom(self):
        mem = CausalMemory()
        mem.add("low", confidence=0.1)
        mem.add("high", confidence=0.9)
        decay = MemoryDecay(mem)
        removed = decay.prune_custom(lambda e: e.confidence < 0.5)
        assert removed == 1
        assert len(mem) == 1

    def test_rank_events(self):
        mem = CausalMemory()
        now = datetime.now(timezone.utc)
        mem.add("fresh", tags=["a"], timestamp=now)
        mem.add("stale", tags=["b"], timestamp=now - timedelta(days=10))
        decay = MemoryDecay(mem)
        ranked = decay.rank_events(now, query_tags=["a"])
        assert ranked[0][0].description == "fresh"
        assert ranked[0][1] > ranked[1][1]

    def test_combined_score(self):
        now = datetime.now(timezone.utc)
        ev = CausalEvent(description="x", tags=["a"], timestamp=now)
        decay = MemoryDecay(CausalMemory())
        score = decay.combined_score(ev, now, query_tags=["a"])
        assert score == 1.0  # both components are 1.0
