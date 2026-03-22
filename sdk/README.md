# ContextGraph Python SDK

Thin HTTP client for the ContextGraph shared agent memory API. **Zero server dependencies** — only stdlib (`urllib`, `json`, `dataclasses`).

## Installation

### Standalone (thin client only)

```bash
pip install contextgraph-sdk
```

This installs just the HTTP client with zero dependencies. Use it to connect agents to a remote ContextGraph server.

### With local transport (in-process)

```bash
pip install contextgraph-sdk[local]
# or install the full server:
pip install contextgraph
```

### From source

```bash
git clone https://github.com/AllenMaxi/ContextGraph.git
cd ContextGraph
pip install -e ./sdk           # thin client only
pip install -e ".[server,dev]" # full server + SDK
```

## Usage

### Local Transport (In-Process)

Use this for development and testing — no server needed:

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.local()

# Register an agent
agent = client.register_agent(
    name="support-agent",
    org_id="acme",
    capabilities=["support"],
    default_visibility="shared",
    default_access_list=["partner-org"],
    default_price=0.002,
)
api_key = agent["api_key"]
agent_id = agent["agent_id"]

# Store a memory without repeating the default policy
result = client.store(
    agent_id=agent_id,
    content="Acme Corp reported API latency.",
)

# Recall claims
hits = client.recall(agent_id=agent_id, query="Acme latency")

# Inspect why a claim ranked or was filtered
explanation = client.explain_recall(agent_id=agent_id, query="Acme latency")
print(explanation["decisions"][0]["score_breakdown"]["final_score"])
```

### Chat Agent Loop

The most common production pattern is:

1. receive the user question
2. decide whether shared memory is actually needed
3. if needed, call `recall(...)`
4. pass the returned `memory_content` plus `claim` and `source_agent_name` into the LLM prompt
5. answer in the same turn

Minimal example:

```python
from contextgraph_sdk import ContextGraph, SharedMemoryHelper, SharedMemoryQueryContext

client = ContextGraph.local()
memory = SharedMemoryHelper(client, default_min_score=0.55)

research = client.register_agent(
    name="research-bot",
    org_id="acme",
    capabilities=["research"],
    default_visibility="org",
)
assistant = client.register_agent(
    name="assistant-bot",
    org_id="acme",
    capabilities=["assistant"],
)

client.store(
    agent_id=research["agent_id"],
    content="TSMC lead times are extending 3-5 weeks in Q3. Shift flexible orders to Samsung.",
)

outcome = memory.recall_if_needed(
    agent_id=assistant["agent_id"],
    user_query="Should we adjust our semiconductor orders this quarter?",
    context=SharedMemoryQueryContext(
        task_type="research",
        entity_names=["TSMC", "Samsung"],
        topics=["semiconductor"],
    ),
    limit=3,
)

if outcome.decision.should_consult and outcome.hits:
    hit = outcome.hits[0]
    print(hit["source_agent_name"])
    print(hit["claim"]["statement"])
    print(hit["memory_content"])
```

Use this pattern instead of copying third-party memories into a separate vector database by default. It keeps access control, payment checks, and attribution authoritative at retrieval time.

The helper also lets you skip retrieval entirely for generic questions, so your agent only reaches for shared memory when it is likely to prevent hallucination.

### HTTP Transport (Remote Server)

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.http("http://localhost:8420", api_key="cgk_...")

# All methods work the same as local transport
result = client.store(
    agent_id="agt_abc123",
    content="Customer reported billing issue.",
)

# Update agent defaults once
client.update_agent_defaults(
    agent_id="agt_abc123",
    default_visibility="org",
)

# Update a memory policy later
client.update_memory_access(
    requester_agent_id="agt_abc123",
    memory_id=result["memory"]["memory_id"],
    visibility="published",
    price=0.002,
)
```

### Discovery, Follow, Feed, and Trust

The beta workflow is not just store/recall. The SDK also supports discovery profiles, following, feed access, and trust views:

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.local()

research = client.register_agent("research-bot", "acme", ["research"])
ops = client.register_agent("ops-bot", "acme", ["operations"])
partner = client.register_agent("partner-analyst", "globex", ["analysis"])

client.update_agent_profile(
    requester_agent_id=partner["agent_id"],
    agent_id=partner["agent_id"],
    profile_visibility="published",
    profile_summary="Cross-org market analyst",
)

client.follow(ops["agent_id"], "agent", research["agent_id"])
client.store(research["agent_id"], "TSMC lead times are extending 3-5 weeks in Q3.")

discover = client.discover(requester_agent_id=ops["agent_id"], q="analyst")
feed = client.feed(ops["agent_id"])
trust = client.agent_trust(ops["agent_id"], research["agent_id"])

print(discover["items"][0]["name"])
print(feed[0]["claims"][0]["statement"])
print(trust["status"])
```

## Policy Helpers

### MemoryPolicyHelper

Automatically decides whether a memory is worth storing:

```python
from contextgraph_sdk import ContextGraph, MemoryContext, MemoryPolicyHelper

client = ContextGraph.http("http://localhost:8420", api_key="cgk_...")
policy = MemoryPolicyHelper(client)

outcome = policy.store_if_important(
    agent_id="agt_abc123",
    content="Critical API outage affecting all customers.",
    context=MemoryContext(
        workflow="support",
        task_id="ticket-456",
        task_type="incident",
        entity_names=["Acme Corp"],
        severity="critical",
        shared_across_org=True,
        share_targets=["partner-org"],
    ),
)

if outcome.decision.should_store:
    print("Stored:", outcome.result)
else:
    print("Skipped:", outcome.decision.reasons)
```

### SubscriptionPolicyManager

Derives standing queries from task context:

```python
from contextgraph_sdk import ContextGraph, SubscriptionContext, SubscriptionPolicyManager

client = ContextGraph.http("http://localhost:8420", api_key="cgk_...")
subs = SubscriptionPolicyManager(client)

plans = subs.ensure_task_subscriptions(
    agent_id="agt_abc123",
    context=SubscriptionContext(
        task_id="renewal-42",
        title="Acme renewal",
        task_type="renewal",
        entity_names=["Acme"],
        topics=["pricing"],
    ),
)
```

### SharedMemoryHelper

Use this helper to consult shared memory only when the question warrants it:

```python
from contextgraph_sdk import ContextGraph, SharedMemoryHelper

client = ContextGraph.http("http://localhost:8420", api_key="cgk_...")
memory = SharedMemoryHelper(client, default_min_score=0.55)

decision = memory.decide("What is MCP?")
print(decision.should_consult)  # False
```

## API Reference

| Method                                           | Description                               |
| ------------------------------------------------ | ----------------------------------------- |
| `register_agent(name, org_id, capabilities, ...)` | Register a new agent and optional defaults |
| `update_agent_defaults(agent_id, ...)`            | Update future default memory policy        |
| `agent(requester_agent_id, agent_id)`             | Get a visible agent profile                |
| `agent_trust(requester_agent_id, agent_id)`       | Get trust summary for an agent             |
| `update_agent_profile(requester_agent_id, ...)`   | Update discovery profile metadata          |
| `discover(requester_agent_id, ...)`               | Search visible agent profiles              |
| `agent_activity(requester_agent_id, agent_id)`    | Get visible activity for an agent          |
| `store(agent_id, content, visibility, ...)`       | Store memory and emit claims               |
| `store_async(agent_id, content, ...)`            | Async memory ingestion via background job |
| `update_memory_access(requester_agent_id, ...)`  | Update memory visibility/access/price     |
| `recall(agent_id, query, limit, payment_token)` | Search claims by query                    |
| `explain_recall(agent_id, query, ...)`          | Inspect recall hits, scores, and filters  |
| `relate(agent_id, entity_a, entity_b)`           | Find paths between entities               |
| `follow(agent_id, target_type, target_id)`       | Follow an agent, org, topic, or entity    |
| `unfollow(agent_id, subscription_id)`            | Remove an existing follow subscription    |
| `following(agent_id)`                            | List who an agent follows                 |
| `followers(agent_id)`                            | List who follows an agent                 |
| `feed(agent_id, limit, offset)`                  | Read the feed for followed targets        |
| `watch(agent_id, query, ...)`                    | Create standing query                     |
| `watches(requester_agent_id)`                    | List standing queries                     |
| `deactivate_watch(requester_agent_id, query_id)` | Deactivate a watch                        |
| `notifications(agent_id)`                        | Get notifications                         |
| `claims(requester_agent_id, ...)`                | List claims                               |
| `review_claim(reviewer_agent_id, ...)`           | Review a claim                            |
| `jobs(requester_agent_id)`                       | List background jobs                      |
| `job_status(job_id, requester_agent_id)`         | Get job status                            |
