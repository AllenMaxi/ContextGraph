# ContextGraph Python SDK

Python client for the ContextGraph shared agent memory API.

## Installation

The SDK ships from this repository today. Install from source:

```bash
git clone https://github.com/AllenMaxi/ContextGraph.git
cd ContextGraph
pip install -e "."
```

For HTTP transport (connecting to a remote server), no extra dependencies are needed — the SDK uses Python's built-in `urllib`.

PyPI naming is still pending because `contextgraph` is already claimed by another project.

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
from sdk.contextgraph_sdk import ContextGraph, SharedMemoryHelper, SharedMemoryQueryContext

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
from sdk.contextgraph_sdk import ContextGraph

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

### SharedMemoryHelper

Use this helper to consult shared memory only when the question warrants it:

```python
from sdk.contextgraph_sdk import ContextGraph, SharedMemoryHelper

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
| `store(agent_id, content, visibility, ...)`       | Store memory and emit claims               |
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
