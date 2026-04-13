"""
analysis/metrics/benford_2d.py

Lane 2 — Benford dois primeiros dígitos.
Três métricas sobre pares d₁d₂ ∈ 10–99.
MAD e JS rodam em paralelo; Z-Score roda após eles.

Sem χ² nesta lane — o M2_SPEC define χ² como exclusivo da Lane 1
por ser referência complementar para stakeholders, não métrica de decisão.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from ..base import BenfordFlag, BenfordMetric, MetricResult

# ── Distribuição esperada ─────────────────────────────────────────────────────

_DIGITS_2D: list[str] = [str(d) for d in range(10, 100)]   # 90 pares

_EXPECTED_2D: np.ndarray = np.log10(1.0 + 1.0 / np.arange(10, 100, dtype=np.float64))
_EXPECTED_2D /= _EXPECTED_2D.sum()
# Normalização explícita necessária: ao contrário dos 9 dígitos de Benford 1d,
# os 90 pares não somam exatamente 1.0 em aritmética de ponto flutuante.
# A divisão pela soma garante que JS e MAD operem sobre distribuições válidas.

# ── Thresholds ────────────────────────────────────────────────────────────────

# MAD — Nigrini (2012) recomenda os mesmos limiares absolutos para 2d
# O desvio esperado por célula é menor (90 pares vs 9 dígitos), então
# um MAD alto aqui é sinal mais forte do que na Lane 1.
_MAD_ALERTA  = 0.006
_MAD_CRITICO = 0.015

# JS — limiares mais conservadores que 1d: com 90 células a distribuição
# suaviza naturalmente; desvios concentrados em poucos pares (ex: 49, 99)
# são exatamente o que esta lane detecta.
_JS_ALERTA   = 0.003
_JS_CRITICO  = 0.010

# Z-Score — mesmos limiares de Nigrini; interpretação idêntica à Lane 1
_Z_ALERTA    = 1.96
_Z_CRITICO   = 2.576


# ── MAD ───────────────────────────────────────────────────────────────────────

class MAD2d(BenfordMetric):
    """
    Mean Absolute Deviation sobre os 90 pares d₁d₂.

        MAD = mean(|p_obs − p_exp|)   para d ∈ 10–99

    Detecta desvio global na distribuição de pares.
    Fraudadores que conhecem Benford e respeitam o 1º dígito, mas
    concentram valores em pares específicos (ex: 49, 99), aparecem
    aqui sem sinalizar na Lane 1.

    p_value = None: mesmo critério do MAD1d.
    """

    def compute(self, counts: dict[str, int]) -> MetricResult:
        obs = self._to_array(counts, _DIGITS_2D)
        n   = obs.sum()

        if n == 0:
            return MetricResult(
                metric="MAD_2d", value=0.0, p_value=None,
                flag=BenfordFlag.CONFORME,
                detail={"error": "empty_counts"},
            )

        p_obs = obs / n
        mad   = float(np.mean(np.abs(p_obs - _EXPECTED_2D)))
        flag  = self._resolve_flag(mad, alerta=_MAD_ALERTA, critico=_MAD_CRITICO)

        # detail: só os 10 pares mais desviantes — evita serializar 90 entradas
        deviations = np.abs(p_obs - _EXPECTED_2D)
        top10_idx  = np.argsort(deviations)[::-1][:10]

        return MetricResult(
            metric="MAD_2d",
            value=round(mad, 6),
            p_value=None,
            flag=flag,
            detail={
                "n": int(n),
                "top10_deviations": {
                    _DIGITS_2D[i]: {
                        "p_obs": round(float(p_obs[i]), 6),
                        "p_exp": round(float(_EXPECTED_2D[i]), 6),
                        "dev":   round(float(deviations[i]), 6),
                    }
                    for i in top10_idx
                },
            },
        )


# ── Jensen-Shannon ────────────────────────────────────────────────────────────

class JS2d(BenfordMetric):
    """
    Jensen-Shannon divergence sobre os 90 pares d₁d₂.

        JS(P‖Q) = ½·KL(P‖M) + ½·KL(Q‖M),   M = (P + Q) / 2

    - Laplace smoothing (α=1) em p_obs com denominador correto para 90 células.
    - p_exp normalizado no nível de módulo — sem risco de log(0).
    - Limiares mais baixos que JS1d: com 90 células qualquer concentração
      artificial produz JS maior do que produziria na Lane 1.

    Cenário-alvo: fraudador que distribui corretamente o 1º dígito mas
    concentra pares em 49 ou 99 (just-below-threshold clássico).
    """

    _ALPHA = 1.0
    _N_CELLS = 90

    def compute(self, counts: dict[str, int]) -> MetricResult:
        obs = self._to_array(counts, _DIGITS_2D)
        n   = obs.sum()

        if n == 0:
            return MetricResult(
                metric="JS_2d", value=0.0, p_value=None,
                flag=BenfordFlag.CONFORME,
                detail={"error": "empty_counts"},
            )

        p_obs = (obs + self._ALPHA) / (n + self._ALPHA * self._N_CELLS)
        p_exp = _EXPECTED_2D

        m  = 0.5 * (p_obs + p_exp)
        js = float(0.5 * (
            np.sum(p_obs * np.log2(p_obs / m)) +
            np.sum(p_exp * np.log2(p_exp / m))
        ))
        js   = max(0.0, js)
        flag = self._resolve_flag(js, alerta=_JS_ALERTA, critico=_JS_CRITICO)

        # detail: top 5 pares com maior contribuição ao JS total
        contrib    = 0.5 * (
            p_obs * np.log2(p_obs / m) +
            p_exp * np.log2(p_exp / m)
        )
        top5_idx = np.argsort(contrib)[::-1][:5]

        return MetricResult(
            metric="JS_2d",
            value=round(js, 6),
            p_value=None,
            flag=flag,
            detail={
                "n": int(n),
                "top5_contributors": {
                    _DIGITS_2D[i]: round(float(contrib[i]), 6)
                    for i in top5_idx
                },
            },
        )


# ── Z-Score por par ───────────────────────────────────────────────────────────

class ZScore2d(BenfordMetric):
    """
    Z-Score individual por par d₁d₂ ∈ 10–99.
    Fórmula com correção de continuidade — Nigrini (2012):

        Z_d = max(|p_obs_d − p_exp_d| − 1/(2n), 0) / √(p_exp_d·(1−p_exp_d)/n)

    Interpretado apenas quando MAD2d ou JS2d sinalizaram desvio.
    Aponta o par específico responsável pelo desvio global — útil
    para o auditor identificar o threshold manipulado.

    value   = Z_max  (par mais desviante)
    p_value = p bilateral do par mais desviante
    detail  = top 10 Z-scores + par responsável pelo máximo
    """

    def compute(self, counts: dict[str, int]) -> MetricResult:
        obs = self._to_array(counts, _DIGITS_2D)
        n   = obs.sum()

        if n == 0:
            return MetricResult(
                metric="ZScore_2d", value=0.0, p_value=None,
                flag=BenfordFlag.CONFORME,
                detail={"error": "empty_counts"},
            )

        p_obs = obs / n
        exp   = _EXPECTED_2D

        numerator   = np.maximum(np.abs(p_obs - exp) - 1.0 / (2.0 * n), 0.0)
        denominator = np.sqrt(exp * (1.0 - exp) / n)

        # Proteção: células com p_exp próximo de zero têm denominador ~0.
        # Ocorre apenas se two_digit_counts tiver contagens esparsas em
        # pares raros — clipa Z nesses casos para não inflar artificialmente.
        with np.errstate(invalid="ignore", divide="ignore"):
            z_scores = np.where(denominator > 1e-12, numerator / denominator, 0.0)

        z_max     = float(z_scores.max())
        max_idx   = int(np.argmax(z_scores))
        max_pair  = _DIGITS_2D[max_idx]
        p_value   = float(2.0 * (1.0 - stats.norm.cdf(z_max)))

        flag = self._resolve_flag(z_max, alerta=_Z_ALERTA, critico=_Z_CRITICO)

        top10_idx = np.argsort(z_scores)[::-1][:10]

        return MetricResult(
            metric="ZScore_2d",
            value=round(z_max, 4),
            p_value=round(p_value, 6),
            flag=flag,
            detail={
                "n": int(n),
                "max_pair": max_pair,
                "top10_z_scores": {
                    _DIGITS_2D[i]: round(float(z_scores[i]), 4)
                    for i in top10_idx
                },
            },
        )