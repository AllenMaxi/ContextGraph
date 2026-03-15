# MCP Chat Agent Integration

ContextGraph works best as a **shared memory bus for MCP-compatible agents**.

The recommended hot path is:

1. the user asks a question
2. the agent calls `contextgraph_recall`
3. ContextGraph returns authorized memories plus source metadata
4. the agent answers using that context in the same turn

That is different from a classic “copy everything into a vector DB” setup.

## Why This Pattern Wins

It keeps:

- access control authoritative at the source memory
- payment checks on the real unlock path
- attribution attached to each recalled memory
- memory freshness and review state in the retrieval loop

## MCP Server Entry Point

ContextGraph ships an MCP server entry point:

```bash
contextgraph-mcp
```

Equivalent module form:

```bash
python -m contextgraph.mcp_server
```

The MCP server exposes tools for:

- `contextgraph_store`
- `contextgraph_recall`
- `contextgraph_relate`
- `contextgraph_watch`
- `contextgraph_notifications`
- `contextgraph_review`

## Minimal MCP Setup

Set the agent identity for the MCP process:

```bash
export CG_AGENT_ID=agt_your_agent
export CG_AGENT_NAME=assistant-bot
export CG_AGENT_ORG=acme
python -m contextgraph.mcp_server
```

See the MCP intro and tool-model docs for the current protocol shape:

- [Model Context Protocol introduction](https://modelcontextprotocol.io/docs/getting-started/intro)
- [Anthropic MCP documentation](https://docs.anthropic.com/en/docs/mcp)

## SDK Pattern for Chat Agents

If you are embedding ContextGraph inside your own runtime instead of using MCP directly, the pattern is still the same:

```python
from sdk.contextgraph_sdk import ContextGraph

client = ContextGraph.http("http://localhost:8420", api_key="cgk_...")

def answer(agent_id: str, user_query: str) -> str:
    hits = client.recall(agent_id=agent_id, query=user_query, limit=3)
    context = "\n\n".join(
        f"Source: {hit['source_agent_name']}\n"
        f"Claim: {hit['claim']['statement']}\n"
        f"Memory: {hit['memory_content']}"
        for hit in hits
    )
    return f"Use this context in the LLM call:\n\n{context}"
```

A runnable local example is in [examples/chat_agent_sdk.py](/Users/maximilianoallende/Documents/promptUltra/examples/chat_agent_sdk.py).

## Recommended Production Pattern

- keep ContextGraph as the shared memory source of truth
- call `recall` at answer time
- cache short-lived results locally if latency requires it
- use `watch` and `feed` for proactive updates and prefetching
- do not ingest third-party memories into another persistent vector store by default

## What To Avoid

Avoid this default architecture:

- external agent shares a memory
- your agent copies that memory into its own vector DB
- later answers from the copied version without rechecking access or pricing

That breaks the strongest parts of ContextGraph:

- memory-level access policy
- locked paid discovery
- source attribution
- policy updates and revocation

