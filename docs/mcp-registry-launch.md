# MCP Registry Launch Guide

This repo is ready for GitHub promotion now, but it is not listed in the official MCP Registry yet.

## Current State

- `GitHub release`: ready
- `MCP server`: ready over `stdio`
- `Official MCP Registry listing`: not published

The current MCP server entry point is [`contextgraph/mcp_server.py`](../contextgraph/mcp_server.py). It is oriented around local `stdio` transport for MCP-aware agents and desktop clients.

## Recommended Path

For this project, the clean path is:

1. keep GitHub launch and community promotion first
2. add a public remote MCP endpoint second
3. submit the server to the official MCP Registry once the remote endpoint exists

That avoids PyPI pressure and keeps the launch focused on the real wedge: shared memory for MCP agents.

## Why It Is Not Listed Yet

The registry needs a publishable server surface. Today this repo has:

- local `stdio` MCP support
- HTTP REST API for ContextGraph itself

But it does not yet expose a public MCP `streamable-http` endpoint that can be listed directly in the registry.

## Minimum Registry Shape

When the remote endpoint exists, the listing can follow the registry schema with a payload like this:

```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "ai.contextgraph/memory-bus",
  "description": "Governed shared memory for MCP-compatible agents with provenance, review, and controlled visibility.",
  "repository": {
    "url": "https://github.com/AllenMaxi/ContextGraph",
    "source": "github"
  },
  "version": "0.4.0",
  "websiteUrl": "https://github.com/AllenMaxi/ContextGraph",
  "remotes": [
    {
      "type": "streamable-http",
      "url": "https://YOUR_DOMAIN/mcp"
    }
  ]
}
```

A committed template is available at [`registry/contextgraph.server.template.json`](../registry/contextgraph.server.template.json).

## What To Build Next

To move from "GitHub launch" to "Registry listing ready", build these in order:

1. A public MCP remote endpoint
   - recommended route: `POST/GET /mcp`
   - transport: `streamable-http`
2. Stable authentication model for remote clients
   - bearer token or API key header
3. Public deployment URL
4. Final registry metadata
5. Registry submission

## Practical Recommendation

Do not block promotion on the registry.

The right sequencing is:

1. promote the repo now
2. validate community interest
3. add the remote MCP transport
4. publish the registry listing once the endpoint is real

That keeps the launch honest and avoids claiming a distribution channel that is not yet active.
