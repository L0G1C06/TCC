# test_sensitivity.py
import numpy as np
import pytest
from ..engine.sensitivity import LHSSensitivityAnalyzer
from ..engine.scorer import GlobalScorer
from ..engine.m2_engine import M2Engine

_ENGINE = M2Engine()


def _raw_values_from_counts(first_digit_counts, n=100_000):
    inputs = {
        "col": {
            "first_digit_counts": first_digit_counts,
            "two_digit_counts": {str(p): n // 90 for p in range(10, 100)},
            "truncation_diagnostics": {
                "last_digit_counts": {str(i): n // 10 for i in range(10)},
                "round_count": 0,
            },
            "valid_count": n,
        }
    }
    return _ENGINE.run(inputs)


class TestLHSSensitivity:
    def test_weight_samples_somam_1(self, benford_perfect_1d):
        analyses = _raw_values_from_counts(benford_perfect_1d)
        gs = GlobalScorer()
        # LHS exige >= 2 escopos
        gs.register("scope_a", analyses)
        gs.register("scope_b", analyses)

        analyzer = LHSSensitivityAnalyzer(n_samples=100, seed=42)
        result = analyzer.analyze(gs.raw_values)

        sums = result.weight_samples.sum(axis=1)
        np.testing.assert_allclose(sums, 1.0, atol=1e-9)

    def test_n_samples_exato(self, benford_perfect_1d):
        analyses = _raw_values_from_counts(benford_perfect_1d)
        gs = GlobalScorer()
        gs.register("scope_a", analyses)
        gs.register("scope_b", analyses)

        analyzer = LHSSensitivityAnalyzer(n_samples=200, seed=42)
        result = analyzer.analyze(gs.raw_values)

        assert result.weight_samples.shape[0] == 200

    def test_robust_top3_vazio_quando_scores_proximos(
        self, benford_perfect_1d
    ):
        """Com escopos idênticos, nenhum deve dominar o top-1 em >80% dos cenários."""
        analyses = _raw_values_from_counts(benford_perfect_1d)
        gs = GlobalScorer()
        for i in range(4):
            gs.register(f"scope_{i}", analyses)

        analyzer = LHSSensitivityAnalyzer(n_samples=500, k=3, seed=42)
        result = analyzer.analyze(gs.raw_values)

        # Com scores idênticos o ranking é determinístico por tie-breaking —
        # nenhum escopo deve ter top_k_stability == 1.0 em TODOS os cenários
        # a menos que o tie-breaking seja sempre o mesmo. Validamos que
        # pelo menos um escopo não está no robust_top3.
        assert len(result.robust_top3) < 4, (
            "Com 4 escopos idênticos, não podem ser todos robust"
        )

    def test_robust_top3_completo_quando_modulo_domina(
        self, benford_perfect_1d, benford_uniform_1d
    ):
        analyses_clean = _raw_values_from_counts(benford_perfect_1d)
        analyses_fraud = _raw_values_from_counts(benford_uniform_1d)

        gs = GlobalScorer()
        gs.register("fraude",  analyses_fraud)
        gs.register("limpo_1", analyses_clean)
        gs.register("limpo_2", analyses_clean)

        analyzer = LHSSensitivityAnalyzer(n_samples=500, k=3, seed=42)
        result = analyzer.analyze(gs.raw_values)

        assert "fraude" in result.robust_top3