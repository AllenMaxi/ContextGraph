# Knowledge Sharing & Dashboard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform ContextGraph into a knowledge-sharing protocol with rich memory recall, agent follow/feed system, trust scores, claim editing, and a full dark-mode dashboard.

**Architecture:** Backend-first — models, repository, service, routes, then dashboard. Each task builds on the previous. All new features follow existing patterns: dataclass models, Protocol repository, InMemoryRepository implementation, service methods, FastAPI routes.

**Tech Stack:** Python 3.11+, FastAPI, vanilla HTML/JS/CSS (dashboard), Canvas API (graph viz)

**Spec:** `docs/superpowers/specs/2026-03-14-knowledge-sharing-dashboard-design.md`

---

## Chunk 1: Data Models & Repository Layer

### Task 1: Add SubscriptionTarget enum and Subscription model

**Files:**
- Modify: `contextgraph/models.py`
- Test: `tests/test_models.py` (create)

- [ ] **Step 1: Write the test**

```python
# tests/test_models.py
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from contextgraph.models import Subscription, SubscriptionTarget


class SubscriptionModelTest(unittest.TestCase):
    def test_subscription_target_enum_values(self) -> None:
        self.assertEqual(SubscriptionTarget.AGENT, "agent")
        self.assertEqual(SubscriptionTarget.TOPIC, "topic")
        self.assertEqual(SubscriptionTarget.ENTITY, "entity")
        self.assertEqual(SubscriptionTarget.ORG, "org")

    def test_subscription_dataclass_defaults(self) -> None:
        now = datetime.now(tz=timezone.utc)
        sub = Subscription(
            subscription_id="sub_001",
            follower_agent_id="agt_alice",
            target_type=SubscriptionTarget.AGENT,
            target_id="agt_bob",
            created_at=now,
        )
        self.assertTrue(sub.active)
        self.assertEqual(sub.target_type, SubscriptionTarget.AGENT)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: FAIL — `SubscriptionTarget` and `Subscription` not defined

- [ ] **Step 3: Add models to models.py**

Add after `JobType` enum (line 48) in `contextgraph/models.py`:

```python
class SubscriptionTarget(StrEnum):
    AGENT = "agent"
    TOPIC = "topic"
    ENTITY = "entity"
    ORG = "org"
```

Add after `StoreResult` (end of file) in `contextgraph/models.py`:

```python
@dataclass(slots=True)
class Subscription:
    subscription_id: str
    follower_agent_id: str
    target_type: SubscriptionTarget
    target_id: str
    created_at: datetime
    active: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add contextgraph/models.py tests/test_models.py
git commit -m "feat: add SubscriptionTarget enum and Subscription model"
```

### Task 2: Update RecallHit with memory content fields

**Files:**
- Modify: `contextgraph/models.py:178-183`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_models.py`:

```python
from contextgraph.models import Claim, Entity, RecallHit, ValidationStatus, Visibility


class RecallHitModelTest(unittest.TestCase):
    def test_recall_hit_new_fields_have_defaults(self) -> None:
        now = datetime.now(tz=timezone.utc)
        claim = Claim(
            claim_id="clm_1",
            memory_id="mem_1",
            source_agent_id="agt_1",
            statement="Test",
            claim_type="attribute",
            relation_type=None,
            confidence=0.9,
            freshness_score=1.0,
            validation_status=ValidationStatus.UNREVIEWED,
            visibility=Visibility.PUBLISHED,
            license="internal",
            entity_ids=[],
            created_at=now,
            expires_at=None,
            updated_at=now,
        )
        # Old constructor still works (backward compat)
        hit = RecallHit(claim=claim, score=0.85, entities=[])
        self.assertEqual(hit.memory_content, "")
        self.assertEqual(hit.source_agent_name, "")
        self.assertEqual(hit.source_reputation_score, 0.0)

    def test_recall_hit_with_new_fields(self) -> None:
        now = datetime.now(tz=timezone.utc)
        claim = Claim(
            claim_id="clm_1", memory_id="mem_1", source_agent_id="agt_1",
            statement="Test", claim_type="attribute", relation_type=None,
            confidence=0.9, freshness_score=1.0,
            validation_status=ValidationStatus.UNREVIEWED,
            visibility=Visibility.PUBLISHED, license="internal",
            entity_ids=[], created_at=now, expires_at=None, updated_at=now,
        )
        hit = RecallHit(
            claim=claim, score=0.85, entities=[],
            memory_content="Full analysis here...",
            source_agent_name="research-bot",
            source_reputation_score=0.92,
        )
        self.assertEqual(hit.memory_content, "Full analysis here...")
        self.assertEqual(hit.source_agent_name, "research-bot")
        self.assertEqual(hit.source_reputation_score, 0.92)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_models.py::RecallHitModelTest -v`
Expected: FAIL — `RecallHit` doesn't accept `memory_content`

- [ ] **Step 3: Update RecallHit in models.py**

Replace the RecallHit dataclass at line 178-183:

```python
@dataclass(slots=True)
class RecallHit:
    claim: Claim
    score: float
    entities: list[Entity]
    memory_content: str = ""
    source_agent_name: str = ""
    source_reputation_score: float = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add contextgraph/models.py tests/test_models.py
git commit -m "feat: add memory_content and reputation fields to RecallHit"
```

### Task 3: Add followers_count to Agent model

**Files:**
- Modify: `contextgraph/models.py:50-62`

- [ ] **Step 1: Add field to Agent**

Add after `reputation_score` (line 62):

```python
    followers_count: int = 0
```

- [ ] **Step 2: Run all existing tests to verify nothing breaks**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All tests pass (new field has default)

- [ ] **Step 3: Commit**

```bash
git add contextgraph/models.py
git commit -m "feat: add followers_count field to Agent model"
```

### Task 4: Add subscription methods to Repository protocol and InMemoryRepository

**Files:**
- Modify: `contextgraph/repository.py`
- Modify: `contextgraph/in_memory.py`
- Test: `tests/test_subscription_repo.py` (create)

- [ ] **Step 1: Write the test**

```python
# tests/test_subscription_repo.py
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from contextgraph.in_memory import InMemoryRepository
from contextgraph.models import Subscription, SubscriptionTarget


class SubscriptionRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryRepository()
        self.now = datetime.now(tz=timezone.utc)

    def test_save_and_get_subscription(self) -> None:
        sub = Subscription(
            subscription_id="sub_1",
            follower_agent_id="agt_alice",
            target_type=SubscriptionTarget.AGENT,
            target_id="agt_bob",
            created_at=self.now,
        )
        self.repo.save_subscription(sub)
        result = self.repo.get_subscription("sub_1")
        self.assertIsNotNone(result)
        self.assertEqual(result.follower_agent_id, "agt_alice")

    def test_get_subscriptions_by_follower(self) -> None:
        for i in range(3):
            self.repo.save_subscription(Subscription(
                subscription_id=f"sub_{i}",
                follower_agent_id="agt_alice",
                target_type=SubscriptionTarget.TOPIC,
                target_id=f"topic_{i}",
                created_at=self.now,
            ))
        self.repo.save_subscription(Subscription(
            subscription_id="sub_other",
            follower_agent_id="agt_bob",
            target_type=SubscriptionTarget.AGENT,
            target_id="agt_alice",
            created_at=self.now,
        ))
        subs = self.repo.get_subscriptions_by_follower("agt_alice")
        self.assertEqual(len(subs), 3)

    def test_get_followers_of_agent(self) -> None:
        self.repo.save_subscription(Subscription(
            subscription_id="sub_1",
            follower_agent_id="agt_alice",
            target_type=SubscriptionTarget.AGENT,
            target_id="agt_bob",
            created_at=self.now,
        ))
        self.repo.save_subscription(Subscription(
            subscription_id="sub_2",
            follower_agent_id="agt_charlie",
            target_type=SubscriptionTarget.AGENT,
            target_id="agt_bob",
            created_at=self.now,
        ))
        followers = self.repo.get_followers_of_agent("agt_bob")
        self.assertEqual(len(followers), 2)

    def test_delete_subscription(self) -> None:
        self.repo.save_subscription(Subscription(
            subscription_id="sub_1",
            follower_agent_id="agt_alice",
            target_type=SubscriptionTarget.AGENT,
            target_id="agt_bob",
            created_at=self.now,
        ))
        self.repo.delete_subscription("sub_1")
        self.assertIsNone(self.repo.get_subscription("sub_1"))

    def test_get_nonexistent_subscription_returns_none(self) -> None:
        self.assertIsNone(self.repo.get_subscription("sub_nope"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_subscription_repo.py -v`
Expected: FAIL — methods don't exist

- [ ] **Step 3: Add methods to Repository protocol**

Add to `contextgraph/repository.py` imports:

```python
from .models import Agent, AuditEntry, Claim, Entity, Memory, Notification, ReviewTask, StandingQuery, Subscription
```

Add to the `Repository` Protocol class before `snapshot`:

```python
    def save_subscription(self, subscription: Subscription) -> Subscription: ...
    def get_subscription(self, subscription_id: str) -> Subscription | None: ...
    def get_subscriptions_by_follower(self, agent_id: str) -> list[Subscription]: ...
    def get_followers_of_agent(self, agent_id: str) -> list[Subscription]: ...
    def delete_subscription(self, subscription_id: str) -> None: ...
```

- [ ] **Step 4: Implement in InMemoryRepository**

Add to `contextgraph/in_memory.py` imports:

```python
from .models import Agent, AuditEntry, Claim, Entity, Memory, Notification, ReviewTask, StandingQuery, Subscription, SubscriptionTarget
```

Add to `__init__`:

```python
        self._subscriptions: dict[str, Subscription] = {}
```

Add methods before `snapshot`:

```python
    def save_subscription(self, subscription: Subscription) -> Subscription:
        with self._lock:
            self._subscriptions[subscription.subscription_id] = subscription
            return subscription

    def get_subscription(self, subscription_id: str) -> Subscription | None:
        with self._lock:
            return self._subscriptions.get(subscription_id)

    def get_subscriptions_by_follower(self, agent_id: str) -> list[Subscription]:
        with self._lock:
            return [s for s in self._subscriptions.values() if s.follower_agent_id == agent_id and s.active]

    def get_followers_of_agent(self, agent_id: str) -> list[Subscription]:
        with self._lock:
            return [
                s for s in self._subscriptions.values()
                if s.target_type == SubscriptionTarget.AGENT and s.target_id == agent_id and s.active
            ]

    def delete_subscription(self, subscription_id: str) -> None:
        with self._lock:
            self._subscriptions.pop(subscription_id, None)
```

Update `snapshot` to include subscriptions:

```python
    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                ...existing fields...,
                "subscriptions": len(self._subscriptions),
            }
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_subscription_repo.py -v`
Expected: PASS

- [ ] **Step 6: Run full test suite**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add contextgraph/repository.py contextgraph/in_memory.py tests/test_subscription_repo.py
git commit -m "feat: add subscription storage to repository layer"
```

---

## Chunk 2: Service Layer — Reputation, Follow, Feed, Recall Update, Claim Edit

### Task 5: Add reputation score calculation

**Files:**
- Modify: `contextgraph/service.py`
- Test: `tests/test_reputation.py` (create)

- [ ] **Step 1: Write the test**

```python
# tests/test_reputation.py
from __future__ import annotations

import unittest

from contextgraph.service import ContextGraphService


class ReputationScoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.agent = self.service.register_agent("research-bot", "acme", ["research"])

    def test_new_agent_has_neutral_score(self) -> None:
        score = self.service.calculate_reputation_score(self.agent.agent_id)
        self.assertEqual(score, 0.5)

    def test_all_attested_claims_high_score(self) -> None:
        # Store a memory that creates claims
        self.service.store_memory(self.agent.agent_id, "Acme Corp reported API latency spikes.", visibility="published")
        claims = self.service.list_claims(self.agent.agent_id)
        # Attest all claims
        for claim in claims:
            self.service.review_claim(self.agent.agent_id, claim.claim_id, "attested", "Confirmed")
        score = self.service.calculate_reputation_score(self.agent.agent_id)
        self.assertGreater(score, 0.5)

    def test_all_challenged_claims_low_score(self) -> None:
        self.service.store_memory(self.agent.agent_id, "Globex Inc had server outages.", visibility="published")
        claims = self.service.list_claims(self.agent.agent_id)
        for claim in claims:
            self.service.review_claim(self.agent.agent_id, claim.claim_id, "challenged", "Incorrect")
        score = self.service.calculate_reputation_score(self.agent.agent_id)
        self.assertLess(score, 0.5)

    def test_review_claim_updates_agent_reputation(self) -> None:
        self.service.store_memory(self.agent.agent_id, "Acme Corp reported API latency.", visibility="published")
        claims = self.service.list_claims(self.agent.agent_id)
        self.service.review_claim(self.agent.agent_id, claims[0].claim_id, "attested", "Good")
        agent = self.service.get_agent(self.agent.agent_id)
        self.assertGreater(agent.reputation_score, 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_reputation.py -v`
Expected: FAIL — `calculate_reputation_score` not defined

- [ ] **Step 3: Implement calculate_reputation_score in service.py**

Add method to `ContextGraphService`:

```python
    def calculate_reputation_score(self, agent_id: str) -> float:
        claims = [c for c in self.repository.list_claims() if c.source_agent_id == agent_id]
        if not claims:
            return 0.5
        attested = sum(1 for c in claims if c.validation_status == ValidationStatus.ATTESTED)
        challenged = sum(1 for c in claims if c.validation_status == ValidationStatus.CHALLENGED)
        total_reviewed = attested + challenged
        if total_reviewed == 0:
            return 0.5
        base = attested / total_reviewed
        volume_factor = min(1.0, total_reviewed / 20)
        return round(base * 0.7 + volume_factor * 0.3, 2)
```

Add reputation recalculation at the end of `review_claim()`, before the return:

```python
        # Recalculate source agent reputation
        source_agent = self.get_agent(claim.source_agent_id)
        source_agent.reputation_score = self.calculate_reputation_score(claim.source_agent_id)
        self.repository.save_agent(source_agent)
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_reputation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add contextgraph/service.py tests/test_reputation.py
git commit -m "feat: add reputation score calculation with auto-recalculation on review"
```

### Task 6: Add follow/unfollow service methods

**Files:**
- Modify: `contextgraph/service.py`
- Test: `tests/test_follow.py` (create)

- [ ] **Step 1: Write the test**

```python
# tests/test_follow.py
from __future__ import annotations

import unittest

from contextgraph.errors import NotFoundError, PermissionDeniedError
from contextgraph.service import ContextGraphService


class FollowServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.alice = self.service.register_agent("alice", "acme", ["research"])
        self.bob = self.service.register_agent("bob", "acme", ["support"])

    def test_follow_agent(self) -> None:
        sub = self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.assertEqual(sub.follower_agent_id, self.alice.agent_id)
        self.assertEqual(sub.target_id, self.bob.agent_id)

    def test_follow_topic(self) -> None:
        sub = self.service.follow(self.alice.agent_id, "topic", "semiconductor")
        self.assertEqual(sub.target_type.value, "topic")
        self.assertEqual(sub.target_id, "semiconductor")

    def test_duplicate_follow_raises_conflict(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        with self.assertRaises(ValueError):
            self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)

    def test_unfollow(self) -> None:
        sub = self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.unfollow(self.alice.agent_id, sub.subscription_id)
        following = self.service.list_following(self.alice.agent_id)
        self.assertEqual(len(following), 0)

    def test_unfollow_by_other_agent_raises_permission_denied(self) -> None:
        sub = self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        with self.assertRaises(PermissionDeniedError):
            self.service.unfollow(self.bob.agent_id, sub.subscription_id)

    def test_list_following(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.follow(self.alice.agent_id, "topic", "AI")
        following = self.service.list_following(self.alice.agent_id)
        self.assertEqual(len(following), 2)

    def test_list_followers(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        followers = self.service.list_followers(self.bob.agent_id)
        self.assertEqual(len(followers), 1)
        self.assertEqual(followers[0].follower_agent_id, self.alice.agent_id)

    def test_follow_updates_followers_count(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        bob = self.service.get_agent(self.bob.agent_id)
        self.assertEqual(bob.followers_count, 1)

    def test_unfollow_decrements_followers_count(self) -> None:
        sub = self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.unfollow(self.alice.agent_id, sub.subscription_id)
        bob = self.service.get_agent(self.bob.agent_id)
        self.assertEqual(bob.followers_count, 0)

    def test_max_subscriptions_enforced(self) -> None:
        for i in range(200):
            self.service.follow(self.alice.agent_id, "topic", f"topic_{i}")
        with self.assertRaises(ValueError):
            self.service.follow(self.alice.agent_id, "topic", "topic_overflow")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_follow.py -v`
Expected: FAIL — `follow` method not defined

- [ ] **Step 3: Implement follow/unfollow in service.py**

Add to `ContextGraphService`:

```python
    _MAX_SUBSCRIPTIONS = 200

    def follow(self, agent_id: str, target_type: str, target_id: str) -> Subscription:
        self.get_agent(agent_id)
        target_enum = SubscriptionTarget(target_type)

        # Validate target exists for agent/org types
        if target_enum == SubscriptionTarget.AGENT:
            self.get_agent(target_id)
        elif target_enum == SubscriptionTarget.ORG:
            # Just check any agent in that org exists
            if not any(a.org_id == target_id for a in self.repository.list_agents()):
                raise NotFoundError(f"No agents found in org '{target_id}'.")

        # Check duplicate
        existing = self.repository.get_subscriptions_by_follower(agent_id)
        for sub in existing:
            if sub.target_type == target_enum and sub.target_id == target_id:
                raise ValueError(f"Already following {target_type}:{target_id}")

        # Check max limit
        if len(existing) >= self._MAX_SUBSCRIPTIONS:
            raise ValueError(f"Maximum {self._MAX_SUBSCRIPTIONS} subscriptions reached.")

        subscription = Subscription(
            subscription_id=new_id("sub"),
            follower_agent_id=agent_id,
            target_type=target_enum,
            target_id=target_id,
            created_at=utcnow(),
        )
        self.repository.save_subscription(subscription)

        # Update followers_count for agent targets
        if target_enum == SubscriptionTarget.AGENT:
            target_agent = self.get_agent(target_id)
            target_agent.followers_count = len(self.repository.get_followers_of_agent(target_id))
            self.repository.save_agent(target_agent)

        self._audit("follow", actor_agent_id=agent_id, details={"target_type": target_type, "target_id": target_id})
        return subscription

    def unfollow(self, agent_id: str, subscription_id: str) -> None:
        self.get_agent(agent_id)
        sub = self.repository.get_subscription(subscription_id)
        if sub is None:
            raise NotFoundError(f"Subscription '{subscription_id}' not found.")
        if sub.follower_agent_id != agent_id:
            raise PermissionDeniedError("Only the subscriber can unfollow.")

        self.repository.delete_subscription(subscription_id)

        # Update followers_count for agent targets
        if sub.target_type == SubscriptionTarget.AGENT:
            target_agent = self.get_agent(sub.target_id)
            target_agent.followers_count = len(self.repository.get_followers_of_agent(sub.target_id))
            self.repository.save_agent(target_agent)

        self._audit("unfollow", actor_agent_id=agent_id, details={"subscription_id": subscription_id})

    def list_following(self, agent_id: str) -> list[Subscription]:
        self.get_agent(agent_id)
        return self.repository.get_subscriptions_by_follower(agent_id)

    def list_followers(self, agent_id: str) -> list[Subscription]:
        self.get_agent(agent_id)
        return self.repository.get_followers_of_agent(agent_id)
```

Add imports at top of service.py:

```python
from .models import Subscription, SubscriptionTarget
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_follow.py -v`
Expected: PASS

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add contextgraph/service.py tests/test_follow.py
git commit -m "feat: add follow/unfollow agent/topic with duplicate prevention and max limit"
```

### Task 7: Update recall() to include memory content

**Files:**
- Modify: `contextgraph/service.py` (recall method, ~line 358-395)
- Test: `tests/test_recall_memory.py` (create)

- [ ] **Step 1: Write the test**

```python
# tests/test_recall_memory.py
from __future__ import annotations

import unittest

from contextgraph.service import ContextGraphService


class RecallMemoryContentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.agent = self.service.register_agent("research-bot", "acme", ["research"])
        self.service.store_memory(
            self.agent.agent_id,
            "Acme Corp reported API latency spikes in Q3 affecting 23% of clients. "
            "Root cause was connection pool exhaustion under concurrent load.",
            visibility="published",
        )

    def test_recall_returns_full_memory_content(self) -> None:
        hits = self.service.recall(self.agent.agent_id, "Acme API latency")
        self.assertGreater(len(hits), 0)
        hit = hits[0]
        self.assertIn("connection pool exhaustion", hit.memory_content)

    def test_recall_returns_source_agent_name(self) -> None:
        hits = self.service.recall(self.agent.agent_id, "Acme API latency")
        self.assertEqual(hits[0].source_agent_name, "research-bot")

    def test_recall_returns_reputation_score(self) -> None:
        hits = self.service.recall(self.agent.agent_id, "Acme API latency")
        # New agent has 0.0 reputation (no reviews yet), but calculate returns 0.5
        self.assertIsInstance(hits[0].source_reputation_score, float)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_recall_memory.py -v`
Expected: FAIL — `memory_content` is empty

- [ ] **Step 3: Update recall() in service.py**

In the `recall()` method, replace the hit construction (around line 386-392):

```python
            entities = [self.repository.get_entity(entity_id) for entity_id in claim.entity_ids]
            memory = self.repository.get_memory(claim.memory_id)
            source_agent = self.repository.get_agent(claim.source_agent_id)

            # For paid cross-org claims without payment, hide memory content
            show_content = True
            if claim.price > 0 and requester.org_id != claim.source_org_id and not payment_token:
                show_content = False

            hits.append(
                RecallHit(
                    claim=claim,
                    score=round(score, 4),
                    entities=[entity for entity in entities if entity is not None],
                    memory_content=memory.content if memory and show_content else "",
                    source_agent_name=source_agent.name if source_agent else "",
                    source_reputation_score=source_agent.reputation_score if source_agent else 0.0,
                )
            )
```

**Note:** The payment check at line 374-381 already raises `PaymentRequiredError` for priced claims without a token from a different org. So `show_content` logic above is for the edge case where same-org agents access priced claims (free for them, but payment_token is None).

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_recall_memory.py tests/test_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add contextgraph/service.py tests/test_recall_memory.py
git commit -m "feat: recall returns full memory content, source agent name, and reputation"
```

### Task 8: Add claim update (PATCH) service method

**Files:**
- Modify: `contextgraph/service.py`
- Test: `tests/test_claim_update.py` (create)

- [ ] **Step 1: Write the test**

```python
# tests/test_claim_update.py
from __future__ import annotations

import unittest

from contextgraph.errors import NotFoundError, PermissionDeniedError
from contextgraph.models import Visibility
from contextgraph.service import ContextGraphService


class ClaimUpdateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.alice = self.service.register_agent("alice", "acme", ["research"])
        self.bob = self.service.register_agent("bob", "acme", ["support"])
        result = self.service.store_memory(
            self.alice.agent_id, "Acme Corp reported Q3 results.", visibility="org",
        )
        self.claim = result.claims[0]

    def test_source_agent_can_update_visibility(self) -> None:
        updated = self.service.update_claim(
            self.alice.agent_id, self.claim.claim_id, visibility="published",
        )
        self.assertEqual(updated.visibility, Visibility.PUBLISHED)

    def test_source_agent_can_update_price(self) -> None:
        updated = self.service.update_claim(
            self.alice.agent_id, self.claim.claim_id, price=0.005,
        )
        self.assertEqual(updated.price, 0.005)

    def test_source_agent_can_update_access_list(self) -> None:
        updated = self.service.update_claim(
            self.alice.agent_id, self.claim.claim_id,
            visibility="shared", access_list=["agt_external"],
        )
        self.assertEqual(updated.visibility, Visibility.SHARED)
        self.assertIn("agt_external", updated.access_list)

    def test_other_agent_cannot_update_claim(self) -> None:
        with self.assertRaises(PermissionDeniedError):
            self.service.update_claim(
                self.bob.agent_id, self.claim.claim_id, visibility="published",
            )

    def test_update_nonexistent_claim_raises_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.update_claim(self.alice.agent_id, "clm_fake", visibility="published")

    def test_update_with_no_fields_is_noop(self) -> None:
        updated = self.service.update_claim(self.alice.agent_id, self.claim.claim_id)
        self.assertEqual(updated.visibility, self.claim.visibility)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_claim_update.py -v`
Expected: FAIL — `update_claim` method not defined with this signature

- [ ] **Step 3: Implement update_claim in service.py**

Add to `ContextGraphService`:

```python
    def update_claim(
        self,
        requester_agent_id: str,
        claim_id: str,
        visibility: str | None = None,
        price: float | None = None,
        access_list: list[str] | None = None,
    ) -> Claim:
        self.get_agent(requester_agent_id)
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            raise NotFoundError(f"Claim '{claim_id}' not found.")
        if claim.source_agent_id != requester_agent_id:
            raise PermissionDeniedError("Only the source agent can update a claim.")

        if visibility is not None:
            claim.visibility = Visibility(visibility)
        if price is not None:
            claim.price = price
        if access_list is not None:
            claim.access_list = list(access_list)

        claim.updated_at = utcnow()
        self.repository.update_claim(claim)
        self._audit("update_claim", actor_agent_id=requester_agent_id, details={"claim_id": claim_id})
        self._emit_notifications(claim)
        return claim
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_claim_update.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add contextgraph/service.py tests/test_claim_update.py
git commit -m "feat: add claim update (visibility, price, access_list) with source agent authorization"
```

### Task 9: Add knowledge feed service method

**Files:**
- Modify: `contextgraph/service.py`
- Test: `tests/test_feed.py` (create)

- [ ] **Step 1: Write the test**

```python
# tests/test_feed.py
from __future__ import annotations

import unittest

from contextgraph.service import ContextGraphService


class KnowledgeFeedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.alice = self.service.register_agent("alice", "acme", ["research"])
        self.bob = self.service.register_agent("bob", "acme", ["support"])

    def test_feed_empty_when_not_following_anyone(self) -> None:
        feed = self.service.get_feed(self.alice.agent_id)
        self.assertEqual(len(feed), 0)

    def test_feed_shows_followed_agent_memories(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.store_memory(self.bob.agent_id, "Globex Inc had server outages.", visibility="org")
        feed = self.service.get_feed(self.alice.agent_id)
        self.assertEqual(len(feed), 1)
        self.assertIn("server outages", feed[0]["memory_content"])

    def test_feed_shows_followed_topic_memories(self) -> None:
        self.service.follow(self.alice.agent_id, "topic", "semiconductor")
        self.service.store_memory(
            self.bob.agent_id,
            "TSMC semiconductor lead times extending in Q3 2026.",
            visibility="org",
        )
        feed = self.service.get_feed(self.alice.agent_id)
        self.assertGreater(len(feed), 0)

    def test_feed_respects_visibility(self) -> None:
        charlie = self.service.register_agent("charlie", "other_org", ["research"])
        self.service.follow(charlie.agent_id, "agent", self.bob.agent_id)
        self.service.store_memory(self.bob.agent_id, "Internal Acme data.", visibility="org")
        feed = self.service.get_feed(charlie.agent_id)
        # Charlie is in a different org, can't see ORG-scoped memories
        self.assertEqual(len(feed), 0)

    def test_feed_deduplicates_memories(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.follow(self.alice.agent_id, "topic", "Acme")
        self.service.store_memory(self.bob.agent_id, "Acme Corp reported Q4 growth.", visibility="org")
        feed = self.service.get_feed(self.alice.agent_id)
        memory_ids = [item["memory_id"] for item in feed]
        self.assertEqual(len(memory_ids), len(set(memory_ids)))

    def test_feed_pagination(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        for i in range(5):
            self.service.store_memory(self.bob.agent_id, f"Report number {i} about Acme Corp.", visibility="org")
        feed = self.service.get_feed(self.alice.agent_id, limit=2)
        self.assertEqual(len(feed), 2)

    def test_feed_includes_source_reputation(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.store_memory(self.bob.agent_id, "Globex Inc had server outages.", visibility="org")
        feed = self.service.get_feed(self.alice.agent_id)
        self.assertIn("source_reputation_score", feed[0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_feed.py -v`
Expected: FAIL — `get_feed` method not defined

- [ ] **Step 3: Implement get_feed in service.py**

Add `import math` to imports. Add to `ContextGraphService`:

```python
    def get_feed(self, agent_id: str, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        requester = self.get_agent(agent_id)
        subscriptions = self.repository.get_subscriptions_by_follower(agent_id)
        if not subscriptions:
            return []

        all_claims = self.repository.list_claims()
        self._sync_bm25_index(all_claims)

        # Group claims by memory_id
        claims_by_memory: dict[str, list[Claim]] = {}
        for claim in all_claims:
            claims_by_memory.setdefault(claim.memory_id, []).append(claim)

        # Collect matching memory_ids from subscriptions
        matched_memory_ids: set[str] = set()
        for sub in subscriptions:
            for memory_id, mem_claims in claims_by_memory.items():
                for claim in mem_claims:
                    if not self._can_access(requester, claim):
                        continue
                    if self._matches_subscription(sub, claim):
                        matched_memory_ids.add(memory_id)
                        break

        # Build feed items
        now = utcnow()
        feed_items: list[dict[str, Any]] = []
        for memory_id in matched_memory_ids:
            memory = self.repository.get_memory(memory_id)
            if memory is None:
                continue
            mem_claims = claims_by_memory.get(memory_id, [])
            if not mem_claims:
                continue
            source_agent = self.repository.get_agent(mem_claims[0].source_agent_id)
            if source_agent is None:
                continue

            entities: list[Entity] = []
            for claim in mem_claims:
                for eid in claim.entity_ids:
                    entity = self.repository.get_entity(eid)
                    if entity and entity not in entities:
                        entities.append(entity)

            age_hours = (now - memory.created_at).total_seconds() / 3600
            recency = math.exp(-age_hours / 168)
            score = recency * 0.6 + source_agent.reputation_score * 0.4

            max_price = max((c.price for c in mem_claims), default=0.0)

            feed_items.append({
                "memory_id": memory.memory_id,
                "memory_content": memory.content,
                "agent_id": memory.agent_id,
                "visibility": memory.visibility.value,
                "claims": mem_claims,
                "entities": entities,
                "source_agent_name": source_agent.name,
                "source_reputation_score": source_agent.reputation_score,
                "created_at": memory.created_at,
                "is_paid": max_price > 0,
                "price": max_price,
                "feed_score": round(score, 4),
            })

        feed_items.sort(key=lambda item: item["feed_score"], reverse=True)
        return feed_items[offset : offset + limit]

    def _matches_subscription(self, sub: Subscription, claim: Claim) -> bool:
        if sub.target_type == SubscriptionTarget.AGENT:
            return claim.source_agent_id == sub.target_id
        if sub.target_type == SubscriptionTarget.ORG:
            return claim.source_org_id == sub.target_id
        if sub.target_type == SubscriptionTarget.ENTITY:
            alias = normalize_alias(sub.target_id)
            for eid in claim.entity_ids:
                entity = self.repository.get_entity(eid)
                if entity and entity.alias_key == alias:
                    return True
            return False
        if sub.target_type == SubscriptionTarget.TOPIC:
            return self._bm25.score(claim.claim_id, sub.target_id) > 0
        return False
```

Add `Entity` to the imports from `.models` if not already there. Add `import math` at the top.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_feed.py -v`
Expected: PASS

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add contextgraph/service.py tests/test_feed.py
git commit -m "feat: add knowledge feed with subscription matching, ranking, and deduplication"
```

---

## Chunk 3: API Routes & Schemas

### Task 10: Add new API schemas

**Files:**
- Modify: `contextgraph/api/schemas.py`

- [ ] **Step 1: Add schemas**

Add to `contextgraph/api/schemas.py`:

```python
from ..models import SubscriptionTarget

class FollowRequest(BaseModel):
    target_type: SubscriptionTarget
    target_id: str

class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    subscription_id: str
    follower_agent_id: str
    target_type: SubscriptionTarget
    target_id: str
    created_at: datetime
    active: bool

class ClaimUpdateRequest(BaseModel):
    visibility: Visibility | None = None
    price: float | None = Field(default=None, ge=0.0)
    access_list: list[str] | None = None

class TrustScoreResponse(BaseModel):
    agent_id: str
    reputation_score: float
    total_claims: int
    attested_claims: int
    challenged_claims: int
    unreviewed_claims: int
    followers_count: int

class FeedItemResponse(BaseModel):
    memory_id: str
    memory_content: str
    agent_id: str
    visibility: str
    claims: list[ClaimResponse] = Field(default_factory=list)
    entities: list[EntityResponse] = Field(default_factory=list)
    source_agent_name: str
    source_reputation_score: float
    created_at: datetime
    is_paid: bool = False
    price: float = 0.0
```

Update `RecallHitResponse`:

```python
class RecallHitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    claim: ClaimResponse
    score: float
    entities: list[EntityResponse] = Field(default_factory=list)
    memory_content: str = ""
    source_agent_name: str = ""
    source_reputation_score: float = 0.0
```

Update `AgentResponse` to include `followers_count`:

```python
class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    agent_id: str
    name: str
    org_id: str
    capabilities: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime
    erc8004_address: str = ""
    identity_verified: bool = False
    reputation_score: float = 0.0
    followers_count: int = 0
```

- [ ] **Step 2: Run existing tests**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add contextgraph/api/schemas.py
git commit -m "feat: add API schemas for feed, follow, trust, claim update"
```

### Task 11: Add new API routes

**Files:**
- Modify: `contextgraph/api/routes.py`
- Test: `tests/test_web.py` (extend with new endpoint tests)

- [ ] **Step 1: Add routes**

Add imports to `routes.py`:

```python
from .schemas import (
    ...,  # existing imports
    ClaimUpdateRequest,
    FeedItemResponse,
    FollowRequest,
    SubscriptionResponse,
    TrustScoreResponse,
)
```

Add new endpoints inside `register_routes()`:

```python
    @app.get("/v1/feed", response_model=list[FeedItemResponse])
    def feed(
        limit: int = 20,
        offset: int = 0,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        return to_jsonable(graph.get_feed(
            agent_id=authenticated.agent_id,
            limit=min(limit, 100),
            offset=max(offset, 0),
        ))

    @app.post("/v1/follow", response_model=SubscriptionResponse, status_code=201)
    def follow(payload: FollowRequest, authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.follow(
            agent_id=authenticated.agent_id,
            target_type=payload.target_type.value,
            target_id=payload.target_id,
        ))

    @app.delete("/v1/follow/{subscription_id}", status_code=204)
    def unfollow(subscription_id: str, authenticated: Any = Depends(authenticated_agent)) -> Any:
        graph.unfollow(agent_id=authenticated.agent_id, subscription_id=subscription_id)

    @app.get("/v1/following", response_model=list[SubscriptionResponse])
    def following(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.list_following(agent_id=authenticated.agent_id))

    @app.get("/v1/followers", response_model=list[SubscriptionResponse])
    def followers(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.list_followers(agent_id=authenticated.agent_id))

    @app.get("/v1/agents/{agent_id}/trust", response_model=TrustScoreResponse)
    def trust_score(agent_id: str, authenticated: Any = Depends(authenticated_agent)) -> Any:
        agent = graph.get_agent(agent_id)
        claims = [c for c in graph.repository.list_claims() if c.source_agent_id == agent_id]
        from ..models import ValidationStatus
        return {
            "agent_id": agent_id,
            "reputation_score": agent.reputation_score,
            "total_claims": len(claims),
            "attested_claims": sum(1 for c in claims if c.validation_status == ValidationStatus.ATTESTED),
            "challenged_claims": sum(1 for c in claims if c.validation_status == ValidationStatus.CHALLENGED),
            "unreviewed_claims": sum(1 for c in claims if c.validation_status == ValidationStatus.UNREVIEWED),
            "followers_count": agent.followers_count,
        }

    @app.patch("/v1/claims/{claim_id}", response_model=ClaimResponse)
    def update_claim(claim_id: str, payload: ClaimUpdateRequest, authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.update_claim(
            requester_agent_id=authenticated.agent_id,
            claim_id=claim_id,
            visibility=payload.visibility.value if payload.visibility else None,
            price=payload.price,
            access_list=payload.access_list,
        ))
```

- [ ] **Step 2: Run full test suite**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 3: Run lint**

Run: `ruff check contextgraph/ sdk/ tests/ && ruff format contextgraph/ sdk/ tests/`
Expected: Clean

- [ ] **Step 4: Commit**

```bash
git add contextgraph/api/routes.py
git commit -m "feat: add API routes for feed, follow/unfollow, trust score, claim PATCH"
```

---

## Chunk 4: Dashboard UI

### Task 12: Build the dashboard SPA — shell, routing, CSS

**Files:**
- Rewrite: `contextgraph/api/console.py`

This is the largest task. The dashboard is a single Python file that generates inline HTML+JS+CSS. It replaces the existing `console.py`.

- [ ] **Step 1: Write the dashboard shell**

Rewrite `contextgraph/api/console.py` with:
- Login/logout flow (reuse existing cookie-based auth)
- Dark theme CSS (full design system from spec section 5.4)
- Icon sidebar with hash routing (`#graph`, `#feed`, `#claims`, `#agents`, `#settings`)
- JS router that shows/hides page sections
- API helper functions (`fetchJSON`, `postJSON`, `patchJSON`, `deleteJSON`)
- Slide-out detail panel component

The file will be large (~800-1000 lines) since it contains HTML+CSS+JS inline. This is intentional — ships with `pip install` with zero frontend build.

- [ ] **Step 2: Test login/logout manually**

Run: `contextgraph-server` and open `http://localhost:8420/console`
Expected: Dark login page, paste API key, see dashboard shell with sidebar

- [ ] **Step 3: Commit**

```bash
git add contextgraph/api/console.py
git commit -m "feat: dashboard shell with dark theme, icon sidebar, hash routing"
```

### Task 13: Dashboard — Graph Explorer page

- [ ] **Step 1: Add graph visualization**

Add to console.py the `#graph` page with:
- Canvas-based force-directed graph renderer (~200 lines JS)
- Nodes = entities from `GET /v1/claims` (deduplicated)
- Edges = claims connecting entities
- Node size = connection count
- Node color = hash of source agent ID
- Glow effect with radial gradients
- Click node → slide-out panel with entity details + related claims
- Zoom (scroll wheel), pan (drag background), drag nodes

- [ ] **Step 2: Test manually**

Store some memories via API, open `#graph` page.
Expected: Interactive graph with glowing nodes, clickable.

- [ ] **Step 3: Commit**

```bash
git add contextgraph/api/console.py
git commit -m "feat: dashboard graph explorer with force-directed canvas visualization"
```

### Task 14: Dashboard — Knowledge Feed page

- [ ] **Step 1: Add feed page**

Add to console.py the `#feed` page with:
- Card grid from `GET /v1/feed`
- Each card: visibility badge, claim preview (first claim statement), source agent + reputation, entity tags, price
- Filter tabs: All / Following / Published / My Memories
- Search bar
- Click card → slide-out panel with full memory content + claims list

- [ ] **Step 2: Test manually**

Follow an agent, store memories, check feed.
Expected: Cards appear, click opens detail panel with full memory.

- [ ] **Step 3: Commit**

```bash
git add contextgraph/api/console.py
git commit -m "feat: dashboard knowledge feed page with card grid and detail panel"
```

### Task 15: Dashboard — Claims management page

- [ ] **Step 1: Add claims page**

Add to console.py the `#claims` page with:
- Card grid from `GET /v1/claims`
- Each card: visibility badge, statement, source agent, price, entity tags
- Filter tabs: All / Published / Private / Org / Shared
- Click card → slide-out panel with:
  - Full memory content
  - Visibility dropdown (only for own claims)
  - Price input (only for own claims)
  - Access list editor (only for SHARED visibility)
  - Save button → `PATCH /v1/claims/{id}`
  - Delete button (future — not in v0.2 scope)

- [ ] **Step 2: Test manually**

Store memories, open claims page, edit visibility.
Expected: Dropdown changes visibility, save persists.

- [ ] **Step 3: Commit**

```bash
git add contextgraph/api/console.py
git commit -m "feat: dashboard claims management with inline visibility and price editing"
```

### Task 16: Dashboard — Agents page

- [ ] **Step 1: Add agents page**

Add to console.py the `#agents` page with:
- Agent cards from `GET /v1/agents`
- Each card: name, org, capabilities tags, reputation score bar, followers count, claim count
- Follow/unfollow button → `POST /v1/follow` / `DELETE /v1/follow/{id}`
- Click → agent profile slide-out with trust details from `GET /v1/agents/{id}/trust`

- [ ] **Step 2: Test manually**

Register multiple agents, follow one, check counts.
Expected: Follow button works, follower count updates.

- [ ] **Step 3: Commit**

```bash
git add contextgraph/api/console.py
git commit -m "feat: dashboard agents page with trust scores and follow/unfollow"
```

### Task 17: Dashboard — Settings page

- [ ] **Step 1: Add settings page**

Add to console.py the `#settings` page with:
- Org summary from `GET /v1/operator/summary`
- Health status from `GET /health`
- Stats cards: claim count, agent count, pending reviews, expired claims
- Payment settings display (currency, default price)
- Federation status
- API key display (masked with copy button)
- Run Claim Expiry Sweep button

- [ ] **Step 2: Test manually**

Open settings page.
Expected: Stats display correctly, expiry sweep works.

- [ ] **Step 3: Commit**

```bash
git add contextgraph/api/console.py
git commit -m "feat: dashboard settings page with org summary and health status"
```

---

## Chunk 5: Final Integration & Verification

### Task 18: Run full test suite and lint

- [ ] **Step 1: Run all tests**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All pass (100+ tests)

- [ ] **Step 2: Run lint**

Run: `ruff check contextgraph/ sdk/ tests/ && ruff format --check contextgraph/ sdk/ tests/`
Expected: Clean

- [ ] **Step 3: Fix any failures**

If any tests fail or lint errors exist, fix them.

- [ ] **Step 4: Commit fixes**

```bash
git add -A
git commit -m "fix: resolve test and lint issues from knowledge sharing integration"
```

### Task 19: Push to GitHub

- [ ] **Step 1: Push**

```bash
git push origin main
```

- [ ] **Step 2: Verify CI passes**

Check GitHub Actions for green CI.

---

## Summary

| Chunk | Tasks | What it delivers |
|-------|-------|-----------------|
| 1 | 1-4 | Data models + repository layer for subscriptions |
| 2 | 5-9 | Service layer: reputation, follow, feed, recall update, claim edit |
| 3 | 10-11 | API routes and schemas for all new endpoints |
| 4 | 12-17 | Full dark-mode dashboard SPA (5 pages) |
| 5 | 18-19 | Integration testing, lint, push |
