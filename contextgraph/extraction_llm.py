"""LLM-powered entity and claim extraction using the Anthropic API.

Falls back to the rule-based :class:`RuleBasedExtractor` when no API key is
configured or when the LLM call fails for any reason.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from .config import Settings
from .extraction import (
    ExtractedClaim,
    ExtractedEntity,
    Extractor,
    RuleBasedExtractor,
    canonicalize_claim,
    canonicalize_statement,
)

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
You are an information-extraction engine.  Given the user text below, extract
all named entities and factual claims.  Return **only** valid JSON — no
markdown fences, no commentary.

Return exactly this structure:
{
  "entities": [
    {
      "name": "Canonical Name",
      "type": "person | company | product | location | concept",
      "aliases": []
    }
  ],
  "claims": [
    {
      "statement": "A single factual sentence.",
      "type": "attribute | relation | event",
      "confidence": 0.0,
      "entities": ["Entity Name 1", "Entity Name 2"],
      "relation_type": "reported | works_at | located_in | associated_with | requested | null"
    }
  ]
}

Rules:
- Every claim must reference at least one entity from the entities list.
- confidence is a float between 0.0 and 1.0.
- relation_type is null for attribute/event claims that have no clear relation.
- type for claims: use "relation" when two or more entities are linked,
  "attribute" for a fact about one entity, "event" for a time-bound occurrence.
- Do NOT invent information not present in the text.
- If the text contains no extractable entities or claims, return empty lists.
"""

# Map LLM claim types to the internal names used by the rule-based extractor.
_CLAIM_TYPE_MAP: dict[str, str] = {
    "attribute": "attribute",
    "relation": "relationship",
    "event": "event",
}

# Map LLM entity types to internal names.
_ENTITY_TYPE_MAP: dict[str, str] = {
    "person": "person",
    "company": "company",
    "product": "topic",
    "location": "topic",
    "concept": "topic",
}


class LLMExtractor:
    """Extract entities and claims by calling the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._fallback = RuleBasedExtractor()

    # ---- public interface (satisfies ``Extractor`` protocol) ----

    def extract(self, content: str) -> list[ExtractedClaim]:
        """Extract claims from *content* via an LLM call.

        Falls back to the rule-based extractor on any failure.
        """
        try:
            raw = self._call_llm(content)
            parsed = self._parse_response(raw)
            claims = self._build_claims(parsed)
            if claims:
                return claims
            logger.warning("LLM returned no claims; falling back to rule-based extractor")
        except Exception:
            logger.exception("LLM extraction failed; falling back to rule-based extractor")
        return self._fallback.extract(content)

    # ---- LLM interaction ----

    def _call_llm(self, text: str) -> dict[str, Any]:
        """Send *text* to the Anthropic Messages API and return parsed JSON."""
        url = f"{self._base_url}/v1/messages"

        payload = json.dumps(
            {
                "model": self._model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": text}],
                "system": _EXTRACTION_PROMPT,
            }
        ).encode()

        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())

        # The Messages API returns content as a list of blocks.
        text_block = self._extract_text_block(body)
        return self._safe_json_loads(text_block)

    # ---- response parsing helpers ----

    @staticmethod
    def _extract_text_block(body: dict[str, Any]) -> str:
        """Pull the first text block out of an Anthropic Messages response."""
        for block in body.get("content", []):
            if block.get("type") == "text":
                return block["text"]
        raise ValueError("No text block found in API response")

    @staticmethod
    def _safe_json_loads(text: str) -> dict[str, Any]:
        """Parse JSON, stripping optional markdown fences."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (optionally with language tag)
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3]
        return json.loads(cleaned.strip())

    # ---- mapping to internal dataclasses ----

    @staticmethod
    def _parse_response(raw: dict[str, Any]) -> dict[str, Any]:
        """Validate the top-level shape of the LLM output."""
        if not isinstance(raw.get("entities"), list):
            raw["entities"] = []
        if not isinstance(raw.get("claims"), list):
            raw["claims"] = []
        return raw

    def _build_claims(self, parsed: dict[str, Any]) -> list[ExtractedClaim]:
        """Convert parsed LLM JSON into ``ExtractedClaim`` instances."""
        entity_type_lookup: dict[str, str] = {}
        for ent in parsed["entities"]:
            name = str(ent.get("name", "")).strip()
            if name:
                raw_type = str(ent.get("type", "concept")).lower()
                entity_type_lookup[name] = _ENTITY_TYPE_MAP.get(raw_type, "topic")

        claims: list[ExtractedClaim] = []
        seen: set[tuple[str, str, str | None, tuple[str, ...]]] = set()

        for item in parsed["claims"]:
            statement = str(item.get("statement", "")).strip()
            if not statement:
                continue

            raw_type = str(item.get("type", "attribute")).lower()
            claim_type = _CLAIM_TYPE_MAP.get(raw_type, "attribute")

            confidence = self._clamp_confidence(item.get("confidence", 0.5))

            raw_relation = item.get("relation_type")
            relation_type: str | None = None
            if raw_relation and str(raw_relation).lower() not in ("null", "none", ""):
                relation_type = str(raw_relation).upper()

            entity_names: list[str] = []
            for e in item.get("entities", []):
                if isinstance(e, str) and e.strip():
                    entity_names.append(e.strip())

            entities = [
                ExtractedEntity(
                    name=name,
                    entity_type=entity_type_lookup.get(name, "topic"),
                )
                for name in entity_names
            ]

            claim = ExtractedClaim(
                statement=canonicalize_statement(statement),
                claim_type=claim_type,
                relation_type=relation_type,
                confidence=confidence,
                entities=entities,
            )

            sig = canonicalize_claim(claim)
            if sig in seen:
                continue
            seen.add(sig)
            claims.append(claim)

        return claims

    @staticmethod
    def _clamp_confidence(value: Any) -> float:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return 0.5
        return round(max(0.0, min(f, 1.0)), 2)


# ---- factory ----


def create_extractor(settings: Settings) -> Extractor:
    """Return the best available extractor based on *settings*.

    If an LLM API key is configured, returns an :class:`LLMExtractor`.
    Otherwise falls back to :class:`RuleBasedExtractor`.
    """
    if settings.llm_api_key:
        logger.info("Using LLM-based extractor (model=%s)", settings.llm_model)
        return LLMExtractor(  # type: ignore[return-value]
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
        )
    logger.info("No LLM API key configured; using rule-based extractor")
    return RuleBasedExtractor()
