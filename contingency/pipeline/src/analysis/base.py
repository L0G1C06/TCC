"""
analysis/metrics/base.py

Contrato central do M2 — tipos e interface que todas as métricas implementam.
Nenhuma lógica estatística aqui: só definições.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Literal


# ── Flag de conformidade ──────────────────────────────────────────────────────

class BenfordFlag(str, Enum):
    """
    Nível de conformidade de uma métrica individual.

    Herda de str para serialização direta em JSON sem conversores extras:
        json.dumps(flag)  →  '"conforme"'

    Valores ASCII puro — sem acentos — para evitar ambiguidade em
    comparações de string, logging e serialização cross-platform.
    """
    CONFORME = "conforme"
    ALERTA   = "alerta"
    CRITICO  = "critico"


# ── Resultado tipado por métrica ──────────────────────────────────────────────

@dataclass(frozen=True)
class MetricResult:
    """
    Saída padronizada de qualquer métrica do M2.

    Campos
    ------
    metric  : identificador da métrica  (ex: "MAD_1d", "JS_2d", "last_digit")
    value   : valor calculado           (ex: 0.0082, 0.031)
    p_value : probabilidade sob H₀      (None quando não aplicável, ex: MAD)
    flag    : nível de conformidade     (conforme | alerta | critico)
    detail  : dict opcional para dados auxiliares —
              Z-scores por dígito, qui-quadrado por célula, etc.
              Nunca afeta o score do M4 — só para diagnóstico.
    """
    metric  : str
    value   : float
    p_value : float | None
    flag    : BenfordFlag
    detail  : dict | None = None

    @property
    def signaled(self) -> bool:
        """True se a métrica detectou qualquer desvio (alerta ou crítico)."""
        return self.flag != BenfordFlag.CONFORME


# ── Interface abstrata ────────────────────────────────────────────────────────

class BenfordMetric(ABC):
    """
    Classe base stateless para todas as métricas do M2.

    Cada subclasse implementa um único método `compute()` que recebe
    contadores brutos e devolve um MetricResult — sem estado interno,
    sem efeitos colaterais, reutilizável para N colunas.

    Subclasses concretas
    --------------------
    Lane 1  →  MAD1d, JS1d, ZScore1d, Chi2_1d       (benford_1d.py)
    Lane 2  →  MAD2d, JS2d, ZScore2d                 (benford_2d.py)
    Lane 3  →  LastDigitChi2, DigitPreference         (last_digit.py)
    """

    @abstractmethod
    def compute(self, counts: dict[str, int]) -> MetricResult:
        """
        Executa o cálculo estatístico sobre os contadores brutos.

        Parâmetros
        ----------
        counts : dict[str, int]
            Contadores brutos extraídos do _MODULE_ELIGIBILITY.json:
            - Lane 1 → {"1": int, ..., "9": int}          (9 entradas)
            - Lane 2 → {"10": int, ..., "99": int}         (90 entradas)
            - Lane 3 → {"0": int, ..., "9": int}           (10 entradas)

        Retorno
        -------
        MetricResult com metric, value, p_value, flag e detail preenchidos.
        """

    # ── Helpers compartilhados ────────────────────────────────────────────────

    @staticmethod
    def _to_array(counts: dict[str, int], keys: list[str]) -> "np.ndarray":
        """
        Converte um dict de contadores para array NumPy na ordem de `keys`.
        Chaves ausentes viram zero — nunca levanta KeyError.

        Exemplo
        -------
            obs = BenfordMetric._to_array(counts, [str(d) for d in range(1, 10)])
        """
        import numpy as np
        return np.array([counts.get(k, 0) for k in keys], dtype=np.float64)

    @staticmethod
    def _resolve_flag(
        value: float,
        *,
        alerta: float,
        critico: float,
        higher_is_worse: bool = True,
    ) -> BenfordFlag:
        """
        Mapeia um valor escalar para BenfordFlag com base em dois thresholds.

        Parâmetros
        ----------
        value           : valor da métrica a classificar
        alerta          : limiar inferior de desvio
        critico         : limiar de desvio grave
        higher_is_worse : True  → valor alto é pior  (MAD, JS, χ²)
                          False → valor baixo é pior  (p-value)

        Exemplos
        --------
            _resolve_flag(0.008, alerta=0.006, critico=0.015)
            → BenfordFlag.ALERTA

            _resolve_flag(0.001, alerta=0.05, critico=0.01, higher_is_worse=False)
            → BenfordFlag.CRITICO

        Pré-condição para higher_is_worse=False
        ----------------------------------------
            critico < alerta  (p-values: critico=0.01, alerta=0.05)
        """
        if higher_is_worse:
            if value >= critico:
                return BenfordFlag.CRITICO
            if value >= alerta:
                return BenfordFlag.ALERTA
            return BenfordFlag.CONFORME
        else:
            if value <= critico:
                return BenfordFlag.CRITICO
            if value <= alerta:
                return BenfordFlag.ALERTA
            return BenfordFlag.CONFORME