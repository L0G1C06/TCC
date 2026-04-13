"""
analysis/engine/m2_engine.py

Orquestrador do M2 — dispara as três lanes em paralelo e aplica
a regra de interpretação condicional do Z-Score.
Stateless — instanciar uma vez, reutilizar para N módulos.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..base import BenfordFlag, MetricResult
from ..metrics.benford_1d import MAD1d, JS1d, ZScore1d, Chi2_1d
from ..metrics.benford_2d import MAD2d, JS2d, ZScore2d
from ..metrics.last_digit import LastDigitChi2, DigitPreference

logger = logging.getLogger(__name__)

# ── Singletons — stateless, seguros para compartilhar entre threads ───────────
_MAD1D    = MAD1d()
_JS1D     = JS1d()
_ZSCORE1D = ZScore1d()
_CHI2_1D  = Chi2_1d()
_MAD2D    = MAD2d()
_JS2D     = JS2d()
_ZSCORE2D = ZScore2d()
_LAST_CHI2 = LastDigitChi2()
_DIGIT_PREF = DigitPreference()

_FLAG_ORDER: dict[BenfordFlag, int] = {
    BenfordFlag.CONFORME: 0,
    BenfordFlag.ALERTA:   1,
    BenfordFlag.CRITICO:  2,
}


# ── Resultado por coluna ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class ColumnAnalysis:
    """
    Resultado completo do M2 para uma coluna.
    Imutável — produzido em thread, consumido pelo scorer e pelo dashboard.
    """
    column : str
    results: tuple[MetricResult, ...]

    @property
    def has_anomaly(self) -> bool:
        return any(r.signaled for r in self.results)

    @property
    def critical_metrics(self) -> list[MetricResult]:
        return [r for r in self.results if r.flag == BenfordFlag.CRITICO]

    @property
    def alert_metrics(self) -> list[MetricResult]:
        return [r for r in self.results if r.flag == BenfordFlag.ALERTA]

    @property
    def worst_flag(self) -> BenfordFlag:
        return max(self.results, key=lambda r: _FLAG_ORDER[r.flag]).flag

    def by_metric(self, name: str) -> MetricResult | None:
        """Acesso rápido por nome — ex: analysis.by_metric('MAD_1d')."""
        return next((r for r in self.results if r.metric == name), None)


# ── Engine ────────────────────────────────────────────────────────────────────

class M2Engine:
    """
    Motor estatístico do M2.

    Paralelismo:
        - As três lanes disparam simultaneamente.
        - Dentro de cada lane, MAD e JS são submetidos como futures
          independentes antes de qualquer .result() ser chamado.
        - Z-Score de cada lane é submetido após MAD e JS completarem,
          em conformidade com o M2_SPEC.
        - χ² da Lane 1 é submetido junto com o Z-Score — mesmo momento,
          futures independentes.
        - Lane 3 (χ² uniforme + digit preference) roda do início ao fim
          em paralelo com as Lanes 1 e 2.

    max_workers = 6:
        Pico de concorrência no primeiro round:
        MAD_1d · JS_1d · MAD_2d · JS_2d · LastDigitChi2 · DigitPreference = 6.
        No segundo round (Z + χ² por lane) o pool já tem workers livres.
    """

    def __init__(self, max_workers: int = 6):
        self._max_workers = max_workers

    # ── Interface pública ─────────────────────────────────────────────────────

    def run(self, column_inputs: dict[str, dict]) -> dict[str, ColumnAnalysis]:
        """
        Executa o M2 completo para todas as colunas elegíveis do módulo.

        Parâmetros
        ----------
        column_inputs : saída de S3Reader.get_analysis_input()
            {
              "col": {
                "first_digit_counts": {"1": int, ..., "9": int},
                "two_digit_counts":   {"10": int, ..., "99": int},
                "last_digit_counts":  {"0": int, ..., "9": int},
              }
            }

        Retorno
        -------
        dict[str, ColumnAnalysis]
        """
        analyses: dict[str, ColumnAnalysis] = {}
        for col, inputs in column_inputs.items():
            try:
                analyses[col] = self._run_column(col, inputs)
            except Exception as exc:
                logger.error("M2 falhou na coluna '%s': %s", col, exc)
                analyses[col] = _error_analysis(col, exc)
        return analyses

    # ── Execução por coluna ───────────────────────────────────────────────────

    def _run_column(self, col: str, inputs: dict) -> ColumnAnalysis:
        first = inputs.get("first_digit_counts", {})
        two   = inputs.get("two_digit_counts", {})
        last  = inputs.get("last_digit_counts", {})

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:

            # ── Round 1: MAD e JS das Lanes 1 e 2 + Lane 3 completa ──────
            # Seis futures submetidos antes de qualquer .result() —
            # garante que o pool os execute verdadeiramente em paralelo.
            f_mad1  = pool.submit(_MAD1D.compute,    first)
            f_js1   = pool.submit(_JS1D.compute,     first)
            f_mad2  = pool.submit(_MAD2D.compute,    two)
            f_js2   = pool.submit(_JS2D.compute,     two)
            f_lchi2 = pool.submit(_LAST_CHI2.compute, last)
            f_dpref = pool.submit(_DIGIT_PREF.compute, last)

            # ── Coleta Round 1 ────────────────────────────────────────────
            mad1  = f_mad1.result()
            js1   = f_js1.result()
            mad2  = f_mad2.result()
            js2   = f_js2.result()
            lchi2 = f_lchi2.result()
            dpref = f_dpref.result()

            # ── Round 2: Z-Score e χ² após MAD/JS ────────────────────────
            # χ² da Lane 1 submetido junto com Z1 — paralelos entre si.
            f_z1   = pool.submit(_ZSCORE1D.compute, first)
            f_chi2 = pool.submit(_CHI2_1D.compute,  first)
            f_z2   = pool.submit(_ZSCORE2D.compute, two)

            # ── Coleta Round 2 ────────────────────────────────────────────
            z1   = f_z1.result()
            chi2 = f_chi2.result()
            z2   = f_z2.result()

        # ── Regra de interpretação condicional do Z-Score ─────────────────
        z1 = _apply_zscore_gate(z1, mad1, js1)
        z2 = _apply_zscore_gate(z2, mad2, js2)

        # Ordem canônica: Lane 1 → Lane 2 → Lane 3
        results = (mad1, js1, z1, chi2, mad2, js2, z2, lchi2, dpref)

        _log_column_summary(col, results)

        return ColumnAnalysis(column=col, results=results)


# ── Funções auxiliares ────────────────────────────────────────────────────────

def _apply_zscore_gate(
    zscore: MetricResult,
    *primary: MetricResult,
) -> MetricResult:
    """
    Regra do M2_SPEC: Z-Score é sempre calculado, mas o flag só é
    elevado se MAD ou JS da mesma lane sinalizaram desvio.

    Quando o gate suprime o flag:
        - value e p_value são preservados intactos.
        - detail recebe a chave "gate" explicando a supressão.
        - O scorer do M4 recebe CONFORME e não penaliza o score.
        - O auditor ainda pode inspecionar o Z real no detail.
    """
    if any(m.signaled for m in primary):
        return zscore

    if zscore.flag == BenfordFlag.CONFORME:
        return zscore

    return MetricResult(
        metric=zscore.metric,
        value=zscore.value,
        p_value=zscore.p_value,
        flag=BenfordFlag.CONFORME,
        detail={
            **(zscore.detail or {}),
            "gate": "flag suprimido — MAD e JS conformes nesta lane",
        },
    )


def _error_analysis(col: str, exc: Exception) -> ColumnAnalysis:
    """
    Produz um ColumnAnalysis de fallback quando uma coluna falha
    completamente — evita que um erro em uma coluna derrube o módulo.
    """
    error_result = MetricResult(
        metric="engine_error",
        value=0.0,
        p_value=None,
        flag=BenfordFlag.CONFORME,
        detail={"error": str(exc), "type": type(exc).__name__},
    )
    return ColumnAnalysis(column=col, results=(error_result,))


def _log_column_summary(col: str, results: tuple[MetricResult, ...]) -> None:
    flagged = [r for r in results if r.signaled]
    if not flagged:
        logger.debug("M2 [%s] todas as métricas conformes", col)
        return

    worst = max(results, key=lambda r: _FLAG_ORDER[r.flag])
    names = ", ".join(r.metric for r in flagged)
    logger.warning(
        "M2 [%s] anomalia detectada — pior: %s (%s) | sinalizadas: %s",
        col, worst.metric, worst.flag.value, names,
    )