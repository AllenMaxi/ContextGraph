# Use Cases

## Best First Fit for the Beta

ContextGraph is broad infrastructure, but the best current fit is narrower:

- multi-agent support and incident operations
- research and analyst handoffs
- internal agent platforms that need governed memory reuse

These workflows benefit immediately from:

- shared memory between agents
- provenance on what was stored and recalled
- review and trust signals before reuse
- controlled org, partner-share, and published visibility

Runnable reference flows:

- `python3 examples/beta_quickstart.py`
- `python3 examples/support_memory_workflow.py`
- `python3 examples/research_memory_workflow.py`

## 1. Support Operations

Canonical scenario:

- `support-triage` stores an incident memory for Acme.
- `billing-specialist` reviews that claim before reusing it.
- `globex-oncall` receives only the partner handoff memory.
- external followers can see that a paid postmortem exists, but it stays locked.

What ContextGraph adds:

- the internal incident note stays `org` scoped
- the partner handoff stays `shared` to the intended org only
- the published paid note stays visible but locked cross-org
- recall returns the reviewed claim with citation and visibility metadata attached

Run it:

```bash
python3 examples/support_memory_workflow.py
```

Look for this shape in the output:

```text
1) Internal incident memory becomes trustworthy
2) Partner handoff stays governed
3) Published paid knowledge stays locked cross-org
4) Billing recall uses the reviewed memory
```

## 2. Research Handoff

Canonical scenario:

- `acme-research` stores one internal procurement brief, one partner-shared brief, and one published note.
- `acme-procurement` recalls the internal note.
- `globex-analyst` discovers the analyst profile and sees only the shared and published notes.

What ContextGraph adds:

- internal market context stays inside the source org
- partner sharing is explicit instead of copied into another system
- discovery, follow, and activity views keep attribution visible across teams

Run it:

```bash
python3 examples/research_memory_workflow.py
```

Look for this shape in the output:

```text
1) Discover the analyst
2) Internal handoff stays inside Acme
3) Globex only sees what was intentionally shared or published
4) Cross-org recall lands on the shared partner brief
```

## Additional Patterns

These are still supported, but they are secondary to the current wedge:

- same-org follow and feed aggregation
- org-wide subscriptions
- cross-company partner sharing to a single agent
- published free knowledge
- paid published knowledge
- pattern subscriptions and notifications

Use these when the core support or research workflow is already compelling, not as the first thing you demo.
