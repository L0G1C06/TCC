"""
analysis/metrics/last_digit.py

Lane 3 — Último dígito.
Duas métricas independentes de Benford — hipótese nula distinta.

H₀: distribuição uniforme, P = 10% para cada dígito 0–9.

Detecta digit preference e arredondamento artificial — padrões
invisíveis a qualquer variante da Lei de Benford porque o último
dígito é estatisticamente independente do primeiro.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from ..base import BenfordFlag, BenfordMetric, MetricResult

# ── Distribuição esperada ─────────────────────────────────────────────────────

_DIGITS_LAST: list[str] = [str(d) for d in range(10)]   # "0" … "9"

_EXPECTED_UNIFORM: np.ndarray = np.full(10, 0.10, dtype=np.float64)
# H₀ distinta de Benford: cada dígito 0–9 com probabilidade exatamente 10%.

# ── Thresholds ────────────────────────────────────────────────────────────────

# χ² — p-value; graus de liberdade = 9 (10 dígitos − 1)
_CHI2_ALERTA  = 0.05
_CHI2_CRITICO = 0.01

# Digit preference — frequência do dígito suspeito
# 0 e 5 concentram arredondamentos; limiar empírico sobre dados fiscais reais.
# Uniforme esperada = 0.10; acima de 0.15 é sinal de arredondamento sistemático.
_DP_ALERTA_0  = 0.15    # dígito 0: arredondamento para centenas/milhares
_DP_CRITICO_0 = 0.25    # threshold do M1 para digit_spike — consistência intencional
_DP_ALERTA_5  = 0.15    # dígito 5: arredondamento para 50, 500, 5000…
_DP_CRITICO_5 = 0.20    # threshold do M1 para digit_spike — consistência intencional


# ── χ² de aderência à uniforme ────────────────────────────────────────────────

class LastDigitChi2(BenfordMetric):
    """
    Teste χ² de aderência à distribuição uniforme sobre 0–9.

        χ² = Σ (obs_d − n/10)² / (n/10)   para d ∈ 0–9

    Graus de liberdade = 9.

    - Complementa a Lane 1: detecta arredondamento e digit preference
      que passam despercebidos quando o 1º dígito está em conformidade.
    - Não é referência complementar como o χ² da Lane 1 — aqui é a
      métrica principal porque a H₀ uniforme tem teste formal natural.

    value   = estatística χ²
    p_value = P(χ²(9) ≥ valor observado)
    detail  = contagens observadas vs esperadas por dígito
    """

    _DF = 9

    def compute(self, counts: dict[str, int]) -> MetricResult:
        obs = self._to_array(counts, _DIGITS_LAST)
        n   = obs.sum()

        if n == 0:
            return MetricResult(
                metric="last_digit_chi2", value=0.0, p_value=None,
                flag=BenfordFlag.CONFORME,
                detail={"error": "empty_counts"},
            )

        exp_counts = _EXPECTED_UNIFORM * n          # n/10 por célula
        chi2_stat  = float(np.sum((obs - exp_counts) ** 2 / exp_counts))
        p_value    = float(1.0 - stats.chi2.cdf(chi2_stat, df=self._DF))

        # p_value pequeno = problema → higher_is_worse=False
        flag = self._resolve_flag(
            p_value,
            alerta=_CHI2_ALERTA,
            critico=_CHI2_CRITICO,
            higher_is_worse=False,
        )

        p_obs = obs / n
        return MetricResult(
            metric="last_digit_chi2",
            value=round(chi2_stat, 4),
            p_value=round(p_value, 6),
            flag=flag,
            detail={
                "df": self._DF,
                "n": int(n),
                "observed": {
                    _DIGITS_LAST[i]: {
                        "count":   int(obs[i]),
                        "p_obs":   round(float(p_obs[i]), 4),
                        "p_exp":   0.10,
                        "contrib": round(float((obs[i] - exp_counts[i]) ** 2 / exp_counts[i]), 4),
                    }
                    for i in range(10)
                },
            },
        )


# ── Digit preference ──────────────────────────────────────────────────────────

class DigitPreference(BenfordMetric):
    """
    Detecta concentração anormal nos dígitos 0 e 5 — sinal de
    arredondamento artificial ou digit preference em licitações.

    Exemplos reais de manipulação:
        R$ 49.999,00  → último dígito 9  (just-below-threshold, Lane 2)
        R$ 50.000,00  → último dígito 0  (arredondamento, esta lane)
        R$ 15.500,00  → último dígito 0  (arredondamento para centena)

    Hipótese nula: freq(0) ≈ 10%  e  freq(5) ≈ 10%.
    Desvio > 50% acima do esperado (> 0.15) é sinal de alerta.

    value   = max(freq_0, freq_5) — o pior dos dois
    p_value = p bilateral do Z-test sobre o dígito mais desviante
    detail  = frequências de 0 e 5, Z-scores individuais, n
    """

    def compute(self, counts: dict[str, int]) -> MetricResult:
        obs = self._to_array(counts, _DIGITS_LAST)
        n   = obs.sum()

        if n == 0:
            return MetricResult(
                metric="digit_preference", value=0.0, p_value=None,
                flag=BenfordFlag.CONFORME,
                detail={"error": "empty_counts"},
            )

        p_obs = obs / n
        freq_0 = float(p_obs[0])
        freq_5 = float(p_obs[5])

        # Z-test bilateral para cada dígito suspeito
        # H₀: p = 0.10  →  σ = √(0.10 · 0.90 / n)
        sigma  = np.sqrt(0.10 * 0.90 / n)
        z_0    = float((freq_0 - 0.10) / sigma)
        z_5    = float((freq_5 - 0.10) / sigma)
        p_0    = float(2.0 * (1.0 - stats.norm.cdf(abs(z_0))))
        p_5    = float(2.0 * (1.0 - stats.norm.cdf(abs(z_5))))

        # value = frequência do dígito mais desviante acima do esperado
        # Só contabiliza desvio positivo: freq abaixo de 10% não é digit preference
        worst_freq = max(freq_0, freq_5)
        worst_p    = p_0 if freq_0 >= freq_5 else p_5
        worst_digit = 0 if freq_0 >= freq_5 else 5

        # Flag: baseada no dígito com threshold mais adequado
        if worst_digit == 0:
            flag = self._resolve_flag(
                worst_freq, alerta=_DP_ALERTA_0, critico=_DP_CRITICO_0
            )
        else:
            flag = self._resolve_flag(
                worst_freq, alerta=_DP_ALERTA_5, critico=_DP_CRITICO_5
            )

        return MetricResult(
            metric="digit_preference",
            value=round(worst_freq, 4),
            p_value=round(worst_p, 6),
            flag=flag,
            detail={
                "n": int(n),
                "worst_digit": worst_digit,
                "freq_0": round(freq_0, 4),
                "freq_5": round(freq_5, 4),
                "z_0":   round(z_0, 4),
                "z_5":   round(z_5, 4),
                "p_0":   round(p_0, 6),
                "p_5":   round(p_5, 6),
                "all_freqs": {
                    _DIGITS_LAST[i]: round(float(p_obs[i]), 4) for i in range(10)
                },
            },
        )