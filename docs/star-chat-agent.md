# Star Chat Agent Example

This is the example to show when you want to explain ContextGraph in one minute.

It demonstrates the product rule that matters most:

- answer directly when shared memory is unnecessary
- consult shared memory only when the question needs it
- attribute the answer to the memory source that supplied it

## Run It

```bash
python3 examples/star_chat_agent.py
```

## What It Shows

The example seeds three agents:

- `research-bot` in `acme`
- `assistant-bot` in `acme`
- `globex-lane-bot` in `globex`

Then it runs three user questions:

1. A general question that should not consult ContextGraph
2. A same-org question that should retrieve memory from `research-bot`
3. A cross-org question that should retrieve memory explicitly shared by `globex-lane-bot`

## Why This Example Matters

Most memory demos are either:

- always-on retrieval
- or isolated single-agent scratchpads

This example shows the wedge more clearly:

**ContextGraph helps an agent use another agent's memory in the same turn, but only when it is actually needed.**

That is the behavior we want for MCP-native agent systems:

- less hallucination
- less prompt noise
- stronger provenance
- cleaner trust boundaries
