"""Tests for contextgraph.scoring (BM25Scorer)."""

from __future__ import annotations

import unittest

from contextgraph.scoring import BM25Scorer


class TestEmptyScorerReturnsZero(unittest.TestCase):
    def test_empty_scorer_returns_zero(self) -> None:
        scorer = BM25Scorer()
        # No documents indexed, scoring an unknown doc returns 0.
        self.assertEqual(scorer.score("nonexistent", "hello world"), 0.0)


class TestSingleDocumentScoresHigherForMatchingQuery(unittest.TestCase):
    def test_single_document_scores_higher_for_matching_query(self) -> None:
        scorer = BM25Scorer()
        scorer.add_document("d1", "the quick brown fox jumps over the lazy dog")
        matching_score = scorer.score("d1", "quick fox")
        non_matching_score = scorer.score("d1", "airplane submarine")
        self.assertGreater(matching_score, 0.0)
        self.assertEqual(non_matching_score, 0.0)


class TestAddAndRemoveDocument(unittest.TestCase):
    def test_add_and_remove_document(self) -> None:
        scorer = BM25Scorer()
        scorer.add_document("d1", "python programming language")
        self.assertTrue(scorer.has_document("d1"))
        self.assertGreater(scorer.score("d1", "python"), 0.0)

        scorer.remove_document("d1")
        self.assertFalse(scorer.has_document("d1"))
        self.assertEqual(scorer.score("d1", "python"), 0.0)

    def test_remove_nonexistent_is_noop(self) -> None:
        scorer = BM25Scorer()
        scorer.remove_document("no_such_doc")  # should not raise


class TestMultipleDocumentsRanking(unittest.TestCase):
    def test_multiple_documents_ranking(self) -> None:
        scorer = BM25Scorer()
        scorer.add_document("d1", "general news about the weather today")
        scorer.add_document("d2", "python programming language tutorial for beginners")
        scorer.add_document("d3", "cooking recipes for Italian pasta dishes")

        scores = {
            doc_id: scorer.score(doc_id, "python programming")
            for doc_id in ("d1", "d2", "d3")
        }
        # d2 should score highest since it matches the query best
        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        self.assertEqual(best, "d2")
        self.assertGreater(scores["d2"], scores["d1"])
        self.assertGreater(scores["d2"], scores["d3"])


class TestIncrementalUpdate(unittest.TestCase):
    def test_incremental_update(self) -> None:
        scorer = BM25Scorer()
        scorer.add_document("d1", "machine learning algorithms")
        score_before = scorer.score("d1", "machine learning")
        self.assertGreater(score_before, 0.0)

        # Add a second document; IDF and avgdl change, so d1's score may shift
        scorer.add_document("d2", "deep learning neural networks for machine vision")
        score_after = scorer.score("d1", "machine learning")
        self.assertGreater(score_after, 0.0)

        # d2 should also be scorable now
        score_d2 = scorer.score("d2", "machine learning")
        self.assertGreater(score_d2, 0.0)


class TestScoreTextWithoutIndex(unittest.TestCase):
    def test_score_text_without_index(self) -> None:
        scorer = BM25Scorer()
        # Corpus is empty, but score_text should still produce a non-zero score
        score = scorer.score_text("python", "python programming language tutorial")
        self.assertGreater(score, 0.0)

    def test_score_text_no_match_returns_zero(self) -> None:
        scorer = BM25Scorer()
        score = scorer.score_text("airplane", "python programming language")
        self.assertEqual(score, 0.0)

    def test_score_text_with_corpus(self) -> None:
        scorer = BM25Scorer()
        scorer.add_document("d1", "background document about science")
        # score_text uses corpus stats but doesn't add the text to the index
        score = scorer.score_text("cooking", "cooking Italian pasta recipes")
        self.assertGreater(score, 0.0)
        self.assertFalse(scorer.has_document("__tmp__"))  # not added


if __name__ == "__main__":
    unittest.main()
