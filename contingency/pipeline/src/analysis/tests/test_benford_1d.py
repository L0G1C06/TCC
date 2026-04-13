import pytest
from ..metrics.benford_1d import MAD1d, JS1d, ZScore1d, Chi2_1d
from ..base import BenfordFlag


class TestMAD1d:
    def test_conforme_em_distribuicao_perfeita(self, benford_perfect_1d):
        result = MAD1d().compute(benford_perfect_1d)
        assert result.value < 0.006
        assert result.flag == BenfordFlag.CONFORME

    def test_critico_em_distribuicao_uniforme(self, benford_uniform_1d):
        result = MAD1d().compute(benford_uniform_1d)
        assert result.value > 0.015
        assert result.flag == BenfordFlag.CRITICO

    def test_p_value_e_none(self, benford_perfect_1d):
        result = MAD1d().compute(benford_perfect_1d)
        assert result.p_value is None


class TestJS1d:
    def test_conforme_em_distribuicao_perfeita(self, benford_perfect_1d):
        result = JS1d().compute(benford_perfect_1d)
        assert result.flag == BenfordFlag.CONFORME

    def test_critico_em_distribuicao_uniforme(self, benford_uniform_1d):
        result = JS1d().compute(benford_uniform_1d)
        assert result.flag == BenfordFlag.CRITICO

    def test_value_limitado_entre_0_e_1(self, benford_uniform_1d):
        result = JS1d().compute(benford_uniform_1d)
        assert 0.0 <= result.value <= 1.0


class TestZScore1d:
    def test_sinaliza_digito_correto_em_fraude(self, fraud_digit7_1d):
        result = ZScore1d().compute(fraud_digit7_1d)
        # detail deve conter z_scores com dígito 7 como o maior
        z_scores = result.detail.get("z_scores", {})
        assert z_scores, "detail deve conter z_scores"
        max_digit = max(z_scores, key=lambda d: abs(z_scores[d]))
        assert max_digit == "7", f"Esperava dígito 7, got {max_digit}"

    def test_value_e_z_max(self, fraud_digit7_1d):
        result = ZScore1d().compute(fraud_digit7_1d)
        z_scores = result.detail.get("z_scores", {})
        assert result.value == pytest.approx(max(abs(v) for v in z_scores.values()), rel=1e-6)

    def test_gate_suprime_flag_quando_mad_e_js_conformes(self, benford_perfect_1d):
        """Gate: Z-Score não deve escalar acima de MAD e JS em dado limpo."""
        from ..engine.m2_engine import M2Engine
        inputs = {"col": {
            "first_digit_counts": benford_perfect_1d,
            "two_digit_counts": {str(n): 1000 for n in range(10, 100)},
            "truncation_diagnostics": {
                "last_digit_counts": {str(i): 10000 for i in range(10)},
                "round_count": 0,
            },
            "valid_count": 100_000,
        }}
        analyses = M2Engine().run(inputs)
        col = analyses["col"]
        zscore_result = col.by_metric("ZScore_1d")
        assert zscore_result is not None
        # Gate deve ter rebaixado para conforme
        assert zscore_result.flag == BenfordFlag.CONFORME, (
            f"Gate não suprimiu ZScore: flag={zscore_result.flag}, "
            f"detail={zscore_result.detail}"
        )


class TestChi2_1d:
    def test_higher_is_worse_false(self, benford_perfect_1d):
        """Chi2 alto em dado limpo = p-valor alto = conforme."""
        result = Chi2_1d().compute(benford_perfect_1d)
        assert result.flag == BenfordFlag.CONFORME

    def test_p_value_presente(self, benford_perfect_1d):
        result = Chi2_1d().compute(benford_perfect_1d)
        assert result.p_value is not None
        assert 0.0 <= result.p_value <= 1.0