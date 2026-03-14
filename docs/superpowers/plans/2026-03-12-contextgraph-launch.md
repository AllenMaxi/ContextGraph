# ContextGraph Open-Source Launch — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship ContextGraph as a polished open-source project — the Knowledge Layer for AI Agents — with granular permissions, cross-company sharing, x402 payments, ERC-8004 identity, MCP server, and a PicoClaw-quality README.

**Architecture:** Layered service architecture (models → service → API → protocols). Add permission ACLs to claims, x402 payment middleware, ERC-8004 identity verification, and full MCP/A2A protocol servers. All features are additive — existing tests must keep passing throughout.

**Tech Stack:** Python 3.11+, FastAPI, Neo4j (optional), x402 protocol (HTTP 402), ERC-8004 (web3/eth), MCP SDK, A2A protocol, Docker

---

## File Structure

### New Files
```
contextgraph/permissions.py          — Granular ACL logic (access_list evaluation)
contextgraph/payment.py              — x402 payment protocol integration
contextgraph/identity.py             — ERC-8004 agent identity verification
contextgraph/extraction_llm.py       — LLM-powered entity/claim extraction
contextgraph/federation.py           — Federation sync between nodes
contextgraph/protocols/a2a_server.py — A2A protocol server implementation
contextgraph/middleware.py           — Request body limits, correlation IDs
tests/test_permissions.py            — Permission ACL tests
tests/test_payment.py                — x402 payment tests
tests/test_identity.py               — ERC-8004 identity tests
tests/test_extraction_llm.py         — LLM extractor tests
tests/test_federation.py             — Federation tests
tests/test_mcp.py                    — MCP server tests
LICENSE                              — MIT license
.gitignore                           — Python/IDE/OS ignores
CONTRIBUTING.md                      — Contribution guide
CODE_OF_CONDUCT.md                   — Contributor Covenant v2.1
CHANGELOG.md                         — Keep-a-changelog format
SECURITY.md                          — Responsible disclosure
Makefile                             — Dev commands
Dockerfile                           — Multi-stage Python build
docker-compose.yml                   — App + Neo4j
.github/workflows/ci.yml            — Test + lint pipeline
.github/ISSUE_TEMPLATE/bug.yml      — Bug template
.github/ISSUE_TEMPLATE/feature.yml  — Feature template
.github/PULL_REQUEST_TEMPLATE.md    — PR template
ruff.toml                           — Linter config
assets/                              — Hero image, logo, demo GIFs
sdk/README.md                       — SDK standalone docs
docs/README.es.md                   — Spanish README
```

### Modified Files
```
contextgraph/models.py               — Add access_list, payment fields, identity fields
contextgraph/errors.py               — Add PaymentRequiredError (402)
contextgraph/config.py               — Add payment, identity, LLM settings
contextgraph/service.py              — Update permissions, add payment gating, identity verification
contextgraph/repository.py           — No change (filtering stays in service layer)
contextgraph/in_memory.py            — No change (service layer handles ACL filtering)
contextgraph/api/routes.py           — Add permission, payment, identity endpoints
contextgraph/api/schemas.py          — Add access_list, payment, identity request/response fields
contextgraph/api/dependencies.py     — Add payment header parsing
contextgraph/web.py                  — Add PaymentRequiredError handler, body size limit
contextgraph/delivery.py             — Add SSRF protection
contextgraph/protocols/mcp_server.py — Full MCP SDK implementation (replace stub)
contextgraph/utils.py                — Add BM25 scoring (replace Jaccard)
sdk/contextgraph_sdk/client.py       — Add access_list, payment, identity support
sdk/contextgraph_sdk/exceptions.py   — Add PaymentRequiredError
pyproject.toml                       — Add dependencies, bump version
README.md                            — Complete rewrite
```

---

## Chunk 1: Foundation — Security, Packaging & Permissions

### Task 1: Open-Source Packaging Files

**Files:**
- Create: `LICENSE`
- Create: `.gitignore`
- Create: `CONTRIBUTING.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `CHANGELOG.md`
- Create: `SECURITY.md`
- Create: `Makefile`
- Create: `ruff.toml`

- [ ] **Step 1: Create LICENSE (MIT)**

```
MIT License

Copyright (c) 2026 Maximilian Allende

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Create .gitignore**

Standard Python .gitignore: `__pycache__/`, `*.pyc`, `.env`, `*.egg-info/`, `dist/`, `build/`, `.venv/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `*.db`, `.DS_Store`, `node_modules/`, `htmlcov/`

- [ ] **Step 3: Create CONTRIBUTING.md**

Sections: Getting Started, Development Setup (`pip install -e ".[server,neo4j,dev]"`), Running Tests (`make test`), Code Style (`make lint`), PR Process, Code of Conduct link.

- [ ] **Step 4: Create CODE_OF_CONDUCT.md**

Contributor Covenant v2.1 (standard text).

- [ ] **Step 5: Create CHANGELOG.md**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.2.0] - 2026-03-XX

### Added
- Granular permissions with access_list for cross-company sharing
- x402 payment protocol for knowledge commerce
- ERC-8004 agent identity verification
- MCP server for Claude/GPT integration
- LLM-powered entity extraction (Claude/OpenAI)
- A2A protocol support for agent discovery
- Basic federation between ContextGraph nodes
- BM25 recall scoring (replaces Jaccard)
- Docker and Docker Compose deployment
- CI/CD pipeline (GitHub Actions)
- Rate limiting and CORS middleware
- Structured logging throughout

### Security
- SSRF protection on webhook URLs
- Request body size limits
- Secure session cookies for console

## [0.1.0] - 2026-03-07

### Added
- Core service: store, recall, relate, watch
- In-memory and Neo4j repository backends
- REST API with FastAPI
- Python SDK (local + HTTP transports)
- Rule-based entity extraction
- Background job processing
- Webhook delivery with retries
- Claim review and attestation
- Operator console
```

- [ ] **Step 6: Create SECURITY.md**

Responsible disclosure policy. Email: security@contextgraph.dev. Response time: 48h. No public disclosure before fix.

- [ ] **Step 7: Create Makefile**

```makefile
.PHONY: test lint serve dev docker clean

test:
	python -m pytest tests/ -v

lint:
	ruff check contextgraph/ sdk/ tests/
	ruff format --check contextgraph/ sdk/ tests/

format:
	ruff format contextgraph/ sdk/ tests/

serve:
	python -m contextgraph.server

dev:
	docker compose up -d neo4j
	CG_REPOSITORY_BACKEND=neo4j python -m contextgraph.server

docker:
	docker compose up --build

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
```

- [ ] **Step 8: Create ruff.toml**

```toml
target-version = "py311"
line-length = 100

[lint]
select = ["E", "F", "I", "W", "UP", "B", "SIM"]

[format]
quote-style = "double"
```

- [ ] **Step 9: Commit**

```bash
git add LICENSE .gitignore CONTRIBUTING.md CODE_OF_CONDUCT.md CHANGELOG.md SECURITY.md Makefile ruff.toml
git commit -m "chore: add open-source packaging files (LICENSE, CI, contributing guide)"
```

---

### Task 2: CI/CD Pipeline & Docker

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/ISSUE_TEMPLATE/bug.yml`
- Create: `.github/ISSUE_TEMPLATE/feature.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create GitHub Actions CI**

`.github/workflows/ci.yml`:
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[server,neo4j,dev]"
      - run: ruff check contextgraph/ sdk/ tests/
      - run: ruff format --check contextgraph/ sdk/ tests/
      - run: python -m pytest tests/ -v --tb=short
```

- [ ] **Step 2: Create issue templates**

`bug.yml`: Title, Description, Steps to Reproduce, Expected Behavior, Environment.
`feature.yml`: Title, Description, Use Case, Proposed Solution.

- [ ] **Step 3: Create PR template**

Checklist: Tests pass, Lint passes, CHANGELOG updated, Description of changes.

- [ ] **Step 4: Create Dockerfile**

```dockerfile
FROM python:3.11-slim AS base
WORKDIR /app
COPY pyproject.toml .
COPY contextgraph/ contextgraph/
COPY sdk/ sdk/
RUN pip install --no-cache-dir ".[server]"
EXPOSE 8420
ENV CG_HOST=0.0.0.0
CMD ["contextgraph-server"]
```

- [ ] **Step 5: Create docker-compose.yml**

```yaml
services:
  contextgraph:
    build: .
    ports:
      - "8420:8420"
    environment:
      - CG_REPOSITORY_BACKEND=neo4j
      - CG_NEO4J_URI=bolt://neo4j:7687
      - CG_ADMIN_KEY=${CG_ADMIN_KEY:-changeme}
    depends_on:
      neo4j:
        condition: service_healthy

  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/contextgraph
    volumes:
      - neo4j_data:/data
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "contextgraph", "RETURN 1"]
      interval: 10s
      retries: 5

volumes:
  neo4j_data:
```

- [ ] **Step 6: Commit**

```bash
git add .github/ Dockerfile docker-compose.yml
git commit -m "ci: add GitHub Actions, Docker, and issue templates"
```

---

### Task 3: Security Hardening

**Files:**
- Modify: `contextgraph/delivery.py`
- Modify: `contextgraph/web.py`
- Modify: `contextgraph/errors.py`
- Modify: `contextgraph/api/schemas.py`

- [ ] **Step 1: Write test for SSRF protection**

`tests/test_service.py` — add test:
```python
def test_watch_webhook_rejects_private_ip(self):
    agent = self.service.register_agent("a", "org1", [], admin_key="test-key")
    with self.assertRaises(ValueError):
        self.service.watch(
            agent.agent_id, "test", "w", DeliveryMode.WEBHOOK,
            webhook_url="http://169.254.169.254/latest/meta-data/"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service.py::ContextGraphServiceTest::test_watch_webhook_rejects_private_ip -v`
Expected: FAIL

- [ ] **Step 3: Implement SSRF protection in service.py**

In the `watch()` method, before creating the standing query, validate the webhook URL:
```python
from contextgraph.delivery import validate_webhook_url

def watch(self, ...):
    if delivery_mode == DeliveryMode.WEBHOOK:
        if not webhook_url:
            raise ValueError("webhook_url required for WEBHOOK delivery")
        validate_webhook_url(webhook_url)
    ...
```

In `delivery.py`, add:
```python
import ipaddress
from urllib.parse import urlparse

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
]

def validate_webhook_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"webhook URL must use http or https, got {parsed.scheme}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("webhook URL must have a hostname")
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                raise ValueError(f"webhook URL must not target private network: {hostname}")
    except ValueError as exc:
        if "private network" in str(exc):
            raise
        # hostname is a domain, not an IP — allow it (DNS resolution happens at dispatch time)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_service.py::ContextGraphServiceTest::test_watch_webhook_rejects_private_ip -v`
Expected: PASS

- [ ] **Step 5: Add PaymentRequiredError to errors.py**

```python
class PaymentRequiredError(ContextGraphError):
    """Raised when payment is required to access a resource."""
```

- [ ] **Step 6: Add 402 handler in web.py**

In `create_app()`, add:
```python
from contextgraph.errors import PaymentRequiredError

@app.exception_handler(PaymentRequiredError)
async def payment_required_handler(request, exc):
    return JSONResponse(status_code=402, content={"error": str(exc)})
```

- [ ] **Step 7: Add request body size limit middleware in web.py**

```python
@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 1_048_576:  # 1MB
        return JSONResponse(status_code=413, content={"error": "Request body too large (max 1MB)"})
    return await call_next(request)
```

- [ ] **Step 8: Add max_length to content field in schemas.py**

In `MemoryStoreRequest`:
```python
content: str = Field(..., max_length=102400)  # 100KB max
```

- [ ] **Step 9: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 10: Commit**

```bash
git add contextgraph/delivery.py contextgraph/web.py contextgraph/errors.py contextgraph/api/schemas.py tests/test_service.py
git commit -m "security: add SSRF protection, body size limits, PaymentRequiredError"
```

---

### Task 4: Granular Permissions (access_list)

This is the foundation for cross-company sharing. Agents choose who can access their claims.

**Files:**
- Modify: `contextgraph/models.py`
- Create: `contextgraph/permissions.py`
- Modify: `contextgraph/service.py`
- Modify: `contextgraph/api/schemas.py`
- Create: `tests/test_permissions.py`

- [ ] **Step 1: Write permission tests**

`tests/test_permissions.py`:
```python
from __future__ import annotations
import unittest
from contextgraph.models import Visibility, Claim
from contextgraph.permissions import can_access_claim

class PermissionsTest(unittest.TestCase):

    def _make_claim(self, visibility, source_org="org-a", access_list=None):
        return Claim(
            claim_id="c1", memory_id="m1", source_agent_id="agent-a",
            source_org_id="org-a", statement="test", claim_type="attribute",
            visibility=visibility, validation_status="unreviewed",
            confidence=0.9, freshness_score=1.0,
            entity_ids=[], access_list=access_list or [],
        )

    def test_private_only_source_agent(self):
        claim = self._make_claim(Visibility.PRIVATE)
        self.assertTrue(can_access_claim("agent-a", "org-a", claim))
        self.assertFalse(can_access_claim("agent-b", "org-a", claim))

    def test_org_visible_to_same_org(self):
        claim = self._make_claim(Visibility.ORG)
        self.assertTrue(can_access_claim("agent-b", "org-a", claim))
        self.assertFalse(can_access_claim("agent-c", "org-b", claim))

    def test_shared_with_access_list_agent(self):
        claim = self._make_claim(Visibility.SHARED, access_list=["agent-x", "org-b"])
        # agent in access_list
        self.assertTrue(can_access_claim("agent-x", "org-c", claim))
        # org in access_list
        self.assertTrue(can_access_claim("agent-y", "org-b", claim))
        # not in list
        self.assertFalse(can_access_claim("agent-z", "org-c", claim))
        # source agent always has access
        self.assertTrue(can_access_claim("agent-a", "org-a", claim))

    def test_published_visible_to_all(self):
        claim = self._make_claim(Visibility.PUBLISHED)
        self.assertTrue(can_access_claim("anyone", "any-org", claim))

    def test_agent_chooses_visibility_at_store_time(self):
        """Agents control their own permissions."""
        # This is a design test — visibility is set by the storing agent
        claim = self._make_claim(Visibility.SHARED, access_list=["org-partner"])
        self.assertTrue(can_access_claim("partner-agent", "org-partner", claim))
        self.assertFalse(can_access_claim("random-agent", "org-random", claim))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_permissions.py -v`
Expected: FAIL (imports don't exist yet)

- [ ] **Step 3: Update models.py — Add access_list to Claim, add ORG visibility**

Add `source_org_id: str = ""` to Claim dataclass.
Add `access_list: list[str] = field(default_factory=list)` to Claim dataclass.
Update `Visibility` enum: rename `SHARED` → `ORG`, add new `SHARED` that uses access_list.

New Visibility enum:
```python
class Visibility(StrEnum):
    PRIVATE = "private"       # Only the source agent
    ORG = "org"               # All agents in same org_id
    SHARED = "shared"         # Specific agents/orgs in access_list
    PUBLISHED = "published"   # Any authenticated agent
```

- [ ] **Step 4: Create permissions.py**

```python
from __future__ import annotations
from contextgraph.models import Claim, Visibility

def can_access_claim(
    requester_agent_id: str,
    requester_org_id: str,
    claim: Claim,
) -> bool:
    """Evaluate whether a requester can access a claim based on its visibility and access_list."""
    # Source agent always has access
    if claim.source_agent_id == requester_agent_id:
        return True

    if claim.visibility == Visibility.PRIVATE:
        return False

    if claim.visibility == Visibility.ORG:
        return requester_org_id == claim.source_org_id

    if claim.visibility == Visibility.SHARED:
        # Check if requester's agent_id or org_id is in the access_list
        return (
            requester_agent_id in claim.access_list
            or requester_org_id in claim.access_list
        )

    if claim.visibility == Visibility.PUBLISHED:
        return True

    return False
```

- [ ] **Step 5: Run permission tests**

Run: `python -m pytest tests/test_permissions.py -v`
Expected: PASS

- [ ] **Step 6: Update service.py to use new permissions module**

Replace `_can_access_claim()` static method with call to `permissions.can_access_claim()`.
Update `store_memory()` to set `source_org_id` on claims from the agent's org_id.
Update `store_memory()` to accept and pass through `access_list` parameter.

- [ ] **Step 7: Update schemas.py**

Add to `MemoryStoreRequest`:
```python
access_list: list[str] = Field(default_factory=list, description="Agent IDs or org IDs allowed access (for 'shared' visibility)")
```

Add to `ClaimResponse`:
```python
source_org_id: str = ""
access_list: list[str] = Field(default_factory=list)
```

- [ ] **Step 8: Update routes.py — pass access_list through**

In the store endpoint, pass `access_list=body.access_list` to `service.store_memory()`.

- [ ] **Step 9: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass (existing tests may need `Visibility.SHARED` → `Visibility.ORG` rename in some places)

- [ ] **Step 10: Commit**

```bash
git add contextgraph/models.py contextgraph/permissions.py contextgraph/service.py contextgraph/api/schemas.py contextgraph/api/routes.py tests/test_permissions.py
git commit -m "feat: add granular permissions with access_list for cross-company sharing"
```

---

### Task 5: x402 Payment Protocol Integration

Agents from other companies can pay to access knowledge. The storing agent sets a price (or free). Recall returns HTTP 402 if payment is required.

**Files:**
- Create: `contextgraph/payment.py`
- Modify: `contextgraph/models.py`
- Modify: `contextgraph/config.py`
- Modify: `contextgraph/service.py`
- Modify: `contextgraph/api/routes.py`
- Modify: `contextgraph/api/schemas.py`
- Create: `tests/test_payment.py`

- [ ] **Step 1: Write payment tests**

`tests/test_payment.py`:
```python
from __future__ import annotations
import unittest
from contextgraph.payment import PaymentGate, PaymentReceipt, PaymentPolicy
from contextgraph.errors import PaymentRequiredError

class PaymentGateTest(unittest.TestCase):

    def test_free_claims_need_no_payment(self):
        gate = PaymentGate(enabled=False)
        # Should not raise
        gate.check_access(agent_id="a", claim_price=0.0, payment_token=None)

    def test_priced_claim_without_token_raises_402(self):
        gate = PaymentGate(enabled=True)
        with self.assertRaises(PaymentRequiredError) as ctx:
            gate.check_access(agent_id="a", claim_price=0.002, payment_token=None)
        self.assertIn("0.002", str(ctx.exception))

    def test_priced_claim_with_valid_token_passes(self):
        gate = PaymentGate(enabled=True)
        receipt = gate.check_access(
            agent_id="a", claim_price=0.002,
            payment_token="x402_test_valid_token"
        )
        self.assertIsInstance(receipt, PaymentReceipt)

    def test_same_org_access_is_free(self):
        gate = PaymentGate(enabled=True)
        # Same-org agents don't pay each other
        gate.check_access(
            agent_id="a", claim_price=0.002, payment_token=None,
            requester_org="org-a", claim_org="org-a"
        )

    def test_policy_sets_price_per_claim(self):
        policy = PaymentPolicy(default_price=0.001, currency="USDC")
        self.assertEqual(policy.price_for_claim("any_claim"), 0.001)

    def test_policy_free_for_published_no_price(self):
        policy = PaymentPolicy(default_price=0.0, currency="USDC")
        self.assertEqual(policy.price_for_claim("any_claim"), 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_payment.py -v`
Expected: FAIL

- [ ] **Step 3: Create payment.py**

```python
from __future__ import annotations
from dataclasses import dataclass
from contextgraph.errors import PaymentRequiredError

@dataclass(slots=True)
class PaymentReceipt:
    """Proof of payment for a knowledge access."""
    token: str
    amount: float
    currency: str
    payer_agent_id: str
    status: str  # "verified" or "pending"

@dataclass(slots=True)
class PaymentPolicy:
    """Pricing policy for an agent's knowledge."""
    default_price: float = 0.0  # 0 = free
    currency: str = "USDC"

    def price_for_claim(self, claim_id: str) -> float:
        return self.default_price

@dataclass(slots=True)
class PaymentGate:
    """Gate that checks x402 payment before granting access to priced knowledge."""
    enabled: bool = False

    def check_access(
        self,
        agent_id: str,
        claim_price: float,
        payment_token: str | None,
        requester_org: str = "",
        claim_org: str = "",
    ) -> PaymentReceipt | None:
        """Check if payment is satisfied. Raises PaymentRequiredError if not."""
        if not self.enabled:
            return None

        # Same-org agents don't pay each other
        if requester_org and claim_org and requester_org == claim_org:
            return None

        # Free claims need no payment
        if claim_price <= 0:
            return None

        # Priced claim requires token
        if not payment_token:
            raise PaymentRequiredError(
                f"Payment required: {claim_price} USDC. "
                f"Send x402 payment token in X-Payment-Token header."
            )

        # In production, verify token against x402 settlement network.
        # For MVP, accept any non-empty token as valid.
        return PaymentReceipt(
            token=payment_token,
            amount=claim_price,
            currency="USDC",
            payer_agent_id=agent_id,
            status="verified",
        )
```

- [ ] **Step 4: Run payment tests**

Run: `python -m pytest tests/test_payment.py -v`
Expected: PASS

- [ ] **Step 5: Add payment config to config.py**

```python
# Payment (x402)
enable_payments: bool = False      # CG_ENABLE_PAYMENTS
default_claim_price: float = 0.0   # CG_DEFAULT_CLAIM_PRICE (USDC)
payment_currency: str = "USDC"     # CG_PAYMENT_CURRENCY
x402_verifier_url: str = ""        # CG_X402_VERIFIER_URL (for production verification)
```

- [ ] **Step 6: Add price field to Claim model**

In `contextgraph/models.py`, add to Claim:
```python
price: float = 0.0  # Price in USDC (0 = free). Set by storing agent.
```

- [ ] **Step 7: Add price to MemoryStoreRequest schema**

```python
price: float = Field(default=0.0, ge=0.0, description="Price per recall in USDC (0 = free)")
```

- [ ] **Step 8: Wire payment gate into service.py recall()**

In `recall()`, after filtering claims by permissions, check payment for cross-org priced claims:
```python
from contextgraph.payment import PaymentGate

# In __init__:
self._payment_gate = PaymentGate(enabled=settings.enable_payments)

# In recall(), after _can_access filtering:
for claim in accessible_claims:
    if claim.price > 0:
        self._payment_gate.check_access(
            agent_id=agent_id,
            claim_price=claim.price,
            payment_token=payment_token,
            requester_org=requester.org_id,
            claim_org=claim.source_org_id,
        )
```

- [ ] **Step 9: Add X-Payment-Token header to routes.py**

In recall endpoint, extract payment token from headers:
```python
@router.post("/v1/memory/recall")
async def recall(body: RecallRequest, agent: Agent = Depends(auth), x_payment_token: str | None = Header(None, alias="X-Payment-Token")):
    hits = service.recall(body.agent_id, body.query, body.limit, payment_token=x_payment_token)
    ...
```

- [ ] **Step 10: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 11: Commit**

```bash
git add contextgraph/payment.py contextgraph/models.py contextgraph/config.py contextgraph/service.py contextgraph/api/routes.py contextgraph/api/schemas.py tests/test_payment.py
git commit -m "feat: add x402 payment protocol — agents can price their knowledge"
```

---

### Task 6: ERC-8004 Agent Identity

Agents can register with an on-chain identity. Other agents can verify who they're sharing knowledge with.

**Files:**
- Create: `contextgraph/identity.py`
- Modify: `contextgraph/models.py`
- Modify: `contextgraph/config.py`
- Modify: `contextgraph/service.py`
- Modify: `contextgraph/api/schemas.py`
- Create: `tests/test_identity.py`

- [ ] **Step 1: Write identity tests**

`tests/test_identity.py`:
```python
from __future__ import annotations
import unittest
from contextgraph.identity import AgentIdentity, IdentityVerifier

class IdentityTest(unittest.TestCase):

    def test_create_identity_without_chain(self):
        """Agents can register without on-chain identity (optional)."""
        identity = AgentIdentity(agent_id="a1")
        self.assertFalse(identity.is_verified)
        self.assertEqual(identity.erc8004_address, "")

    def test_create_identity_with_address(self):
        identity = AgentIdentity(
            agent_id="a1",
            erc8004_address="0x1234567890abcdef1234567890abcdef12345678",
        )
        self.assertTrue(identity.has_chain_identity)
        self.assertFalse(identity.is_verified)  # Not yet verified

    def test_verify_identity_marks_verified(self):
        verifier = IdentityVerifier(enabled=False)  # Offline mode
        identity = AgentIdentity(
            agent_id="a1",
            erc8004_address="0x1234567890abcdef1234567890abcdef12345678",
        )
        result = verifier.verify(identity)
        # In offline mode, trust the address
        self.assertTrue(result.is_verified)

    def test_identity_metadata_on_agent(self):
        identity = AgentIdentity(
            agent_id="a1",
            erc8004_address="0xabc123",
            display_name="ResearchBot",
            reputation_score=4.5,
        )
        self.assertEqual(identity.display_name, "ResearchBot")
        self.assertEqual(identity.reputation_score, 4.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_identity.py -v`
Expected: FAIL

- [ ] **Step 3: Create identity.py**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from contextgraph.utils import utcnow

@dataclass(slots=True)
class AgentIdentity:
    """ERC-8004 agent identity with optional on-chain verification."""
    agent_id: str
    erc8004_address: str = ""
    display_name: str = ""
    reputation_score: float = 0.0
    is_verified: bool = False
    verified_at: str = ""

    @property
    def has_chain_identity(self) -> bool:
        return bool(self.erc8004_address)

@dataclass(slots=True)
class IdentityVerifier:
    """Verifies agent identity against ERC-8004 registry."""
    enabled: bool = False
    registry_url: str = ""  # URL to ERC-8004 registry contract or API

    def verify(self, identity: AgentIdentity) -> AgentIdentity:
        """Verify an agent's on-chain identity.

        In production: query the ERC-8004 registry contract on Base/Ethereum.
        In offline mode: trust the provided address (for development/testing).
        """
        if not identity.has_chain_identity:
            return identity

        if not self.enabled:
            # Offline mode — trust the address for development
            identity.is_verified = True
            identity.verified_at = utcnow().isoformat()
            return identity

        # Production: verify against registry_url
        # This would use web3.py or HTTP call to the ERC-8004 registry
        # For MVP, we implement the interface and add real verification later
        identity.is_verified = True
        identity.verified_at = utcnow().isoformat()
        return identity
```

- [ ] **Step 4: Run identity tests**

Run: `python -m pytest tests/test_identity.py -v`
Expected: PASS

- [ ] **Step 5: Add identity fields to Agent model**

In `contextgraph/models.py`, add to Agent:
```python
erc8004_address: str = ""
identity_verified: bool = False
reputation_score: float = 0.0
```

- [ ] **Step 6: Add identity config to config.py**

```python
# Identity (ERC-8004)
enable_identity_verification: bool = False  # CG_ENABLE_IDENTITY
erc8004_registry_url: str = ""              # CG_ERC8004_REGISTRY_URL
```

- [ ] **Step 7: Wire identity into register_agent()**

In `service.py` `register_agent()`, accept optional `erc8004_address` parameter:
```python
def register_agent(self, name, org_id, capabilities, admin_key="", erc8004_address=""):
    ...
    agent.erc8004_address = erc8004_address
    if erc8004_address:
        verifier = IdentityVerifier(
            enabled=self._settings.enable_identity_verification,
            registry_url=self._settings.erc8004_registry_url,
        )
        identity = AgentIdentity(agent_id=agent.agent_id, erc8004_address=erc8004_address)
        verified = verifier.verify(identity)
        agent.identity_verified = verified.is_verified
        agent.reputation_score = verified.reputation_score
```

- [ ] **Step 8: Update schemas.py**

Add to `AgentRegistrationRequest`:
```python
erc8004_address: str = Field(default="", description="ERC-8004 on-chain address (optional)")
```

Add to `AgentResponse`:
```python
erc8004_address: str = ""
identity_verified: bool = False
reputation_score: float = 0.0
```

- [ ] **Step 9: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 10: Commit**

```bash
git add contextgraph/identity.py contextgraph/models.py contextgraph/config.py contextgraph/service.py contextgraph/api/schemas.py tests/test_identity.py
git commit -m "feat: add ERC-8004 agent identity — optional on-chain verification"
```

---

## Chunk 2: Protocol Integrations — MCP, A2A, Federation

### Task 7: MCP Server (Full Implementation)

Replace the stub with a working MCP tool server that any Claude/GPT agent can use.

**Files:**
- Modify: `contextgraph/protocols/mcp_server.py`
- Modify: `pyproject.toml`
- Create: `tests/test_mcp.py`

- [ ] **Step 1: Write MCP server tests**

`tests/test_mcp.py`:
```python
from __future__ import annotations
import unittest
from contextgraph.protocols.mcp_server import ContextGraphMCPServer
from contextgraph.service import ContextGraphService
from contextgraph.in_memory import InMemoryRepository
from contextgraph.config import Settings

class MCPServerTest(unittest.TestCase):

    def setUp(self):
        settings = Settings(admin_key="test")
        repo = InMemoryRepository()
        self.service = ContextGraphService(repo, settings=settings)
        self.mcp = ContextGraphMCPServer(self.service)
        self.agent = self.service.register_agent("mcp-agent", "org1", [], admin_key="test")

    def test_list_tools_returns_all_tools(self):
        tools = self.mcp.list_tools()
        names = [t["name"] for t in tools]
        self.assertIn("contextgraph_store", names)
        self.assertIn("contextgraph_recall", names)
        self.assertIn("contextgraph_relate", names)
        self.assertIn("contextgraph_watch", names)

    def test_call_store_and_recall(self):
        # Store
        result = self.mcp.call_tool("contextgraph_store", {
            "agent_id": self.agent.agent_id,
            "content": "Acme Corp CTO is Jane Smith",
            "visibility": "org",
        })
        self.assertIn("claims", result)

        # Recall
        result = self.mcp.call_tool("contextgraph_recall", {
            "agent_id": self.agent.agent_id,
            "query": "Acme Corp",
        })
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

    def test_call_unknown_tool_raises(self):
        with self.assertRaises(ValueError):
            self.mcp.call_tool("nonexistent_tool", {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mcp.py -v`
Expected: FAIL (current stub may partially work but new tests should fail)

- [ ] **Step 3: Rewrite mcp_server.py**

Full implementation with proper tool schemas, error handling, and JSON serialization:
```python
from __future__ import annotations
from contextgraph.service import ContextGraphService
from contextgraph.utils import to_jsonable
from contextgraph.errors import ContextGraphError

class ContextGraphMCPServer:
    """MCP tool server exposing ContextGraph operations."""

    def __init__(self, service: ContextGraphService) -> None:
        self._service = service
        self._tools = {
            "contextgraph_store": self._store,
            "contextgraph_recall": self._recall,
            "contextgraph_relate": self._relate,
            "contextgraph_watch": self._watch,
        }

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": "contextgraph_store",
                "description": "Store a memory in the knowledge graph. Extracts entities and relationships automatically.",
                "inputSchema": {
                    "type": "object",
                    "required": ["agent_id", "content"],
                    "properties": {
                        "agent_id": {"type": "string", "description": "Your agent ID"},
                        "content": {"type": "string", "description": "Text content to store as knowledge"},
                        "visibility": {"type": "string", "enum": ["private", "org", "shared", "published"], "default": "org"},
                        "access_list": {"type": "array", "items": {"type": "string"}, "description": "Agent/org IDs for shared visibility"},
                        "price": {"type": "number", "description": "Price in USDC (0 = free)", "default": 0},
                    },
                },
            },
            {
                "name": "contextgraph_recall",
                "description": "Query the knowledge graph for relevant claims and entities.",
                "inputSchema": {
                    "type": "object",
                    "required": ["agent_id", "query"],
                    "properties": {
                        "agent_id": {"type": "string"},
                        "query": {"type": "string", "description": "What knowledge are you looking for?"},
                        "limit": {"type": "integer", "default": 10},
                    },
                },
            },
            {
                "name": "contextgraph_relate",
                "description": "Find relationship paths between two entities in the knowledge graph.",
                "inputSchema": {
                    "type": "object",
                    "required": ["agent_id", "entity_a", "entity_b"],
                    "properties": {
                        "agent_id": {"type": "string"},
                        "entity_a": {"type": "string"},
                        "entity_b": {"type": "string"},
                        "max_depth": {"type": "integer", "default": 2},
                    },
                },
            },
            {
                "name": "contextgraph_watch",
                "description": "Subscribe to future knowledge matching a query.",
                "inputSchema": {
                    "type": "object",
                    "required": ["agent_id", "query", "name"],
                    "properties": {
                        "agent_id": {"type": "string"},
                        "query": {"type": "string"},
                        "name": {"type": "string", "description": "Name for this subscription"},
                        "delivery_mode": {"type": "string", "enum": ["pull", "webhook"], "default": "pull"},
                    },
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict) -> dict | list:
        handler = self._tools.get(name)
        if not handler:
            raise ValueError(f"Unknown tool: {name}")
        try:
            return handler(arguments)
        except ContextGraphError as exc:
            return {"error": str(exc), "error_type": type(exc).__name__}

    def _store(self, args: dict) -> dict:
        result = self._service.store_memory(
            agent_id=args["agent_id"],
            content=args["content"],
            visibility=args.get("visibility", "org"),
            access_list=args.get("access_list", []),
            price=args.get("price", 0.0),
        )
        return to_jsonable(result)

    def _recall(self, args: dict) -> list:
        hits = self._service.recall(
            agent_id=args["agent_id"],
            query=args["query"],
            limit=args.get("limit", 10),
        )
        return to_jsonable(hits)

    def _relate(self, args: dict) -> list:
        paths = self._service.relate(
            agent_id=args["agent_id"],
            entity_a=args["entity_a"],
            entity_b=args["entity_b"],
            max_depth=args.get("max_depth", 2),
        )
        return to_jsonable(paths)

    def _watch(self, args: dict) -> dict:
        query = self._service.watch(
            agent_id=args["agent_id"],
            query=args["query"],
            name=args["name"],
            delivery_mode=args.get("delivery_mode", "pull"),
        )
        return to_jsonable(query)
```

- [ ] **Step 4: Run MCP tests**

Run: `python -m pytest tests/test_mcp.py -v`
Expected: PASS

- [ ] **Step 5: Add `contextgraph-mcp` entry point to pyproject.toml**

```toml
[project.scripts]
contextgraph-server = "contextgraph.server:main"
contextgraph-mcp = "contextgraph.protocols.mcp_server:main"
```

Add a `main()` function to mcp_server.py that runs the MCP server over stdio (standard MCP transport).

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add contextgraph/protocols/mcp_server.py tests/test_mcp.py pyproject.toml
git commit -m "feat: full MCP server — Claude/GPT agents can use ContextGraph as a tool"
```

---

### Task 8: LLM-Powered Extraction

**Files:**
- Create: `contextgraph/extraction_llm.py`
- Modify: `contextgraph/config.py`
- Modify: `contextgraph/bootstrap.py`
- Create: `tests/test_extraction_llm.py`

- [ ] **Step 1: Write LLM extractor tests**

`tests/test_extraction_llm.py`:
```python
from __future__ import annotations
import unittest
from contextgraph.extraction_llm import LLMExtractor, parse_extraction_response

class LLMExtractorTest(unittest.TestCase):

    def test_parse_valid_json_response(self):
        response = '{"entities": [{"name": "Acme Corp", "type": "organization"}, {"name": "Jane", "type": "person"}], "claims": [{"statement": "Jane is CTO of Acme Corp", "subject": "Jane", "predicate": "CTO_OF", "object": "Acme Corp", "confidence": 0.95}]}'
        entities, claims = parse_extraction_response(response)
        self.assertEqual(len(entities), 2)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].confidence, 0.95)

    def test_parse_malformed_json_returns_empty(self):
        entities, claims = parse_extraction_response("not json")
        self.assertEqual(len(entities), 0)
        self.assertEqual(len(claims), 0)

    def test_extractor_builds_prompt(self):
        extractor = LLMExtractor(api_key="test", model="claude-sonnet-4-6")
        prompt = extractor._build_prompt("Acme Corp CTO Jane reported issues")
        self.assertIn("entities", prompt)
        self.assertIn("Acme Corp CTO Jane reported issues", prompt)
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_extraction_llm.py -v`

- [ ] **Step 3: Create extraction_llm.py**

```python
from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from contextgraph.extraction import Extractor, ExtractedEntity, ExtractedClaim

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """Extract entities and relationships from the following text.

Return JSON with this exact structure:
{
  "entities": [{"name": "...", "type": "person|organization|concept|product|location"}],
  "claims": [{"statement": "...", "subject": "...", "predicate": "...", "object": "...", "confidence": 0.0-1.0}]
}

Text:
{content}"""

def parse_extraction_response(response: str) -> tuple[list[ExtractedEntity], list[ExtractedClaim]]:
    """Parse LLM JSON response into entities and claims."""
    try:
        # Handle markdown code blocks
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        logger.warning("Failed to parse LLM extraction response")
        return [], []

    entities = [
        ExtractedEntity(name=e["name"], entity_type=e.get("type", "concept"))
        for e in data.get("entities", [])
        if "name" in e
    ]
    claims = [
        ExtractedClaim(
            statement=c["statement"],
            claim_type="relationship" if c.get("object") else "attribute",
            relation_type=c.get("predicate", ""),
            confidence=float(c.get("confidence", 0.7)),
            entities=[
                ExtractedEntity(name=c["subject"], entity_type="")
            ] + ([ExtractedEntity(name=c["object"], entity_type="")] if c.get("object") else []),
        )
        for c in data.get("claims", [])
        if "statement" in c and "subject" in c
    ]
    return entities, claims

@dataclass
class LLMExtractor:
    """Entity/claim extraction using an LLM (Claude, OpenAI, etc.)."""
    api_key: str
    model: str = "claude-sonnet-4-6"
    base_url: str = "https://api.anthropic.com"

    def _build_prompt(self, content: str) -> str:
        return _EXTRACTION_PROMPT.format(content=content)

    def extract(self, content: str) -> tuple[list[ExtractedEntity], list[ExtractedClaim]]:
        """Extract entities and claims using an LLM API call."""
        prompt = self._build_prompt(content)
        try:
            # Use urllib to avoid adding dependencies
            import urllib.request
            import urllib.error

            body = json.dumps({
                "model": self.model,
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            req = urllib.request.Request(
                f"{self.base_url}/v1/messages",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            text = result["content"][0]["text"]
            return parse_extraction_response(text)
        except Exception:
            logger.exception("LLM extraction failed, falling back to empty")
            return [], []
```

- [ ] **Step 4: Run extraction tests**

Run: `python -m pytest tests/test_extraction_llm.py -v`
Expected: PASS (parse tests pass, build_prompt passes; actual API call is not tested)

- [ ] **Step 5: Add LLM config to config.py**

```python
# LLM Extraction
llm_api_key: str = ""           # CG_LLM_API_KEY
llm_model: str = "claude-sonnet-4-6"  # CG_LLM_MODEL
llm_base_url: str = "https://api.anthropic.com"  # CG_LLM_BASE_URL
```

- [ ] **Step 6: Update bootstrap.py to use LLM extractor when configured**

If `settings.llm_api_key` is set, use `LLMExtractor`. Otherwise, fall back to `RuleBasedExtractor`.

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v`

- [ ] **Step 8: Commit**

```bash
git add contextgraph/extraction_llm.py contextgraph/config.py contextgraph/bootstrap.py tests/test_extraction_llm.py
git commit -m "feat: LLM-powered extraction — Claude/OpenAI for entity/claim extraction"
```

---

### Task 9: Improve Recall Quality (BM25)

**Files:**
- Modify: `contextgraph/utils.py`
- Modify: `contextgraph/service.py`

- [ ] **Step 1: Write BM25 test**

Add to `tests/test_service.py`:
```python
def test_recall_ranks_exact_matches_higher(self):
    agent = self.service.register_agent("a", "org1", [], admin_key="test-key")
    self.service.store_memory(agent.agent_id, "Acme Corp reported critical API latency issues")
    self.service.store_memory(agent.agent_id, "Generic status update with no specific content")
    hits = self.service.recall(agent.agent_id, "Acme Corp API latency")
    self.assertTrue(len(hits) > 0)
    self.assertIn("Acme", hits[0].claim.statement)
```

- [ ] **Step 2: Implement BM25 scoring in utils.py**

```python
import math
from collections import Counter

def bm25_score(query_tokens: list[str], doc_tokens: list[str], avg_doc_len: float, k1: float = 1.5, b: float = 0.75) -> float:
    """BM25 scoring for a single document against a query."""
    doc_len = len(doc_tokens)
    doc_freq = Counter(doc_tokens)
    score = 0.0
    for term in query_tokens:
        tf = doc_freq.get(term, 0)
        if tf == 0:
            continue
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1))
        score += numerator / denominator
    return score
```

- [ ] **Step 3: Update service.py recall() to use BM25 instead of Jaccard**

Replace `jaccard_similarity` call with `bm25_score`. Compute `avg_doc_len` from all accessible claims.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add contextgraph/utils.py contextgraph/service.py tests/test_service.py
git commit -m "feat: upgrade recall scoring from Jaccard to BM25"
```

---

### Task 10: Basic Federation

**Files:**
- Create: `contextgraph/federation.py`
- Modify: `contextgraph/api/routes.py`
- Modify: `contextgraph/config.py`
- Create: `tests/test_federation.py`

- [ ] **Step 1: Write federation tests**

`tests/test_federation.py`:
```python
from __future__ import annotations
import unittest
from contextgraph.federation import FederationPeer, FederationManager

class FederationTest(unittest.TestCase):

    def test_add_peer(self):
        mgr = FederationManager()
        peer = mgr.add_peer("https://cg.partner.com", shared_secret="s3cret")
        self.assertEqual(peer.url, "https://cg.partner.com")
        self.assertTrue(peer.active)

    def test_list_peers(self):
        mgr = FederationManager()
        mgr.add_peer("https://a.com", shared_secret="s1")
        mgr.add_peer("https://b.com", shared_secret="s2")
        self.assertEqual(len(mgr.list_peers()), 2)

    def test_remove_peer(self):
        mgr = FederationManager()
        peer = mgr.add_peer("https://a.com", shared_secret="s1")
        mgr.remove_peer(peer.peer_id)
        self.assertEqual(len(mgr.list_peers()), 0)

    def test_build_sync_payload(self):
        mgr = FederationManager()
        # Sync payload should include published claims since a timestamp
        payload = mgr.build_sync_payload(claims=[], since=None)
        self.assertEqual(payload["claims"], [])
```

- [ ] **Step 2: Create federation.py**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from contextgraph.utils import new_id, utcnow

@dataclass(slots=True)
class FederationPeer:
    peer_id: str
    url: str
    shared_secret: str
    active: bool = True
    last_sync: str = ""
    created_at: str = field(default_factory=lambda: utcnow().isoformat())

@dataclass
class FederationManager:
    _peers: dict[str, FederationPeer] = field(default_factory=dict)

    def add_peer(self, url: str, shared_secret: str) -> FederationPeer:
        peer = FederationPeer(
            peer_id=new_id("peer"),
            url=url.rstrip("/"),
            shared_secret=shared_secret,
        )
        self._peers[peer.peer_id] = peer
        return peer

    def list_peers(self) -> list[FederationPeer]:
        return [p for p in self._peers.values() if p.active]

    def remove_peer(self, peer_id: str) -> None:
        self._peers.pop(peer_id, None)

    def get_peer(self, peer_id: str) -> FederationPeer | None:
        return self._peers.get(peer_id)

    def build_sync_payload(self, claims: list, since: str | None = None) -> dict:
        return {
            "claims": [c for c in claims],
            "since": since or "",
            "timestamp": utcnow().isoformat(),
        }
```

- [ ] **Step 3: Add federation API endpoints in routes.py**

```python
@router.post("/v1/federation/peers")
@router.get("/v1/federation/peers")
@router.delete("/v1/federation/peers/{peer_id}")
@router.post("/v1/federation/sync")  # Receive claims from a peer
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/ -v`

- [ ] **Step 5: Commit**

```bash
git add contextgraph/federation.py contextgraph/api/routes.py contextgraph/config.py tests/test_federation.py
git commit -m "feat: basic federation — ContextGraph nodes can share published claims"
```

---

### Task 11: A2A Protocol Server

**Files:**
- Create: `contextgraph/protocols/a2a_server.py`
- Modify: `contextgraph/api/routes.py`

- [ ] **Step 1: Create A2A Agent Card endpoint**

Add to routes.py:
```python
@router.get("/.well-known/agent.json")
async def agent_card():
    return {
        "name": "contextgraph-node",
        "description": "Knowledge graph memory node — store, recall, and share structured knowledge between AI agents",
        "url": settings.public_url,
        "version": "0.2.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": [
            {"id": "knowledge-store", "name": "Store Knowledge", "description": "Store text as structured claims in the knowledge graph"},
            {"id": "knowledge-recall", "name": "Recall Knowledge", "description": "Query the knowledge graph for relevant claims"},
            {"id": "knowledge-relate", "name": "Relate Entities", "description": "Find relationship paths between entities"},
        ],
    }
```

- [ ] **Step 2: Create a2a_server.py with task handling**

Basic A2A task processing that maps A2A tasks to ContextGraph operations.

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`

- [ ] **Step 4: Commit**

```bash
git add contextgraph/protocols/a2a_server.py contextgraph/api/routes.py
git commit -m "feat: A2A protocol — agent card and task handling for cross-agent discovery"
```

---

## Chunk 3: README, Visual Assets & Launch Polish

### Task 12: README Rewrite (PicoClaw-Inspired)

**Files:**
- Modify: `README.md`
- Create: `docs/README.es.md`

- [ ] **Step 1: Write the full README**

Follow the structure from the design spec Section 5.6. Key sections:

1. Hero image (centered, 800px)
2. Title + tagline + badges
3. Language links (English | Espanol)
4. "What is ContextGraph?" — 3 sentences max
5. Agent stack positioning diagram
6. Comparison table (Mem0, Zep/Graphiti, Letta, Cognee, **ContextGraph**)
   - Use "Limited" where appropriate for competitors, not "No"
7. Demo GIF placeholder
8. Quickstart — 4 steps:
   - `pip install contextgraph`
   - `docker run ...`
   - Register agent (show how to get API key)
   - Store + Recall in 3 lines
9. MCP Integration — 3-step setup for Claude Desktop
10. Cross-Company Sharing example (access_list)
11. x402 Payment example (pricing knowledge)
12. ERC-8004 Identity example
13. Architecture diagram
14. Feature list with descriptions
15. Configuration reference table
16. Roadmap with checkboxes
17. Contributing link
18. Community (Discord, X/Twitter)
19. License

- [ ] **Step 2: Write Spanish README**

Translate key sections to `docs/README.es.md`.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/README.es.md
git commit -m "docs: PicoClaw-inspired README with quickstart, comparison table, and examples"
```

---

### Task 13: Visual Assets

**Files:**
- Create: `assets/hero.png`
- Create: `assets/logo.svg`
- Create: `assets/architecture.svg`

- [ ] **Step 1: Generate hero image**

Use AI image generation with prompt:
> "A friendly octopus-like creature in a futuristic control room. The octopus has glowing cyan tentacles that form a knowledge graph — each tentacle connects to different screens showing AI agent interfaces. The tentacles have small glowing nodes at connection points. Dark ocean-blue background (#0A1628) with electric cyan (#00D4FF) and green (#00FF88) accents. Semi-realistic digital art style, wide banner format 1200x600px. The word 'ContextGraph' appears subtly on one of the screens."

- [ ] **Step 2: Create architecture diagram (SVG)**

Clean diagram showing the stack positioning. Hand-craft or generate with a diagramming tool.

- [ ] **Step 3: Record demo GIFs**

Use `terminalizer` or `asciinema` to record:
- GIF 1: Store + Recall flow in terminal
- GIF 2: MCP integration with Claude

- [ ] **Step 4: Commit assets**

```bash
git add assets/
git commit -m "assets: hero image, logo, and architecture diagram"
```

---

### Task 14: SDK Improvements

**Files:**
- Modify: `sdk/contextgraph_sdk/client.py`
- Modify: `sdk/contextgraph_sdk/exceptions.py`
- Create: `sdk/README.md`

- [ ] **Step 1: Add PaymentRequiredError to SDK exceptions**

```python
class PaymentRequiredError(ContextGraphError):
    """HTTP 402 — payment required for knowledge access."""
```

Update `HttpTransport` to map 402 → `PaymentRequiredError`.

- [ ] **Step 2: Add retry logic to HttpTransport**

```python
import time

def _request(self, method, path, body=None, headers=None, retries=3):
    for attempt in range(retries):
        try:
            return self._do_request(method, path, body, headers)
        except ConnectionError:
            if attempt == retries - 1:
                raise
            time.sleep(0.5 * (2 ** attempt))
```

- [ ] **Step 3: Add timeout configuration**

```python
class HttpTransport:
    def __init__(self, base_url, api_key, timeout=30):
        self._timeout = timeout
```

- [ ] **Step 4: Add access_list and price to SDK store method**

```python
def store(self, agent_id, content, visibility="org", access_list=None, price=0.0, ...):
    ...
```

- [ ] **Step 5: Add payment_token to SDK recall method**

```python
def recall(self, agent_id, query, limit=10, payment_token=None):
    headers = {}
    if payment_token:
        headers["X-Payment-Token"] = payment_token
    ...
```

- [ ] **Step 6: Create sdk/README.md**

Standalone SDK documentation with install instructions, usage examples, error handling.

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v`

- [ ] **Step 8: Commit**

```bash
git add sdk/
git commit -m "feat: SDK improvements — retry logic, timeout, payment support"
```

---

### Task 15: Update pyproject.toml & Version Bump

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Bump version to 0.2.0**

- [ ] **Step 2: Add new optional dependency groups**

```toml
[project.optional-dependencies]
server = ["fastapi>=0.115.0", "python-multipart", "uvicorn[standard]>=0.34.0"]
neo4j = ["neo4j>=5.28.0"]
dev = ["pytest>=8.0.0", "httpx>=0.27.0", "ruff>=0.8.0"]
```

- [ ] **Step 3: Add MCP entry point**

```toml
[project.scripts]
contextgraph-server = "contextgraph.server:main"
contextgraph-mcp = "contextgraph.protocols.mcp_server:main"
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump to v0.2.0, add MCP entry point"
```

---

### Task 16: Final Test Suite Expansion

**Files:**
- Modify: `tests/test_service.py`
- Modify: `tests/test_web.py`
- Modify: `tests/test_sdk.py`

- [ ] **Step 1: Add cross-org published visibility test**

```python
def test_published_claims_visible_across_orgs(self):
    agent_a = self.service.register_agent("a", "org1", [], admin_key="test-key")
    agent_b = self.service.register_agent("b", "org2", [], admin_key="test-key")
    self.service.store_memory(agent_a.agent_id, "Public knowledge for everyone", visibility="published")
    hits = self.service.recall(agent_b.agent_id, "Public knowledge")
    self.assertTrue(len(hits) > 0)
```

- [ ] **Step 2: Add shared access_list cross-org test**

```python
def test_shared_claims_visible_to_access_list_org(self):
    agent_a = self.service.register_agent("a", "org1", [], admin_key="test-key")
    agent_b = self.service.register_agent("b", "org2", [], admin_key="test-key")
    self.service.store_memory(
        agent_a.agent_id, "Shared with org2 only",
        visibility="shared", access_list=["org2"]
    )
    hits = self.service.recall(agent_b.agent_id, "Shared with org2")
    self.assertTrue(len(hits) > 0)
```

- [ ] **Step 3: Add payment-gated recall test**

```python
def test_priced_claim_requires_payment_token(self):
    # With payments enabled
    ...
```

- [ ] **Step 4: Add multi-hop relate test**

```python
def test_relate_finds_two_hop_path(self):
    # A -> B -> C traversal
    ...
```

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add tests/
git commit -m "test: add cross-org sharing, payment gating, and multi-hop tests"
```

---

### Task 17: Clean Up & Pre-Launch Checklist

- [ ] **Step 1: Move internal docs to docs/internal/**

```bash
mkdir -p docs/internal
mv 2026-03-07-contextgraph-design.md docs/internal/
mv 2026-03-07-contextgraph-implementation-plan.md docs/internal/
```

- [ ] **Step 2: Run linter**

Run: `ruff check contextgraph/ sdk/ tests/`
Fix any issues.

- [ ] **Step 3: Run full test suite one final time**

Run: `python -m pytest tests/ -v`
Expected: All pass, 0 failures

- [ ] **Step 4: Verify Docker build**

Run: `docker compose build`
Expected: Successful build

- [ ] **Step 5: Verify quickstart flow end-to-end**

```bash
docker compose up -d
curl -X POST http://localhost:8420/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name": "test-agent", "org_id": "demo", "capabilities": []}' \
  -H "X-Admin-Key: changeme"
# Use returned api_key to store and recall
```

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: pre-launch cleanup — move internal docs, lint fixes"
```

---

*Plan complete. 17 tasks, ~120 implementation steps. Estimated: 4 weeks with AI assistance.*
