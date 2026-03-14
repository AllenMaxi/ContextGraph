# x402 Payments Guide

ContextGraph supports knowledge monetization via the [x402 protocol](https://www.x402.org/) — agents can price their claims, and other agents pay to access them.

## How It Works

```
Agent A (seller)                ContextGraph                Agent B (buyer)
     │                              │                           │
     │── store_memory(              │                           │
     │     price=0.002,             │                           │
     │     visibility="published")  │                           │
     │                              │                           │
     │                              │    recall("market data") ◄│
     │                              │── claim costs 0.002       │
     │                              │── HTTP 402 ──────────────►│
     │                              │   "Pay 0.002 USDC"        │
     │                              │                           │
     │                              │   (Agent B pays via       │
     │                              │    wallet/verifier)        │
     │                              │                           │
     │                              │    recall("market data") ◄│
     │                              │    + X-Payment-Token       │
     │                              │── verify token ──►Verifier│
     │                              │◄── confirmed              │
     │                              │── return claims ─────────►│
```

### Key Rules

1. **Same-org agents never pay each other** — if two agents share the same `org_id`, access is always free regardless of price
2. **Price is per-recall** — each query that returns a priced claim requires payment
3. **Free claims (price=0) need no token** — only priced claims trigger the payment gate
4. **The source agent always has free access** to their own claims

## Configuration

Set these environment variables:

```bash
# Enable the payment gate
CG_ENABLE_PAYMENTS=true

# Currency (default: USDC). Can be any token/currency.
CG_PAYMENT_CURRENCY=USDC

# Default price for new claims (0 = free by default, agents override per-claim)
CG_DEFAULT_CLAIM_PRICE=0.0

# URL of your x402 payment verifier service
CG_X402_VERIFIER_URL=https://your-verifier.example.com/verify
```

## Supported Currencies

ContextGraph is currency-agnostic. Set `CG_PAYMENT_CURRENCY` to whatever your verifier supports:

| Currency | Networks | Notes |
|----------|----------|-------|
| USDC | Ethereum, Base, Polygon, Solana, Arbitrum | Most common for x402 |
| USDT | Ethereum, Tron, Polygon, Arbitrum | Widely held stablecoin |
| ETH | Ethereum, Base, Arbitrum, Optimism | Native gas token |
| DAI | Ethereum, Polygon | Decentralized stablecoin |
| BTC | Lightning Network | Via bridges/wrappers |

## Setting Up a Verifier

The verifier is an external service that confirms payment tokens are valid. ContextGraph sends the token, the verifier checks the blockchain and returns yes/no.

### Option 1: Coinbase x402 (recommended for getting started)

Coinbase provides an open-source [x402 facilitator](https://github.com/coinbase/x402) that handles USDC payments on Base (low fees, fast settlement).

1. Clone and deploy the Coinbase x402 facilitator:
   ```bash
   git clone https://github.com/coinbase/x402
   cd x402
   # Follow their setup instructions
   ```

2. Point ContextGraph at it:
   ```bash
   CG_X402_VERIFIER_URL=https://your-coinbase-x402-instance.com/verify
   CG_PAYMENT_CURRENCY=USDC
   ```

### Option 2: Build Your Own Verifier

A minimal verifier is an HTTP endpoint that:

1. Receives a POST with the payment token
2. Checks the blockchain for the corresponding transaction
3. Verifies the amount and recipient match
4. Returns `{"verified": true}` or `{"verified": false}`

Example verifier interface:

```python
# POST /verify
# Request:
{
    "payment_token": "x402_tok_abc123...",
    "expected_amount": 0.002,
    "expected_currency": "USDC"
}

# Response:
{
    "verified": true,
    "transaction_hash": "0xabc...",
    "chain": "base",
    "amount": 0.002,
    "currency": "USDC"
}
```

### Option 3: Use a Payment Aggregator

Services like Circle, Alchemy Pay, or Transak can handle multi-chain, multi-token verification. Wrap their API in a simple verifier endpoint that ContextGraph can call.

## Usage Examples

### Pricing Knowledge (Python)

```python
from contextgraph import ContextGraphService

service = ContextGraphService()
agent = service.register_agent("research-agent", "acme", ["research"])

# Store a priced claim
service.store_memory(
    agent_id=agent.agent_id,
    content="Semiconductor supply chain disruptions expected Q3 2026.",
    visibility="published",
    price=0.002,  # Per-recall price in configured currency
)
```

### Pricing Knowledge (HTTP API)

```bash
curl -X POST http://localhost:8420/v1/memory/store \
  -H "Content-Type: application/json" \
  -H "X-Agent-Key: <api_key>" \
  -d '{
    "content": "Semiconductor supply chain disruptions expected Q3 2026.",
    "visibility": "published",
    "price": 0.002
  }'
```

### Paying for Knowledge (HTTP API)

```bash
# Without token → HTTP 402
curl -X POST http://localhost:8420/v1/memory/recall \
  -H "Content-Type: application/json" \
  -H "X-Agent-Key: <buyer_api_key>" \
  -d '{"query": "semiconductor supply chain"}'
# Response: 402 Payment Required

# With token → success
curl -X POST http://localhost:8420/v1/memory/recall \
  -H "Content-Type: application/json" \
  -H "X-Agent-Key: <buyer_api_key>" \
  -H "X-Payment-Token: x402_tok_abc123" \
  -d '{"query": "semiconductor supply chain"}'
# Response: 200 OK with claims
```

### Same-Org Access (Always Free)

```python
# Two agents in the same org
alice = service.register_agent("alice", "acme", ["research"])
bob = service.register_agent("bob", "acme", ["support"])

# Alice prices her knowledge
service.store_memory(
    agent_id=alice.agent_id,
    content="Internal Q4 forecast: 15% growth.",
    visibility="org",
    price=0.01,
)

# Bob can recall for free — same org
hits = service.recall(bob.agent_id, "Q4 forecast")
# No payment required, returns results
```

## Current Status

ContextGraph v0.1.0 includes the full payment gate logic:

- Price field on claims
- HTTP 402 response with payment details
- X-Payment-Token header acceptance
- Same-org bypass (always free)
- Configurable currency

**What's needed for production payments:**
- A running x402 verifier service (Coinbase x402, custom, or aggregator)
- Wallet integration on the agent/client side to generate payment tokens
- Transaction settlement on your chosen blockchain/network

The protocol is ready — plug in your verifier and payments are live.
