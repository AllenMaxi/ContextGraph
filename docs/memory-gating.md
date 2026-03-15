# Memory Gating for Chat Agents

ContextGraph works best when agents use shared memory **only when it is likely to improve factual accuracy**.

The default production policy should be:

1. answer directly if the question is generic and does not depend on shared state
2. consult ContextGraph when the question is organizational, recent, proprietary, or clearly about another agent's knowledge
3. only use recalled memory if the result passes a minimum score threshold
4. if no result passes the threshold, do not hallucinate

## Good Reasons To Consult Shared Memory

- internal incidents, support cases, and latency questions
- pricing, renewals, vendors, and partner notes
- recent decisions made by another agent or team
- cross-org shared knowledge that the current agent is allowed to access
- situations where guessing would be worse than saying "I don't have reliable memory for that"

## Good Reasons Not To Consult Shared Memory

- general background questions such as "What is MCP?"
- writing tasks, brainstorming, summaries, and transformations
- questions already fully answered by the user's prompt
- tasks where shared memory would only add latency and noise

## Recommended Runtime Pattern

```text
User question
  -> Need-memory gate
  -> if no: answer directly
  -> if yes: recall from ContextGraph
      -> apply score threshold
      -> if strong hit: answer with attribution
      -> if weak/no hit: do not hallucinate
```

## SDK Helper

The SDK ships a helper for this pattern:

- [`SharedMemoryHelper`](../sdk/contextgraph_sdk/policies.py)
- runnable example: [`examples/chat_agent_sdk.py`](../examples/chat_agent_sdk.py)

The helper does two things:

- decides whether shared memory should be consulted
- filters weak hits below a configurable minimum score

## Why This Matters

Without a gate, shared memory becomes noisy.

Without a score threshold, weak hits can pollute the prompt.

With both in place, ContextGraph becomes a better fit for agentic systems:

- lower latency on generic turns
- less hallucination on organization-specific turns
- clearer attribution when memory is actually used
