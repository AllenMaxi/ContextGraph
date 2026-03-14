# ContextGraph Python SDK

Python client for the ContextGraph shared agent memory API.

## Installation

The SDK is included in the ContextGraph package:

```bash
pip install -e "."
```

For HTTP transport (connecting to a remote server), no extra dependencies are needed — the SDK uses Python's built-in `urllib`.

## Usage

### Local Transport (In-Process)

Use this for development and testing — no server needed:

```python
from sdk.contextgraph_sdk import ContextGraph

client = ContextGraph.local()

# Register an agent
agent = client.register_agent(
    name="support-agent",
    org_id="acme",
    capabilities=["support"],
)
api_key = agent["api_key"]
agent_id = agent["agent_id"]

# Store a memory
result = client.store(
    agent_id=agent_id,
    content="Acme Corp reported API latency.",
    visibility="shared",
    access_list=["partner-org"],
    price=0.002,
)

# Recall claims
hits = client.recall(agent_id=agent_id, query="Acme latency")
```

### HTTP Transport (Remote Server)

```python
from sdk.contextgraph_sdk import ContextGraph

client = ContextGraph.http("http://localhost:8420", api_key="cgk_...")

# All methods work the same as local transport
result = client.store(
    agent_id="agt_abc123",
    content="Customer reported billing issue.",
    visibility="shared",
)

# Update a memory policy later
client.update_memory_access(
    requester_agent_id="agt_abc123",
    memory_id=result["memory"]["memory_id"],
    visibility="published",
    price=0.002,
)
```

## Policy Helpers

### MemoryPolicyHelper

Automatically decides whether a memory is worth storing:

```python
from sdk.contextgraph_sdk import ContextGraph, MemoryContext, MemoryPolicyHelper

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
from sdk.contextgraph_sdk import ContextGraph, SubscriptionContext, SubscriptionPolicyManager

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

## API Reference

| Method                                           | Description                               |
| ------------------------------------------------ | ----------------------------------------- |
| `register_agent(name, org_id, capabilities)`     | Register a new agent                      |
| `store(agent_id, content, visibility, ...)`      | Store memory and emit claims              |
| `store_async(agent_id, content, ...)`            | Async memory ingestion via background job |
| `update_memory_access(requester_agent_id, ...)`  | Update memory visibility/access/price     |
| `recall(agent_id, query, limit)`                 | Search claims by query                    |
| `relate(agent_id, entity_a, entity_b)`           | Find paths between entities               |
| `watch(agent_id, query, ...)`                    | Create standing query                     |
| `watches(requester_agent_id)`                    | List standing queries                     |
| `deactivate_watch(requester_agent_id, query_id)` | Deactivate a watch                        |
| `notifications(agent_id)`                        | Get notifications                         |
| `claims(requester_agent_id, ...)`                | List claims                               |
| `review_claim(reviewer_agent_id, ...)`           | Review a claim                            |
| `jobs(requester_agent_id)`                       | List background jobs                      |
| `job_status(job_id, requester_agent_id)`         | Get job status                            |
