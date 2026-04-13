"""
analysis/metrics/benford_1d.py

Lane 1 — Benford primeiro dígito.
Quatro métricas independentes sobre a mesma distribuição observada.
MAD e JS rodam em paralelo; Z-Score e χ² rodam em paralelo após eles.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from ..base import BenfordFlag, BenfordMetric, MetricResult

# ── Distribuição esperada ─────────────────────────────────────────────────────

_DIGITS_1D: list[str] = [str(d) for d in range(1, 10)]

_EXPECTED_1D: np.ndarray = np.log10(1.0 + 1.0 / np.arange(1, 10, dtype=np.float64))
# Soma exata = 1.0 por construção matemática — nenhuma normalização necessária.

# ── Thresholds ────────────────────────────────────────────────────────────────

# MAD — Nigrini (2012), tabela de conformidade
_MAD_ALERTA  = 0.006    # limite: close conformity → acceptable conformity
_MAD_CRITICO = 0.015    # limite: marginally acceptable → nonconformity

# JS — empírico; valores típicos em dados fiscais reais ficam abaixo de 0.002
# Referência: Kossovsky (2014) — desvios acima de 0.012 indicam manipulação
_JS_ALERTA   = 0.004
_JS_CRITICO  = 0.012

# Z-Score — Nigrini (2012): significativo a 95% / 99%
_Z_ALERTA    = 1.96
_Z_CRITICO   = 2.576

# χ² — p-value: referência clássica, não métrica de decisão
_CHI2_ALERTA  = 0.05
_CHI2_CRITICO = 0.01


# ── MAD ───────────────────────────────────────────────────────────────────────

class MAD1d(BenfordMetric):
    """
    Mean Absolute Deviation entre distribuição observada e Benford esperado.
    Métrica primária do auditor — Nigrini (2012).

        MAD = mean(|p_obs − p_exp|)

    p_value = None: MAD não tem distribuição de referência formal.
    O auditor interpreta o valor absoluto pelos thresholds de Nigrini.
    """

    def compute(self, counts: dict[str, int]) -> MetricResult:
        obs = self._to_array(counts, _DIGITS_1D)
        n   = obs.sum()

        if n == 0:
            return MetricResult(
                metric="MAD_1d", value=0.0, p_value=None,
                flag=BenfordFlag.CONFORME,
                detail={"error": "empty_counts"},
            )

        p_obs = obs / n
        mad   = float(np.mean(np.abs(p_obs - _EXPECTED_1D)))
        flag  = self._resolve_flag(mad, alerta=_MAD_ALERTA, critico=_MAD_CRITICO)

        return MetricResult(
            metric="MAD_1d",
            value=round(mad, 6),
            p_value=None,
            flag=flag,
            detail={
                "n": int(n),
                "p_obs": {str(i + 1): round(float(p_obs[i]), 6) for i in range(9)},
                "p_exp": {str(i + 1): round(float(_EXPECTED_1D[i]), 6) for i in range(9)},
            },
        )


# ── Jensen-Shannon ────────────────────────────────────────────────────────────

class JS1d(BenfordMetric):
    """
    Jensen-Shannon divergence entre distribuição observada e Benford esperado.

        M       = (P + Q) / 2
        JS(P‖Q) = ½·KL(P‖M) + ½·KL(Q‖M)

    - Simétrico e limitado em [0, 1] com log₂.
    - Laplace smoothing (α=1) aplicado apenas em p_obs para evitar log(0).
      p_exp não precisa — log₁₀(1 + 1/d) > 0 para todo d ∈ 1–9.
    - Detecta fraudadores que respeitam o 1º dígito mas concentram
      pares específicos — complementa o MAD nesse cenário.

    p_value = None: JS não tem distribuição assintótica simples com Laplace.
    """

    _ALPHA = 1.0   # parâmetro de Laplace smoothing

    def compute(self, counts: dict[str, int]) -> MetricResult:
        obs = self._to_array(counts, _DIGITS_1D)
        n   = obs.sum()

        if n == 0:
            return MetricResult(
                metric="JS_1d", value=0.0, p_value=None,
                flag=BenfordFlag.CONFORME,
                detail={"error": "empty_counts"},
            )

        # Laplace smoothing só em p_obs — p_exp é matematicamente seguro
        p_obs = (obs + self._ALPHA) / (n + self._ALPHA * 9)
        p_exp = _EXPECTED_1D

        m  = 0.5 * (p_obs + p_exp)
        js = float(0.5 * (
            np.sum(p_obs * np.log2(p_obs / m)) +
            np.sum(p_exp * np.log2(p_exp / m))
        ))
        js   = max(0.0, js)   # proteção contra arredondamento numérico (−ε)
        flag = self._resolve_flag(js, alerta=_JS_ALERTA, critico=_JS_CRITICO)

        return MetricResult(
            metric="JS_1d",
            value=round(js, 6),
            p_value=None,
            flag=flag,
            detail={
                "n": int(n),
                "p_obs_smoothed": {
                    str(i + 1): round(float(p_obs[i]), 6) for i in range(9)
                },
            },
        )


# ── Z-Score por dígito ────────────────────────────────────────────────────────

class ZScore1d(BenfordMetric):
    """
    Z-Score individual por dígito d ∈ 1–9.
    Fórmula com correção de continuidade — Nigrini (2012):

        Z_d = max(|p_obs_d − p_exp_d| − 1/(2n), 0) / √(p_exp_d·(1−p_exp_d)/n)

    Sempre calculado, mas interpretado apenas quando MAD ou JS
    sinalizaram desvio — o engine aplica essa regra, não esta classe.

    value   = Z_max  (dígito mais desviante)
    p_value = p bilateral do dígito mais desviante
    detail  = z_scores de todos os nove dígitos + dígito responsável
    """

    def compute(self, counts: dict[str, int]) -> MetricResult:
        obs = self._to_array(counts, _DIGITS_1D)
        n   = obs.sum()

        if n == 0:
            return MetricResult(
                metric="ZScore_1d", value=0.0, p_value=None,
                flag=BenfordFlag.CONFORME,
                detail={"error": "empty_counts"},
            )

        p_obs = obs / n
        exp   = _EXPECTED_1D

        # Correção de continuidade: clipa em 0 para não produzir Z negativo
        numerator   = np.maximum(np.abs(p_obs - exp) - 1.0 / (2.0 * n), 0.0)
        denominator = np.sqrt(exp * (1.0 - exp) / n)
        z_scores    = numerator / denominator

        z_max       = float(z_scores.max())
        max_digit   = int(np.argmax(z_scores)) + 1   # dígito 1-indexed
        p_value     = float(2.0 * (1.0 - stats.norm.cdf(z_max)))

        flag = self._resolve_flag(z_max, alerta=_Z_ALERTA, critico=_Z_CRITICO)

        return MetricResult(
            metric="ZScore_1d",
            value=round(z_max, 4),
            p_value=round(p_value, 6),
            flag=flag,
            detail={
                "n": int(n),
                "z_scores": {
                    str(i + 1): round(float(z_scores[i]), 4) for i in range(9)
                },
                "max_digit": max_digit,
            },
        )


# ── Chi-Quadrado ──────────────────────────────────────────────────────────────

class Chi2_1d(BenfordMetric):
    """
    Teste χ² clássico de aderência à distribuição de Benford.
    Graus de liberdade = 8  (9 dígitos − 1).

    Referência complementar — NUNCA a métrica de decisão principal.
    Com n > 100 000, o χ² quase sempre rejeita H₀ mesmo para desvios
    irrelevantes do ponto de vista do auditor.

    Use MAD e JS para decidir; use χ² para comunicar significância
    formal a stakeholders que exigem p-value.

    value   = estatística χ²
    p_value = P(χ²(8) ≥ valor observado)
    """

    _DF = 8

    def compute(self, counts: dict[str, int]) -> MetricResult:
        obs = self._to_array(counts, _DIGITS_1D)
        n   = obs.sum()

        if n == 0:
            return MetricResult(
                metric="Chi2_1d", value=0.0, p_value=None,
                flag=BenfordFlag.CONFORME,
                detail={"error": "empty_counts"},
            )

        exp_counts = _EXPECTED_1D * n
        chi2_stat  = float(np.sum((obs - exp_counts) ** 2 / exp_counts))
        p_value    = float(1.0 - stats.chi2.cdf(chi2_stat, df=self._DF))

        # p_value pequeno = problema → higher_is_worse=False
        flag = self._resolve_flag(
            p_value,
            alerta=_CHI2_ALERTA,
            critico=_CHI2_CRITICO,
            higher_is_worse=False,
        )

        return MetricResult(
            metric="Chi2_1d",
            value=round(chi2_stat, 4),
            p_value=round(p_value, 6),
            flag=flag,
            detail={
                "df": self._DF,
                "n": int(n),
                "expected_counts": {
                    str(i + 1): round(float(exp_counts[i]), 2) for i in range(9)
                },
            },
        )