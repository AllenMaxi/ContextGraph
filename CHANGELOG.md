# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-03-14

### Added

- Memory-level access ownership with `visibility`, `access_list`, and `price` persisted on memories
- Canonical memory policy update endpoint at `PATCH /v1/memories/{memory_id}/access`
- Locked feed items for priced cross-org knowledge with `is_locked` and `requires_payment`
- Regression coverage for feed payment leaks, mixed-policy memories, and cross-org follow/access flows
- Public launch docs: roadmap, FAQ, use cases, and runnable examples

### Changed

- Claim policy updates now act as a compatibility shim that rewrites the parent memory policy
- Feed now acts as discovery for priced cross-org memories instead of exposing locked content
- Recall now enforces payment at the memory level and normalizes legacy sibling-claim policy drift on access
- FastAPI app lifecycle uses lifespan handlers instead of deprecated shutdown hooks

## [0.1.0] - 2026-03-09

### Added

- Core claim-native memory engine with entity extraction
- In-memory and Neo4j repository backends
- FastAPI HTTP API with agent authentication (`X-Agent-Key`)
- Admin key gating for agent registration (`CG_ADMIN_KEY`)
- Standing queries with pull and webhook delivery modes
- Background job processing with retry and dead-letter semantics
- Claim TTL with automatic expiry sweeps
- Review workflow (attest/challenge) with audit logging
- Operator console with cookie-based authentication
- Python SDK with local and HTTP transports
- Memory and subscription policy helpers
- Fixture-driven extractor evaluation framework
- CORS middleware (configurable via `CG_CORS_ORIGINS`)
- Rate limiting middleware (`CG_RATE_LIMIT_PER_MINUTE`)
- Docker and Docker Compose support
- GitHub Actions CI for Python 3.11–3.13
- Comprehensive test suite
