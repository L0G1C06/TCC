# test_scorer.py
import pytest
from ..engine.scorer import M4Scorer, GlobalScorer
from ..engine.m2_engine import M2Engine

_ENGINE = M2Engine()

def _make_inputs(first_digit_counts, n=100_000):
    return {
        "first_digit_counts": first_digit_counts,
        "two_digit_counts": {str(p): n // 90 for p in range(10, 100)},
        "truncation_diagnostics": {
            "last_digit_counts": {str(i): n // 10 for i in range(10)},
            "round_count": 0,
        },
        "valid_count": n,
    }


class TestM4Scorer:
    def test_score_maior_em_dado_fraudado(
        self, benford_perfect_1d, benford_uniform_1d
    ):
        analyses_clean = _ENGINE.run({"col": _make_inputs(benford_perfect_1d)})
        analyses_fraud = _ENGINE.run({"col": _make_inputs(benford_uniform_1d)})

        # score_module retorna dict[str, ColumnScore]
        scores_clean = M4Scorer().score_module(analyses_clean)
        scores_fraud = M4Scorer().score_module(analyses_fraud)

        assert scores_fraud["col"].score >= scores_clean["col"].score

    def test_score_entre_0_e_1(self, benford_perfect_1d):
        analyses = _ENGINE.run({"col": _make_inputs(benford_perfect_1d)})
        scores = M4Scorer().score_module(analyses)
        assert 0.0 <= scores["col"].score <= 1.0


class TestGlobalScorer:
    def test_scores_distintos_para_escalas_diferentes(
        self, benford_perfect_1d, benford_uniform_1d
    ):
        gs = GlobalScorer()
        gs.register("limpo",  _ENGINE.run({"col": _make_inputs(benford_perfect_1d)}))
        gs.register("fraude", _ENGINE.run({"col": _make_inputs(benford_uniform_1d)}))

        # score_all retorna dict[str, dict[str, ColumnScore]]
        all_scores = gs.score_all()

        score_limpo  = all_scores["limpo"]["col"].score
        score_fraude = all_scores["fraude"]["col"].score

        assert score_fraude > score_limpo, (
            f"GlobalScorer deve rankear fraude acima de limpo: "
            f"fraude={score_fraude:.4f}, limpo={score_limpo:.4f}"
        )

    def test_concordancia_de_ranking_com_m4scorer(
            self, benford_perfect_1d, benford_uniform_1d
    ):
        """GlobalScorer diferencia fraude de limpo; M4Scorer requer múltiplas colunas."""
        analyses_a = _ENGINE.run({"col": _make_inputs(benford_perfect_1d)})
        analyses_b = _ENGINE.run({"col": _make_inputs(benford_uniform_1d)})

        # M4Scorer com múltiplas colunas no mesmo módulo — aí a normalização tem sentido
        analyses_mixed = _ENGINE.run({
            "limpo": _make_inputs(benford_perfect_1d),
            "fraude": _make_inputs(benford_uniform_1d),
        })
        scores_mixed = M4Scorer().score_module(analyses_mixed)
        assert scores_mixed["fraude"].score > scores_mixed["limpo"].score, (
            "M4Scorer: fraude deve > limpo quando ambos estão no mesmo módulo"
        )

        # GlobalScorer — normalização cross-módulo, 1 coluna por escopo funciona
        gs = GlobalScorer()
        gs.register("limpo", analyses_a)
        gs.register("fraude", analyses_b)
        all_scores = gs.score_all()
        assert all_scores["fraude"]["col"].score > all_scores["limpo"]["col"].score, (
            "GlobalScorer: fraude deve > limpo"
        )