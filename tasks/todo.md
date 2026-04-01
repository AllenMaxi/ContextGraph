# ContextGraph Distribution & Feature Pass

## Goal
Ship 5 changes that maximize adoption: v2 MCP tools, Claude Code integration guide,
compression ratio metric, skeptical memory (confidence decay), and background
memory consolidation.

---

## Phase 1 — Distribution Pass (ship first)

### 1. Add v2 session MCP tools
- [ ] Add `contextgraph_session_start` tool definition + dispatch
- [ ] Add `contextgraph_session_event` tool definition + dispatch
- [ ] Add `contextgraph_checkpoint` tool definition + dispatch
- [ ] Add `contextgraph_resume` tool definition + dispatch
- [ ] Update MCP tool count in test_mcp_server.py
- [ ] Run all tests, verify 0 regressions

### 2. Write Claude Code integration guide
- [ ] Create `docs/claude-code-integration.md`
- [ ] Cover: install, configure hooks, PreCompact/PostCompact lifecycle
- [ ] Cover: env vars (CG_SERVER_URL, CG_AGENT_KEY, CG_AGENT_ID)
- [ ] Cover: session start → events → checkpoint → resume flow
- [ ] Cover: .contextgraph/ directory inspection
- [ ] Add link from README.md

### 3. Add compression ratio metric to ContextPack
- [ ] Add `source_tokens` field to ContextPack model
- [ ] Add `compression_ratio` computed property or field
- [ ] Compute source_tokens in compile_context from source memory content
- [ ] Add to ContextPackResponse schema
- [ ] Add to test_context_pack.py
- [ ] Update demo to print compression ratio

## Phase 2 — Skeptical Memory

### 4. Implement confidence decay / skeptical memory
- [ ] Add `CG_CLAIM_STALENESS_THRESHOLD_DAYS` setting (default: 14)
- [ ] Add `staleness_warning` field to ContextPackClaim
- [ ] In compile_context, flag claims older than threshold without recent attestation
- [ ] Add `stale_claim_count` to ContextPack
- [ ] Add staleness to explanation output
- [ ] Write tests for staleness detection
- [ ] Add `MEMORY_CONSOLIDATION` job type for future use

## Phase 3 — Background Consolidation

### 5. Implement background memory consolidation sweep
- [ ] Add `JobType.MEMORY_CONSOLIDATION` enum value
- [ ] Add `CG_ENABLE_MEMORY_CONSOLIDATION` setting (default: false)
- [ ] Add `CG_MEMORY_CONSOLIDATION_INTERVAL_HOURS` setting (default: 24)
- [ ] Implement `_run_memory_consolidation()` in service:
  - Merge near-duplicate claims across agents (Jaccard >= 0.88)
  - Archive challenged claims older than 30 days with no defense
  - Promote well-attested claims meeting trust threshold
  - Flag orphaned claims (memory deleted, claim still indexed)
- [ ] Schedule via background worker timer
- [ ] Write tests for each consolidation action
- [ ] Add consolidation stats to operator_snapshot

---

## Review
- [ ] Run full test suite
- [ ] Run ruff check + format
- [ ] Update README with new features
- [ ] Commit and push
