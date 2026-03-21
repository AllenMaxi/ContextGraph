# Pilot Checklist

Use this for every new design partner or serious beta user.

## Before the Pilot

- confirm the workflow is support or research adjacent
- confirm they already have multiple agents or cooperating automations
- confirm they are comfortable with self-hosted or guided deployment
- confirm they do not expect a full runtime-hosting platform from this repo

## Technical Setup

- deploy with Neo4j, not in-memory
- set `CG_ADMIN_KEY`
- confirm API access and dashboard login
- register initial agents
- store initial memories
- configure at least one follow relationship
- verify recall works on the shared memory path
- verify operator can inspect trust/activity

## Product Validation

- identify one high-value memory-sharing workflow
- define what “success” means in that workflow
- define what would make the pilot fail
- capture who will use the dashboard vs API/SDK vs CLI

## During the Pilot

- review stored memory quality weekly
- review what was recalled and reused
- monitor whether follow/discovery is actually useful
- track governance pain points
- track missing operational requirements

## After 30 Days

- did they keep using it without prompting?
- did it reduce duplicated memory work?
- did provenance/trust change operator behavior?
- would they pay for managed hosting/support?
- what blocked wider rollout?
