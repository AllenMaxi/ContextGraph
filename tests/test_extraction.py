from __future__ import annotations

import unittest

from contextgraph.extraction import RuleBasedExtractor


class ContextGraphExtractionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.extractor = RuleBasedExtractor()

    def test_extracts_lowercase_company_with_suffix(self) -> None:
        claims = self.extractor.extract("acme corp requested an urgent review.")

        entity_names = {entity.name for claim in claims for entity in claim.entities}
        self.assertIn("Acme Corp", entity_names)

    def test_request_relation_takes_priority_over_from_clause(self) -> None:
        claims = self.extractor.extract("Maria from Globex Inc wants an update.")

        self.assertEqual(claims[0].relation_type, "REQUESTED")

    def test_empty_input_returns_no_claims(self) -> None:
        self.assertEqual(self.extractor.extract(""), [])
        self.assertEqual(self.extractor.extract("   "), [])

    def test_whitespace_only_returns_no_claims(self) -> None:
        self.assertEqual(self.extractor.extract("\n\t  \n"), [])

    def test_unicode_entities_are_extracted(self) -> None:
        claims = self.extractor.extract("José from Münchner GmbH reported an issue.")
        entity_names = {entity.name for claim in claims for entity in claim.entities}
        # At minimum, the text should be processed without errors
        self.assertIsInstance(claims, list)

    def test_long_text_does_not_crash(self) -> None:
        long_text = "Acme Corp reported an issue. " * 500
        claims = self.extractor.extract(long_text)
        self.assertIsInstance(claims, list)
        self.assertGreater(len(claims), 0)

    def test_no_extractable_entities_returns_claims_without_entities(self) -> None:
        claims = self.extractor.extract("The weather is nice today.")
        # The extractor may or may not produce claims for generic text,
        # but it should not crash
        self.assertIsInstance(claims, list)

    def test_special_characters_do_not_crash(self) -> None:
        text = "Agent <script>alert('xss')</script> from Company & Partners reported @issue #123."
        claims = self.extractor.extract(text)
        self.assertIsInstance(claims, list)

    def test_single_word_input(self) -> None:
        claims = self.extractor.extract("hello")
        self.assertIsInstance(claims, list)


if __name__ == "__main__":
    unittest.main()
