# ContextGraph Distribution & Feature Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 5 changes that maximize ContextGraph adoption: v2 MCP tools, Claude Code integration guide, compression ratio metric, skeptical memory, and background consolidation.

**Architecture:** Additive-only changes across MCP server, models, service, docs, and config. No breaking changes to existing APIs.

**Tech Stack:** Python 3.11+, existing ContextGraph service layer, MCP JSON-RPC, ruff for lint/format.

---

## Task 1: Add v2 Session MCP Tools

**Files:**
- Modify: `contextgraph/mcp_server.py`
- Modify: `tests/test_mcp_server.py`

These 4 new tools expose the session lifecycle via MCP so Claude Code and other MCP-aware agents can use reactive delta compaction.

- [ ] **Step 1: Add `contextgraph_session_start` tool definition**

Add to the `TOOLS` list in `contextgraph/mcp_server.py` after the `contextgraph_compile_context` entry:

```python
{
    "name": "contextgraph_session_start",
    "description": (
        "Start a new coding session in ContextGraph. "
        "Returns a session object with a session_id for recording events and checkpoints."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Human-readable title for the session.",
                "default": "",
            },
            "source": {
                "type": "string",
                "description": "Source tool identifier (e.g. 'claude-code', 'cursor').",
                "default": "mcp",
            },
            "metadata": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Arbitrary key/value metadata for the session.",
                "default": {},
            },
        },
        "required": [],
    },
},
```

- [ ] **Step 2: Add `contextgraph_session_event` tool definition**

```python
{
    "name": "contextgraph_session_event",
    "description": (
        "Record a structured event in a coding session. "
        "Event types include: decision, constraint, todo, failure, resolved_item, "
        "file_change, command, note, artifact, external_reference, context_pressure."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "The session to record the event in.",
            },
            "event_type": {
                "type": "string",
                "description": "Type of event (decision, constraint, todo, failure, etc.).",
            },
            "content": {
                "type": "string",
                "description": "Event content.",
                "default": "",
            },
            "auto_checkpoint": {
                "type": "boolean",
                "description": "Automatically checkpoint after this event.",
                "default": False,
            },
        },
        "required": ["session_id", "event_type"],
    },
},
```

- [ ] **Step 3: Add `contextgraph_checkpoint` tool definition**

```python
{
    "name": "contextgraph_checkpoint",
    "description": (
        "Checkpoint a coding session, compiling all events since the last checkpoint "
        "into a structured delta pack with decisions, tasks, failures, and restoration instructions."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "The session to checkpoint.",
            },
            "reason": {
                "type": "string",
                "description": "Reason for the checkpoint.",
                "default": "manual",
            },
            "token_budget": {
                "type": "integer",
                "description": "Token budget for the delta pack.",
                "default": 1600,
            },
        },
        "required": ["session_id"],
    },
},
```

- [ ] **Step 4: Add `contextgraph_resume` tool definition**

```python
{
    "name": "contextgraph_resume",
    "description": (
        "Resume a coding session by retrieving the latest checkpoint and delta pack. "
        "Returns the session state, restoration prompt, and structured context for continuing work."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "The session to resume.",
            },
        },
        "required": ["session_id"],
    },
},
```

- [ ] **Step 5: Add dispatch handlers for all 4 tools**

Add these handlers in `_dispatch_tool()` before the `raise ValueError` line:

```python
if tool_name == "contextgraph_session_start":
    session = service.create_session(
        agent_id=agent_id,
        title=arguments.get("title", ""),
        source=arguments.get("source", "mcp"),
        metadata=arguments.get("metadata"),
    )
    return _serialize(session)

if tool_name == "contextgraph_session_event":
    result = service.record_session_event(
        agent_id=agent_id,
        session_id=arguments["session_id"],
        event_type=arguments["event_type"],
        content=arguments.get("content", ""),
        auto_checkpoint=arguments.get("auto_checkpoint", False),
    )
    return _serialize(result)

if tool_name == "contextgraph_checkpoint":
    pack = service.checkpoint_session(
        agent_id=agent_id,
        session_id=arguments["session_id"],
        reason=arguments.get("reason", "manual"),
        token_budget=arguments.get("token_budget", 1600),
    )
    return _serialize(pack)

if tool_name == "contextgraph_resume":
    resume = service.resume_session(
        requester_agent_id=agent_id,
        session_id=arguments["session_id"],
    )
    return _serialize(resume)
```

- [ ] **Step 6: Update test_mcp_server.py tool count**

```python
# Change:
self.assertEqual(len(TOOLS), 7)
# To:
self.assertEqual(len(TOOLS), 11)
```

Add the 4 new tool names to the `expected_names` set:
```python
"contextgraph_session_start",
"contextgraph_session_event",
"contextgraph_checkpoint",
"contextgraph_resume",
```

- [ ] **Step 7: Run tests**

```bash
python3 -m pytest tests/test_mcp_server.py tests/test_reactive_delta_compaction.py -v
python3 -m pytest tests/ -q --tb=short
```

- [ ] **Step 8: Commit**

```bash
git add contextgraph/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add v2 session/checkpoint/resume MCP tools"
```

---

## Task 2: Write Claude Code Integration Guide

**Files:**
- Create: `docs/claude-code-integration.md`
- Modify: `README.md` (add link)

- [ ] **Step 1: Create the integration guide**

Create `docs/claude-code-integration.md` with these sections:

1. **Overview** — What ContextGraph adds to Claude Code (governed memory that persists across compaction boundaries)
2. **Prerequisites** — Install ContextGraph, start server, register an agent
3. **Configure Claude Code Hooks** — Show `settings.json` hook config pointing to `examples/hooks/claude_code_precompact.py` and `claude_code_postcompact.py`
4. **Environment Variables** — `CG_SERVER_URL`, `CG_AGENT_KEY`, `CG_AGENT_ID`, `CG_WORKSPACE`
5. **How It Works** — PreCompact hook emits `context_pressure` event with auto-checkpoint → PostCompact hook calls `resume_session` and syncs `.contextgraph/` directory
6. **MCP Integration** — Alternative: configure ContextGraph as an MCP server in Claude Code's MCP config, use `contextgraph_session_start`, `contextgraph_session_event`, `contextgraph_checkpoint`, `contextgraph_resume` tools
7. **Inspecting Session State** — Show `.contextgraph/` directory contents: `session.json`, `delta_pack.json`, `decisions.txt`, `restoration_prompt.txt`
8. **Branching Sessions** — Fork from a checkpoint when starting a new approach
9. **Memory Doctor** — Run `cg doctor-memory` to check session health

Use actual code from `examples/hooks/` — do not invent new code. Reference existing files.

- [ ] **Step 2: Add link from README.md**

In the "Start Here" section, add after the context compiler demo line:

```markdown
- Claude Code integration: [`docs/claude-code-integration.md`](docs/claude-code-integration.md)
```

Also add in the MCP section:

```markdown
Session lifecycle tools: `contextgraph_session_start`, `contextgraph_session_event`, `contextgraph_checkpoint`, `contextgraph_resume`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/claude-code-integration.md README.md
git commit -m "docs: add Claude Code integration guide"
```

---

## Task 3: Add Compression Ratio Metric to ContextPack

**Files:**
- Modify: `contextgraph/models.py`
- Modify: `contextgraph/service.py`
- Modify: `contextgraph/api/schemas.py`
- Modify: `tests/test_context_pack.py`
- Modify: `examples/context_pack_demo.py`

- [ ] **Step 1: Add fields to ContextPack model**

In `contextgraph/models.py`, add to `ContextPack` after `tokens_used`:

```python
source_tokens: int = 0  # total tokens in source memories before compilation
compression_ratio: float = 0.0  # source_tokens / tokens_used (0 if tokens_used == 0)
```

- [ ] **Step 2: Compute source_tokens in compile_context**

In `contextgraph/service.py` `compile_context()`, after the claims loop and before building the pack, compute:

```python
# Compute source tokens from all source memories
source_token_set: set[str] = set()
source_tokens_total = 0
for claim, score, memory in scored:
    if memory.memory_id not in source_token_set:
        source_token_set.add(memory.memory_id)
        source_tokens_total += self._estimate_tokens(memory.content)

compression_ratio = round(source_tokens_total / tokens_used, 1) if tokens_used > 0 else 0.0
```

Set `source_tokens=source_tokens_total` and `compression_ratio=compression_ratio` on the ContextPack constructor.

- [ ] **Step 3: Add to ContextPackResponse schema**

In `contextgraph/api/schemas.py` `ContextPackResponse`, add:

```python
source_tokens: int = 0
compression_ratio: float = 0.0
```

- [ ] **Step 4: Add test**

In `tests/test_context_pack.py`, add a test in `TestCompileContextBasic`:

```python
def test_compression_ratio_computed(self) -> None:
    self.service.store_memory(
        agent_id=self.agent.agent_id,
        content="The deployment pipeline uses Docker containers orchestrated by Kubernetes for all production services.",
        visibility="private",
    )
    pack = self.service.compile_context(
        agent_id=self.agent.agent_id,
        query="deployment Docker Kubernetes",
        token_budget=4000,
    )
    if pack.included_claims:
        self.assertGreater(pack.source_tokens, 0)
        self.assertGreater(pack.compression_ratio, 0.0)
```

- [ ] **Step 5: Update demo to print compression ratio**

In `examples/context_pack_demo.py`, add after the tokens line in the agent loop:

```python
if pack.get("source_tokens", 0) > 0:
    print(f"  Compression: {pack['source_tokens']} -> {pack['tokens_used']} tokens ({pack['compression_ratio']}x)")
```

- [ ] **Step 6: Run tests and commit**

```bash
python3 -m pytest tests/test_context_pack.py -v
python3 -m pytest tests/ -q --tb=short
git add contextgraph/models.py contextgraph/service.py contextgraph/api/schemas.py tests/test_context_pack.py examples/context_pack_demo.py
git commit -m "feat: add compression ratio metric to context packs"
```

---

## Task 4: Implement Skeptical Memory (Confidence Decay)

**Files:**
- Modify: `contextgraph/config.py`
- Modify: `contextgraph/models.py`
- Modify: `contextgraph/service.py`
- Modify: `contextgraph/api/schemas.py`
- Create: `tests/test_skeptical_memory.py`

- [ ] **Step 1: Add config setting**

In `contextgraph/config.py` `Settings`, add:

```python
claim_staleness_threshold_days: int = _read_int("CG_CLAIM_STALENESS_THRESHOLD_DAYS", 14)
```

- [ ] **Step 2: Add staleness_warning field to ContextPackClaim**

In `contextgraph/models.py` `ContextPackClaim`, add:

```python
staleness_warning: str = ""  # e.g. "claim is 21 days old with no recent attestation"
```

- [ ] **Step 3: Add stale_claim_count to ContextPack**

In `contextgraph/models.py` `ContextPack`, add after `compression_ratio`:

```python
stale_claim_count: int = 0
```

- [ ] **Step 4: Implement staleness detection in compile_context**

In `contextgraph/service.py` `compile_context()`, after building each `ContextPackClaim` via `_build_context_pack_claim`, check staleness:

```python
def _check_claim_staleness(self, claim: Claim) -> str:
    """Return a staleness warning if claim is old without recent attestation."""
    threshold_days = self.settings.claim_staleness_threshold_days
    if threshold_days <= 0:
        return ""
    age = (utcnow() - claim.created_at).days
    if age < threshold_days:
        return ""
    if claim.validation_status in (ValidationStatus.TRUSTED, ValidationStatus.ATTESTED):
        return ""
    return f"Claim is {age} days old with status '{claim.validation_status.value}' — verify before acting"
```

Call this in the compile loop and set `pack_claim.staleness_warning`. Count stale claims and set `stale_claim_count` on the pack.

- [ ] **Step 5: Add to schema**

In `contextgraph/api/schemas.py`:
- `ContextPackClaimResponse`: add `staleness_warning: str = ""`
- `ContextPackResponse`: add `stale_claim_count: int = 0`

- [ ] **Step 6: Write tests**

Create `tests/test_skeptical_memory.py`:

```python
"""Tests for skeptical memory — confidence decay and staleness detection."""

import unittest
from datetime import timedelta

from contextgraph.bootstrap import create_service
from contextgraph.config import Settings
from contextgraph.utils import utcnow


class TestStalenessDetection(unittest.TestCase):
    def setUp(self) -> None:
        self.service = create_service(Settings(
            repository_backend="memory",
            sentinel_enabled=False,
            claim_staleness_threshold_days=14,
        ))
        self.agent = self.service.register_agent(name="alice", org_id="acme")

    def test_fresh_claim_no_staleness_warning(self) -> None:
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The API uses rate limiting at 100 req/min.",
            visibility="private",
        )
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="API rate limiting",
            token_budget=4000,
        )
        for claim in pack.included_claims:
            self.assertEqual(claim.staleness_warning, "")
        self.assertEqual(pack.stale_claim_count, 0)

    def test_old_unreviewed_claim_gets_staleness_warning(self) -> None:
        result = self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The cache TTL is set to 300 seconds.",
            visibility="private",
        )
        # Age the claim artificially
        for claim in result.claims:
            claim.created_at = utcnow() - timedelta(days=30)
            self.service.repository.update_claim(claim)

        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="cache TTL",
            token_budget=4000,
        )
        stale = [c for c in pack.included_claims if c.staleness_warning]
        self.assertGreater(len(stale), 0)
        self.assertGreater(pack.stale_claim_count, 0)

    def test_attested_claim_not_stale(self) -> None:
        result = self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The database connection pool size is 20.",
            visibility="private",
        )
        for claim in result.claims:
            claim.created_at = utcnow() - timedelta(days=30)
            claim.validation_status = "attested"
            self.service.repository.update_claim(claim)

        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="database connection pool",
            token_budget=4000,
        )
        for claim in pack.included_claims:
            self.assertEqual(claim.staleness_warning, "")

    def test_staleness_disabled_when_threshold_zero(self) -> None:
        service = create_service(Settings(
            repository_backend="memory",
            sentinel_enabled=False,
            claim_staleness_threshold_days=0,
        ))
        agent = service.register_agent(name="bob", org_id="acme")
        result = service.store_memory(
            agent_id=agent.agent_id,
            content="Monitoring uses Prometheus.",
            visibility="private",
        )
        for claim in result.claims:
            claim.created_at = utcnow() - timedelta(days=60)
            service.repository.update_claim(claim)

        pack = service.compile_context(
            agent_id=agent.agent_id,
            query="monitoring Prometheus",
            token_budget=4000,
        )
        for claim in pack.included_claims:
            self.assertEqual(claim.staleness_warning, "")
```

- [ ] **Step 7: Run tests and commit**

```bash
python3 -m pytest tests/test_skeptical_memory.py -v
python3 -m pytest tests/ -q --tb=short
git add contextgraph/config.py contextgraph/models.py contextgraph/service.py contextgraph/api/schemas.py tests/test_skeptical_memory.py
git commit -m "feat: add skeptical memory with confidence decay and staleness warnings"
```

---

## Task 5: Implement Background Memory Consolidation

**Files:**
- Modify: `contextgraph/models.py` (JobType enum)
- Modify: `contextgraph/config.py` (settings)
- Modify: `contextgraph/service.py` (consolidation sweep)
- Create: `tests/test_memory_consolidation.py`

- [ ] **Step 1: Add JobType and config**

In `contextgraph/models.py` `JobType`, add:
```python
MEMORY_CONSOLIDATION = "memory_consolidation"
```

In `contextgraph/config.py` `Settings`, add:
```python
enable_memory_consolidation: bool = _read_bool("CG_ENABLE_MEMORY_CONSOLIDATION", False)
memory_consolidation_interval_hours: int = _read_int("CG_MEMORY_CONSOLIDATION_INTERVAL_HOURS", 24)
```

- [ ] **Step 2: Implement consolidation method**

In `contextgraph/service.py`, add:

```python
def run_memory_consolidation(self) -> dict[str, int]:
    """Run a background memory consolidation sweep.

    Actions:
    1. Archive challenged claims older than 30 days with no attestation
    2. Promote well-attested claims meeting trust promotion thresholds
    3. Flag orphaned claims whose parent memory was archived/hidden
    """
    now = utcnow()
    stats = {"archived_stale_challenged": 0, "promoted": 0, "flagged_orphaned": 0}

    for claim in self.repository.list_claims():
        # 1. Archive old challenged claims
        if (
            claim.validation_status == ValidationStatus.CHALLENGED
            and claim.attestation_count == 0
            and (now - claim.created_at).days > 30
        ):
            claim.validation_status = ValidationStatus.REJECTED
            claim.updated_at = now
            self.repository.update_claim(claim)
            stats["archived_stale_challenged"] += 1
            continue

        # 2. Check for orphaned claims
        memory = self.repository.get_memory(claim.memory_id)
        if memory is not None and memory.curation_status != MemoryCurationStatus.ACTIVE:
            if claim.validation_status not in (
                ValidationStatus.REJECTED,
                ValidationStatus.EXPIRED,
            ):
                claim.validation_status = ValidationStatus.EXPIRED
                claim.updated_at = now
                self.repository.update_claim(claim)
                stats["flagged_orphaned"] += 1

    # 3. Promote trusted claims (reuse existing method)
    stats["promoted"] = self.promote_trusted_claims()

    self._audit(
        "memory_consolidation",
        actor_agent_id="_system",
        details={k: str(v) for k, v in stats.items()},
    )
    return stats
```

- [ ] **Step 3: Schedule in background worker**

In `__init__`, after the claim expiry sweep scheduling, add:

```python
if self.settings.enable_memory_consolidation:
    self._schedule_memory_consolidation(
        self.settings.memory_consolidation_interval_hours * 3600
    )
```

Add the scheduling method:

```python
def _schedule_memory_consolidation(self, interval_seconds: float) -> None:
    if self._closing:
        return
    try:
        self.run_memory_consolidation()
    except Exception:
        logger.exception("Memory consolidation sweep failed")
    timer = Timer(interval_seconds, self._schedule_memory_consolidation, args=[interval_seconds])
    timer.daemon = True
    timer.start()
    self._timers.add(timer)
```

- [ ] **Step 4: Add to operator_snapshot**

In the `operator_snapshot` method, add consolidation stats if available.

- [ ] **Step 5: Write tests**

Create `tests/test_memory_consolidation.py`:

```python
"""Tests for background memory consolidation."""

import unittest
from datetime import timedelta

from contextgraph.bootstrap import create_service
from contextgraph.config import Settings
from contextgraph.models import ValidationStatus
from contextgraph.utils import utcnow


class TestMemoryConsolidation(unittest.TestCase):
    def setUp(self) -> None:
        self.service = create_service(Settings(
            repository_backend="memory",
            sentinel_enabled=False,
            trust_promotion_enabled=True,
            trust_promotion_min_age_days=7,
            trust_promotion_min_attestations=2,
        ))
        self.agent = self.service.register_agent(name="alice", org_id="acme")
        self.reviewer = self.service.register_agent(name="bob", org_id="acme")

    def test_archives_old_challenged_claims(self) -> None:
        result = self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="Disputed fact that nobody defended.",
            visibility="org",
        )
        claim = result.claims[0]
        # Challenge it
        self.service.review_claim(
            reviewer_agent_id=self.reviewer.agent_id,
            claim_id=claim.claim_id,
            decision="challenged",
            reason="incorrect",
        )
        # Age it past 30 days
        claim = self.service.repository.get_claim(claim.claim_id)
        claim.created_at = utcnow() - timedelta(days=35)
        self.service.repository.update_claim(claim)

        stats = self.service.run_memory_consolidation()
        self.assertGreater(stats["archived_stale_challenged"], 0)

        updated = self.service.repository.get_claim(claim.claim_id)
        self.assertEqual(updated.validation_status, ValidationStatus.REJECTED)

    def test_flags_orphaned_claims(self) -> None:
        result = self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="Fact in a hidden memory.",
            visibility="org",
        )
        # Archive the parent memory
        self.service.update_memory_curation(
            requester_agent_id=self.agent.agent_id,
            memory_id=result.memory.memory_id,
            curation_status="archived",
            reason="obsolete",
        )

        stats = self.service.run_memory_consolidation()
        self.assertGreater(stats["flagged_orphaned"], 0)

    def test_no_action_on_healthy_claims(self) -> None:
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="Fresh healthy fact.",
            visibility="org",
        )
        stats = self.service.run_memory_consolidation()
        self.assertEqual(stats["archived_stale_challenged"], 0)
        self.assertEqual(stats["flagged_orphaned"], 0)
```

- [ ] **Step 6: Run tests and commit**

```bash
python3 -m pytest tests/test_memory_consolidation.py -v
python3 -m pytest tests/ -q --tb=short
git add contextgraph/models.py contextgraph/config.py contextgraph/service.py tests/test_memory_consolidation.py
git commit -m "feat: add background memory consolidation sweep"
```

---

## Task 6: Final Review, Lint, and Push

**Files:**
- All modified files
- `README.md` (final updates)

- [ ] **Step 1: Run full test suite**

```bash
python3 -m pytest tests/ -v --tb=short
```

- [ ] **Step 2: Run ruff lint and format**

```bash
python3 -m ruff check contextgraph/ sdk/ tests/ examples/context_pack_demo.py
python3 -m ruff format contextgraph/ sdk/ tests/ examples/context_pack_demo.py
```

- [ ] **Step 3: Update README**

Add to "What Ships Today" list:
- `contextgraph_session_start`, `contextgraph_session_event`, `contextgraph_checkpoint`, `contextgraph_resume` MCP tools
- compression ratio metric on context packs
- skeptical memory with staleness warnings
- background memory consolidation

Update MCP section tool list from 7 to 11.

Update test count.

- [ ] **Step 4: Final commit and push**

```bash
git add -A
git commit -m "feat: distribution pass — MCP v2 tools, compression ratio, skeptical memory, consolidation"
git push origin main
```
