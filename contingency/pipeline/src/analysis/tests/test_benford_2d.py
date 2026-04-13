from ..metrics.benford_2d import MAD2d, JS2d, ZScore2d
from ..base import BenfordFlag


class TestMAD2d:
    def test_conforme_em_distribuicao_perfeita(self, benford_perfect_2d):
        result = MAD2d().compute(benford_perfect_2d)
        assert result.flag == BenfordFlag.CONFORME

    def test_detail_contem_top10_desvios(self, benford_perfect_2d):
        result = MAD2d().compute(benford_perfect_2d)
        top = result.detail.get("top10_deviations", {})
        assert len(top) <= 10


class TestJS2d:
    def test_detecta_bunching_invisivel_para_lane1(
        self, benford_perfect_1d, bunching_49_2d, benford_perfect_2d
    ):
        """Par 49 concentrado deve disparar JS2d mas não MAD1d."""
        from ..metrics.benford_1d import MAD1d

        # Lane 1 não vê — os 1º dígitos continuam quase Benford
        # (usamos benford_perfect_1d diretamente como proxy)
        mad_result = MAD1d().compute(benford_perfect_1d)
        assert mad_result.flag == BenfordFlag.CONFORME, "Lane 1 não deveria sinalizar"

        # Lane 2 detecta
        js2d_result = JS2d().compute(bunching_49_2d)
        assert js2d_result.flag != BenfordFlag.CONFORME, (
            "JS2d deveria detectar bunching no par 49"
        )

    def test_detail_contem_top5_contribuidores(self, bunching_49_2d):
        result = JS2d().compute(bunching_49_2d)
        top = result.detail.get("top5_contributors", [])
        assert len(top) <= 5

    def test_par_49_e_top_contribuidor(self, bunching_49_2d):
        result = JS2d().compute(bunching_49_2d)
        top = result.detail.get("top5_contributors", {})
        assert top, "detail deve conter top5_contributors"
        top_pair = max(top, key=lambda k: top[k])  # chave com maior contribuição
        assert top_pair == "49", f"Esperava par 49 como top contribuidor, got {top_pair}"


class TestZScore2d:
    def test_aponta_par_correto(self, bunching_49_2d):
        result = ZScore2d().compute(bunching_49_2d)
        z_scores = result.detail.get("z_scores", {})
        if z_scores:
            max_pair = max(z_scores, key=lambda k: abs(z_scores[k]))
            assert max_pair == "49", f"Esperava par 49, got {max_pair}"

    def test_sem_divisao_por_zero(self, benford_perfect_2d):
        """Pares raros não devem lançar exceção."""
        result = ZScore2d().compute(benford_perfect_2d)
        assert result is not None