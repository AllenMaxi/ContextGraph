from __future__ import annotations

import os
from dataclasses import dataclass


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


def _read_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


@dataclass(slots=True)
class Settings:
    host: str = os.getenv("CG_HOST", "0.0.0.0")
    port: int = _read_int("CG_PORT", 8420)
    debug: bool = _read_bool("CG_DEBUG", False)
    repository_backend: str = os.getenv("CG_REPOSITORY_BACKEND", "memory")
    neo4j_uri: str = os.getenv("CG_NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("CG_NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("CG_NEO4J_PASSWORD", "contextgraph")
    trust_threshold: float = _read_float("CG_TRUST_THRESHOLD", 0.65)
    default_claim_ttl_days: int = _read_int("CG_DEFAULT_CLAIM_TTL_DAYS", 30)
    enable_federation: bool = _read_bool("CG_ENABLE_FEDERATION", False)
    enable_background_worker: bool = _read_bool("CG_ENABLE_BACKGROUND_WORKER", False)
    background_worker_poll_seconds: float = _read_float("CG_BACKGROUND_WORKER_POLL_SECONDS", 0.1)
    webhook_timeout_seconds: float = _read_float("CG_WEBHOOK_TIMEOUT_SECONDS", 5.0)
    delivery_max_attempts: int = _read_int("CG_DELIVERY_MAX_ATTEMPTS", 3)
    delivery_retry_base_seconds: float = _read_float("CG_DELIVERY_RETRY_BASE_SECONDS", 0.5)
    enable_claim_expiry_sweeps: bool = _read_bool("CG_ENABLE_CLAIM_EXPIRY_SWEEPS", True)
    claim_expiry_sweep_seconds: float = _read_float("CG_CLAIM_EXPIRY_SWEEP_SECONDS", 30.0)
    admin_key: str = os.getenv("CG_ADMIN_KEY", "")
    cors_origins: str = os.getenv("CG_CORS_ORIGINS", "*")
    rate_limit_per_minute: int = _read_int("CG_RATE_LIMIT_PER_MINUTE", 60)
    # x402 Payments
    enable_payments: bool = _read_bool("CG_ENABLE_PAYMENTS", False)
    default_claim_price: float = _read_float("CG_DEFAULT_CLAIM_PRICE", 0.0)
    payment_currency: str = os.getenv("CG_PAYMENT_CURRENCY", "USDC")
    x402_verifier_url: str = os.getenv("CG_X402_VERIFIER_URL", "")
    # ERC-8004 Identity
    enable_identity_verification: bool = _read_bool("CG_ENABLE_IDENTITY", False)
    erc8004_registry_url: str = os.getenv("CG_ERC8004_REGISTRY_URL", "")
    # Federation & A2A
    federation_node_id: str = os.getenv("CG_FEDERATION_NODE_ID", "")
    federation_peers: str = os.getenv("CG_FEDERATION_PEERS", "")  # comma-separated URLs
    federation_key: str = os.getenv("CG_FEDERATION_KEY", "")
    enable_a2a: bool = _read_bool("CG_ENABLE_A2A", False)
    a2a_base_url: str = os.getenv("CG_A2A_BASE_URL", "")
    enable_remote_mcp: bool = _read_bool("CG_ENABLE_REMOTE_MCP", False)
    remote_mcp_path: str = os.getenv("CG_REMOTE_MCP_PATH", "/mcp")
    public_base_url: str = os.getenv("CG_PUBLIC_BASE_URL", "")
    # LLM Extraction
    llm_api_key: str = os.getenv("CG_LLM_API_KEY", "")
    llm_model: str = os.getenv("CG_LLM_MODEL", "claude-sonnet-4-6")
    llm_base_url: str = os.getenv("CG_LLM_BASE_URL", "https://api.anthropic.com")
    # AG-UI Streaming
    enable_streaming: bool = _read_bool("CG_ENABLE_STREAMING", True)
    streaming_heartbeat_seconds: float = _read_float("CG_STREAMING_HEARTBEAT_SECONDS", 30.0)
    # Quorum defaults
    default_quorum_high: int = _read_int("CG_DEFAULT_QUORUM_HIGH", 2)
    default_quorum_critical: int = _read_int("CG_DEFAULT_QUORUM_CRITICAL", 2)
    # UCP Commerce
    enable_ucp: bool = _read_bool("CG_ENABLE_UCP", False)
    # Dashboard
    enable_dashboard: bool = _read_bool("CG_ENABLE_DASHBOARD", True)
    # World Visualization
    enable_world: bool = _read_bool("CG_ENABLE_WORLD", False)
    world_max_viewers: int = _read_int("CG_WORLD_MAX_VIEWERS", 50)
    # Agent Lifecycle
    agent_idle_threshold_days: int = _read_int("CG_AGENT_IDLE_THRESHOLD_DAYS", 30)
    agent_idle_scan_interval_hours: int = _read_int("CG_AGENT_IDLE_SCAN_INTERVAL_HOURS", 24)
    # Skeptical Memory
    claim_staleness_threshold_days: int = _read_int("CG_CLAIM_STALENESS_THRESHOLD_DAYS", 14)
    # Memory Consolidation
    enable_memory_consolidation: bool = _read_bool("CG_ENABLE_MEMORY_CONSOLIDATION", False)
    memory_consolidation_interval_hours: int = _read_int("CG_MEMORY_CONSOLIDATION_INTERVAL_HOURS", 24)
    # Sentinel Pipeline
    sentinel_enabled: bool = _read_bool("CG_SENTINEL_ENABLED", True)
    sentinel_audit_depth: str = os.getenv("CG_SENTINEL_AUDIT_DEPTH", "auto")
    sentinel_bypass_reputation_threshold: float = _read_float("CG_SENTINEL_BYPASS_REPUTATION", 0.8)
    sentinel_new_agent_claim_threshold: int = _read_int("CG_SENTINEL_NEW_AGENT_CLAIMS", 5)
    sentinel_canary_interval_hours: int = _read_int("CG_SENTINEL_CANARY_INTERVAL_HOURS", 24)
    sentinel_post_store_timeout_seconds: int = _read_int("CG_SENTINEL_POST_STORE_TIMEOUT", 300)
    # Trust Promotion
    trust_promotion_enabled: bool = _read_bool("CG_TRUST_PROMOTION_ENABLED", True)
    trust_promotion_min_age_days: int = _read_int("CG_TRUST_PROMOTION_MIN_AGE_DAYS", 7)
    trust_promotion_min_attestations: int = _read_int("CG_TRUST_PROMOTION_MIN_ATTESTATIONS", 2)
    trust_promotion_scan_interval_hours: int = _read_int("CG_TRUST_PROMOTION_SCAN_INTERVAL_HOURS", 24)


settings = Settings()
