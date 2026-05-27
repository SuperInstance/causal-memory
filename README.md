# causal-memory

A Python library for tracking cause-effect chains in agent decision making — store causal events, build chains, query histories, extract patterns, and apply memory decay.

Part of the [Cocapn fleet](https://github.com/Lucineer/the-fleet).

## Installation

```bash
pip install causal-memory
```

## Quick Start

```python
from causal_memory import CausalMemory, ChainQuery, CausalLearning, MemoryDecay

# Create a memory store
mem = CausalMemory()

# Record causal events
deploy = mem.add("deployed v1.2", tags=["deploy", "backend"], confidence=0.95)
spike = mem.add("latency spike on /api", cause_id=deploy.id, tags=["alert", "latency"], confidence=0.8)
fix = mem.add("scaled replicas to 5", cause_id=spike.id, tags=["scaling"], confidence=0.9)

# Query effects downstream
effects = mem.get_effects(deploy.id, depth=3)
# → [CausalEvent("latency spike on /api"), CausalEvent("scaled replicas to 5")]

# Walk a causal chain root → event
chain = mem.get_causal_chain(fix.id)
# → [deploy, spike, fix]

# Search with ChainQuery
q = ChainQuery(mem)
alerts = q.by_tag("alert")          # events tagged "alert"
high = q.by_confidence(0.85)        # high-confidence events
path = q.path_between(deploy.id, fix.id)  # causal path

# Extract patterns with CausalLearning
learn = CausalLearning(mem)
patterns = learn.extract_patterns()  # recurring cause→effect pairs

# Apply forgetting with MemoryDecay
from datetime import datetime, timezone
decay = MemoryDecay(mem)
ranked = decay.rank_events(datetime.now(timezone.utc), query_tags=["deploy"])
```

## Module Overview

| Module | Class | Purpose |
|---|---|---|
| `memory.py` | `CausalMemory`, `CausalEvent` | Core event store with graph indexing |
| `chain.py` | `CausalChain`, `ChainLink` | Ordered decision→outcome sequences |
| `query.py` | `ChainQuery` | Search, filter, path-finding, counterfactuals |
| `learning.py` | `CausalLearning`, `Pattern` | Pattern extraction, tag correlations, confidence drift |
| `decay.py` | `MemoryDecay` | Time-based and relevance-based forgetting |

## Features

- **Zero external dependencies** — uses only stdlib dataclasses and collections
- **Full type hints** — clean IDE support
- **Graph-backed queries** — BFS for effects, path-finding, chain traversal
- **Counterfactual reasoning** — find alternative pasts given conditions
- **Memory decay** — exponential time-decay, tag-relevance scoring, custom pruning
- **Pattern mining** — extract recurring cause→effect patterns across histories

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -q
```

## License

MIT © SuperInstance
