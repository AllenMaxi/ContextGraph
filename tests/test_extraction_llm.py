"""Tests for contextgraph.extraction_llm (LLM-based extraction)."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch, MagicMock

from contextgraph.config import Settings
from contextgraph.extraction import RuleBasedExtractor
from contextgraph.extraction_llm import LLMExtractor, create_extractor


class TestCreateExtractorWithoutApiKey(unittest.TestCase):
    def test_create_extractor_without_api_key_returns_rule_based(self) -> None:
        s = Settings(llm_api_key="")
        extractor = create_extractor(s)
        self.assertIsInstance(extractor, RuleBasedExtractor)


class TestCreateExtractorWithApiKey(unittest.TestCase):
    def test_create_extractor_with_api_key_returns_llm_extractor(self) -> None:
        s = Settings(llm_api_key="sk-test-key-123")
        extractor = create_extractor(s)
        self.assertIsInstance(extractor, LLMExtractor)


class TestLLMExtractorFallsBackOnApiError(unittest.TestCase):
    def test_llm_extractor_falls_back_on_api_error(self) -> None:
        extractor = LLMExtractor(
            api_key="sk-test",
            model="claude-sonnet-4-6",
            base_url="https://api.anthropic.com",
        )
        # Mock urllib.request.urlopen to raise an error
        with patch("contextgraph.extraction_llm.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection refused")
            claims = extractor.extract("Alice works at Acme Corp")

        # Should fall back to rule-based and still return claims
        self.assertIsInstance(claims, list)
        self.assertGreater(len(claims), 0)
        # Verify the fallback produced reasonable output
        statements = [c.statement for c in claims]
        self.assertTrue(
            any("Alice" in s or "Acme" in s for s in statements),
            f"Expected entity mention in fallback claims, got: {statements}",
        )


class TestLLMExtractorParsesValidResponse(unittest.TestCase):
    def test_llm_extractor_parses_valid_response(self) -> None:
        extractor = LLMExtractor(
            api_key="sk-test",
            model="claude-sonnet-4-6",
            base_url="https://api.anthropic.com",
        )

        llm_json = {
            "entities": [
                {"name": "Alice", "type": "person", "aliases": []},
                {"name": "Acme Corp", "type": "company", "aliases": []},
            ],
            "claims": [
                {
                    "statement": "Alice works at Acme Corp",
                    "type": "relation",
                    "confidence": 0.9,
                    "entities": ["Alice", "Acme Corp"],
                    "relation_type": "works_at",
                },
            ],
        }

        api_response_body = json.dumps({
            "content": [
                {"type": "text", "text": json.dumps(llm_json)},
            ],
        }).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = api_response_body
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("contextgraph.extraction_llm.urllib.request.urlopen", return_value=mock_response):
            claims = extractor.extract("Alice works at Acme Corp")

        self.assertEqual(len(claims), 1)
        claim = claims[0]
        self.assertIn("Alice works at Acme Corp", claim.statement)
        self.assertEqual(claim.claim_type, "relationship")
        self.assertAlmostEqual(claim.confidence, 0.9)
        entity_names = [e.name for e in claim.entities]
        self.assertIn("Alice", entity_names)
        self.assertIn("Acme Corp", entity_names)
        # Verify entity types mapped correctly
        entity_types = {e.name: e.entity_type for e in claim.entities}
        self.assertEqual(entity_types["Alice"], "person")
        self.assertEqual(entity_types["Acme Corp"], "company")


if __name__ == "__main__":
    unittest.main()
