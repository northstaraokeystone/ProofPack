"""Tests for confidence-gated web fallback module.

Validates CRAG flow: evaluate, correct, merge.
"""
from unittest.mock import patch
from io import StringIO


class TestFallbackEvaluate:
    """Tests for confidence evaluation."""

    def test_high_confidence_correct(self):
        """Test high confidence is classified as CORRECT."""
        from fallback.evaluate import score, Classification

        synthesis = {
            "supporting_evidence": [
                {"chunk_id": "c1", "confidence": 0.95},
                {"chunk_id": "c2", "confidence": 0.90},
            ],
            "evidence_count": 10,
            "strength": 0.9,
            "coverage": 0.85,
        }

        with patch('sys.stdout', new=StringIO()):
            classification, confidence = score(synthesis, "test query")

        assert classification == Classification.CORRECT
        assert confidence > 0.8

    def test_medium_confidence_ambiguous(self):
        """Test medium confidence is classified as AMBIGUOUS."""
        from fallback.evaluate import score, Classification

        synthesis = {
            "supporting_evidence": [
                {"chunk_id": "c1", "confidence": 0.6},
            ],
            "evidence_count": 3,
            "strength": 0.6,
            "coverage": 0.5,
        }

        with patch('sys.stdout', new=StringIO()):
            classification, confidence = score(synthesis, "test query")

        assert classification == Classification.AMBIGUOUS
        assert 0.5 <= confidence < 0.8

    def test_low_confidence_incorrect(self):
        """Test low confidence is classified as INCORRECT."""
        from fallback.evaluate import score, Classification

        synthesis = {
            "supporting_evidence": [],
            "evidence_count": 0,
            "strength": 0.1,
            "coverage": 0.1,
            "gaps": ["no_evidence", "low_coverage", "query_mismatch"]
        }

        with patch('sys.stdout', new=StringIO()):
            classification, confidence = score(synthesis, "test query")

        assert classification == Classification.INCORRECT
        assert confidence < 0.5

    def test_should_fallback(self):
        """Test should_fallback convenience function."""
        from fallback.evaluate import should_fallback

        high_confidence = {
            "supporting_evidence": [{"chunk_id": "c1", "confidence": 0.95}],
            "evidence_count": 10,
        }

        low_confidence = {
            "supporting_evidence": [],
            "evidence_count": 0,
        }

        with patch('sys.stdout', new=StringIO()):
            assert should_fallback(low_confidence) is True
            assert should_fallback(high_confidence) is False


class TestFallbackCorrect:
    """Tests for correction strategies."""

    def test_reformulate_query(self):
        """Test query reformulation."""
        from fallback.correct import reformulate

        with patch('sys.stdout', new=StringIO()):
            reformulations = reformulate("What is the error cause?")

        assert len(reformulations) > 0
        assert "What is the error cause?" in reformulations  # Original included

    def test_decompose_complex_query(self):
        """Test query decomposition."""
        from fallback.correct import decompose

        with patch('sys.stdout', new=StringIO()):
            sub_queries = decompose("Find the error and fix it")

        # Should be decomposed on "and"
        assert len(sub_queries) >= 1

    def test_web_search_mock(self):
        """Test web search with mock provider."""
        from fallback.correct import with_web

        with patch('sys.stdout', new=StringIO()):
            result = with_web(
                "test query",
                max_results=3,
                provider="mock"
            )

        assert result.strategy == "web_search"
        assert len(result.web_results) > 0
        assert result.elapsed_ms > 0


class TestFallbackWeb:
    """Tests for web search integration."""

    def test_mock_search(self):
        """Test mock search provider."""
        from fallback.web import search

        with patch('sys.stdout', new=StringIO()):
            results = search("test query", max_results=3, provider="mock")

        assert len(results) == 3
        assert all(r.url.startswith("https://") for r in results)

    def test_available_providers(self):
        """Test listing available providers."""
        from fallback.web import get_available_providers

        providers = get_available_providers()

        assert "mock" in providers  # Mock always available


class TestFallbackMerge:
    """Tests for result merging."""

    def test_augment_strategy(self):
        """Test AUGMENT merge strategy."""
        from fallback.merge import combine, MergeStrategy
        from fallback.web import WebResult

        synthesis = {
            "executive_summary": "Internal summary",
            "supporting_evidence": [{"chunk_id": "c1", "confidence": 0.7}]
        }

        web_results = [
            WebResult(
                url="https://example.com/1",
                title="Web Result 1",
                snippet="Snippet 1",
                relevance_score=0.9
            )
        ]

        with patch('sys.stdout', new=StringIO()):
            result = combine(
                synthesis,
                web_results,
                strategy=MergeStrategy.AUGMENT,
                confidence_before=0.6
            )

        assert "Internal" in result.merged_content
        assert "Web" in result.merged_content
        assert result.confidence_after > result.confidence_before

    def test_replace_strategy(self):
        """Test REPLACE merge strategy."""
        from fallback.merge import combine, MergeStrategy
        from fallback.web import WebResult

        synthesis = {"executive_summary": "Low quality internal"}

        web_results = [
            WebResult(
                url="https://example.com/1",
                title="Good Web Result",
                snippet="High quality content",
                relevance_score=0.95
            )
        ]

        with patch('sys.stdout', new=StringIO()):
            result = combine(
                synthesis,
                web_results,
                strategy=MergeStrategy.REPLACE,
                confidence_before=0.3
            )

        # Replace strategy should have minimal internal content
        assert "replaced" in result.merged_content.lower()

    def test_strategy_selection(self):
        """Test automatic strategy selection."""
        from fallback.merge import select_strategy, MergeStrategy

        # High confidence -> AUGMENT
        strategy = select_strategy("CORRECT", 0.9, 5)
        assert strategy == MergeStrategy.AUGMENT

        # Very low confidence -> REPLACE
        strategy = select_strategy("INCORRECT", 0.2, 5)
        assert strategy == MergeStrategy.REPLACE

        # Medium with good web results -> INTERLEAVE
        strategy = select_strategy("AMBIGUOUS", 0.6, 5)
        assert strategy == MergeStrategy.INTERLEAVE


class TestCRAGFlow:
    """End-to-end CRAG flow tests."""

    def test_full_crag_flow(self):
        """Test complete CRAG: evaluate -> correct -> merge."""
        from fallback.evaluate import score, Classification
        from fallback.correct import with_web
        from fallback.merge import combine_with_auto_strategy

        # Start with low-confidence synthesis
        synthesis = {
            "executive_summary": "Incomplete analysis",
            "supporting_evidence": [{"chunk_id": "c1", "confidence": 0.4}],
            "evidence_count": 1,
        }

        with patch('sys.stdout', new=StringIO()):
            # Step 1: Evaluate
            classification, confidence = score(synthesis, "test query")

            # Step 2: Correct (if needed)
            if classification != Classification.CORRECT:
                correction = with_web("test query", provider="mock")

                # Step 3: Merge
                result = combine_with_auto_strategy(
                    synthesis,
                    correction.web_results,
                    classification.value,
                    confidence
                )

                # Confidence should improve
                assert result.confidence_after >= result.confidence_before
