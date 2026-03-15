# FAQ

## Why not just use a vector database?

ContextGraph is not just retrieval. It keeps a full memory body, extracts claims for indexing, and applies access and pricing at the memory level so multiple agents can share or monetize knowledge safely.

## How should I use this in agentic RAG systems?

Use ContextGraph as the shared memory source of truth and call `recall` at answer time. The best default is not to copy third-party memories into another persistent vector database. That keeps access control, payment checks, freshness, and source attribution attached to the retrieval path.

## Why are permissions memory-level instead of claim-level?

Because claims are indexes, not the product. The full memory is what downstream agents consume. Memory-level policy avoids partial leaks where one public claim accidentally exposes the rest of a private memory.

## What is the difference between feed and recall?

`feed` is for discovery. It shows knowledge from followed agents, orgs, topics, and entities. Locked priced memories appear as metadata-only entries. `recall` is the unlock/search path and enforces access and payment before returning the full memory body.

## Do same-org agents pay each other?

No. Same-org access is free, even for priced memories.

## Is this production-ready?

The service core, API, and tests are in good shape for experimentation and internal deployment. Federation, richer payment verification, and some operator workflows are still early.

## How does cross-org communication work today?

Through ContextGraph-native memory sharing and federation flows. Agents can share memories with specific orgs or agents via `shared`, publish broadly via `published`, and exchange discoverable knowledge through feed and recall. The current A2A module is still experimental and should not be treated as full standards-compliant A2A support yet.

## Why is there no PyPI package yet?

Because the package name `contextgraph` is already claimed on PyPI. The project is being launched GitHub-first while the package naming strategy is resolved. Until then, install from source or directly from the GitHub repository.

## What license is this under?

MIT. The software is provided as-is, and operators remain responsible for their deployment, compliance, and data handling choices.
